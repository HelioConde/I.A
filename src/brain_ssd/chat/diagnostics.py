"""Privacy-first structured diagnostics for local Brain-SSD experiments.

Records *only* allowlisted numeric counters, booleans, and fixed identifiers.
Never records prompts, model completions, memory contents, file paths, tokens,
raw errors, stack traces or arbitrary metadata. Shared by Windows and Linux.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import statistics
import sys
import threading
import time
import uuid
import zipfile
from typing import Any, Iterable

SCHEMA_VERSION = 1
MAX_FILE_BYTES = 1024 * 1024
MAX_BACKUPS = 4
MAX_EXPORT_EVENTS = 1000
EVENTS = frozenset({
    "session.start", "session.stop", "runtime.ready", "runtime.error",
    "chat.start", "retrieval.done", "memory.recall", "chat.prompt",
    "inference.done", "inference.error", "chat.complete", "chat.cancelled",
    "chat.error", "test.start", "test.result", "test.error",
})
NUMERIC = frozenset({
    "duration_ms", "ttft_ms", "tokens_per_second", "working_set_bytes_max",
    "private_bytes_max", "physical_read_bytes", "sources", "pages",
    "episodes", "history_messages", "prompt_utf8_bytes", "evidence_utf8_bytes",
    "answer_chars", "question_chars", "return_code", "cpu_threads", "count",
    "exit_code", "context_size", "activated_bytes",
})
BOOLEAN = frozenset({"inference_verified", "episodic_enabled", "shadow_enabled"})
ENUMS = {
    "profile": {"economia", "equilibrado", "rapido", "not_applicable"},
    "core_mode": {"subprocess", "persistent", "not_applicable"},
    "status": {"OK", "UNAVAILABLE", "FAIL", "PASS", "ERROR", "CANCELLED",
               "SKIP", "READY", "NOT_APPLICABLE", "UNKNOWN"},
    "suite": {"chat_windows", "chat_runtime", "chat_history", "chat_stream",
              "chat_doctor", "chat_episodic", "chat_episodic_http",
              "cognitive_lab", "consolidation", "core", "storage",
              "router_gating", "cache_policy", "hybrid", "progressive",
              "bench_episodic_memory", "run_cognitive_lab",
              "real_windows_inference"},
    "error_type": {"ValueError", "RuntimeError", "FileNotFoundError",
                   "PermissionError", "OSError", "TimeoutError",
                   "ConnectionError", "BrokenPipeError",
                   "GenerationCancelled", "Other"},
}
UUID_PATTERN = re.compile(r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$")


def default_diagnostics_dir() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    base = Path(local) if local else Path.home() / ".local" / "share"
    return base / "BrainSSD" / "diagnostics"


def _safe_fields(raw: dict[str, Any]) -> dict[str, Any]:
    """Opt-in schema; reject unexpected keys even when their values look safe."""
    clean: dict[str, Any] = {}
    for key, value in raw.items():
        if key in NUMERIC and type(value) in (int, float) and not isinstance(value, bool):
            if -1_000_000_000_000 <= value <= 1_000_000_000_000_000 and (
                not isinstance(value, float) or (value == value and value not in (float("inf"), float("-inf")))
            ):
                clean[key] = round(value, 4) if isinstance(value, float) else value
        elif key in BOOLEAN and type(value) is bool:
            clean[key] = value
        elif key in ENUMS and isinstance(value, str) and value in ENUMS[key]:
            clean[key] = value
        elif key == "request_id" and isinstance(value, str) and UUID_PATTERN.fullmatch(value):
            clean[key] = value
    return clean


def _safe_record(raw: Any) -> dict[str, Any] | None:
    """Export filter protects against malformed or manually edited JSONLs."""
    if not isinstance(raw, dict):
        return None
    name = raw.get("event")
    if name not in EVENTS:
        return None
    stamp = raw.get("timestamp_utc")
    session = raw.get("session_id")
    if not (isinstance(stamp, str)
            and re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?\+00:00", stamp)
            and isinstance(session, str) and UUID_PATTERN.fullmatch(session)):
        return None
    safe = {"schema_version": SCHEMA_VERSION, "timestamp_utc": stamp,
            "session_id": session, "event": name}
    safe.update(_safe_fields(raw))
    return safe


class DiagnosticLogger:
    """Best-effort thread-safe JSONL logger with bounded rotation.

    Logging failures must not stop the local model. Disk write errors are
    counted in memory, not appended with filesystem paths or raw exceptions.
    """

    def __init__(self, directory: Path | None = None, *,
                 session_id: str | None = None,
                 max_bytes: int = MAX_FILE_BYTES, backups: int = MAX_BACKUPS):
        if not 4096 <= max_bytes <= 20_000_000:
            raise ValueError("Invalid rotation limit")
        if not 1 <= backups <= 12:
            raise ValueError("Invalid backup count")
        self.path = (Path(directory) if directory is not None else default_diagnostics_dir()).expanduser().resolve()
        self.path.mkdir(parents=True, exist_ok=True)
        if os.name == "posix":
            self.path.chmod(0o700)
        self.session_id = session_id or str(uuid.uuid4())
        if not UUID_PATTERN.fullmatch(self.session_id):
            raise ValueError("Invalid logger session id")
        self.file = self.path / "events.jsonl"
        self.max_bytes = max_bytes
        self.backups = backups
        self._lock = threading.RLock()
        self.start_monotonic = time.monotonic()
        self.write_errors = 0

    def _rotate(self) -> None:
        # Called while lock held.
        for idx in range(self.backups, 0, -1):
            old = self.path / ("events.jsonl" if idx == 1 else f"events.jsonl.{idx-1}")
            new = self.path / f"events.jsonl.{idx}"
            if old.exists():
                old.replace(new)

    def emit(self, event: str, **fields: Any) -> bool:
        if event not in EVENTS:
            raise ValueError("Unknown diagnostic event")
        record = {
            "schema_version": SCHEMA_VERSION,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "session_id": self.session_id,
            "event": event,
            **_safe_fields(fields),
        }
        encoded = (json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        with self._lock:
            try:
                if self.file.exists() and self.file.stat().st_size + len(encoded) > self.max_bytes:
                    self._rotate()
                fd = os.open(self.file, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
                try:
                    if os.name == "posix":
                        os.fchmod(fd, 0o600)
                    with os.fdopen(fd, "ab", closefd=False) as handle:
                        handle.write(encoded)
                        handle.flush()
                finally:
                    os.close(fd)
                return True
            except OSError:
                self.write_errors += 1
                return False

    def elapsed_ms(self, since: float) -> float:
        return round(max(0.0, (time.monotonic() - since) * 1000), 3)

    def files(self) -> list[Path]:
        # Oldest-to-newest, deterministic. No arbitrary or external files.
        return [p for p in [*(self.path / f"events.jsonl.{i}"
                                for i in range(self.backups, 0, -1)), self.file] if p.is_file()]


def inspect_events(files: Iterable[Path], *, max_events: int = MAX_EXPORT_EVENTS
                   ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not 1 <= max_events <= MAX_EXPORT_EVENTS:
        raise ValueError("Invalid export event limit")
    from collections import deque
    records: Any = deque(maxlen=max_events)
    malformed = 0
    for name in files:
        try:
            with Path(name).open("r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    try:
                        row = _safe_record(json.loads(line))
                    except (ValueError, TypeError):
                        row = None
                    if row is None:
                        malformed += 1
                    else:
                        records.append(row)
        except OSError:
            malformed += 1
    events = list(records)
    counts = Counter(r["event"] for r in events)
    by_suite = Counter(r.get("suite", "") for r in events if r["event"] == "test.result")
    durations = [r["duration_ms"] for r in events
                 if r["event"] in ("inference.done", "chat.complete")
                 and type(r.get("duration_ms")) in (int, float)]
    fails = Counter(r.get("error_type", "Other") for r in events
                    if r["event"] in ("runtime.error", "inference.error", "chat.error", "test.error"))
    metrics: dict[str, Any] = {}
    if durations:
        metrics = {
            "sample_count": len(durations),
            "latency_mean_ms": round(statistics.mean(durations), 2),
            "latency_p50_ms": round(statistics.median(durations), 2),
            "latency_max_ms": round(max(durations), 2),
        }
    report = {
        "schema_version": SCHEMA_VERSION,
        "category": "SANITIZED_DIAGNOSTIC_ONLY",
        "events_retained": len(events), "malformed_or_discarded_lines": malformed,
        "sessions": len(set(e["session_id"] for e in events)),
        "event_counts": dict(sorted(counts.items())),
        "test_suites_with_results": dict(sorted(by_suite.items())),
        "error_types": dict(sorted(fails.items())),
        "latency": metrics,
        "disclaimer": "No prompts or model answers. CI mock tests do not prove real Qwen inference.",
    }
    return events, report


def export_diagnostics(directory: Path, destination: Path, *,
                       max_events: int = MAX_EXPORT_EVENTS) -> dict[str, Any]:
    """Only sanitized, size-bounded events and aggregate summary go into ZIP."""
    logger_files = [p for p in [*(Path(directory) / f"events.jsonl.{i}"
                                      for i in range(MAX_BACKUPS, 0, -1)),
                                     Path(directory) / "events.jsonl"] if p.is_file()]
    events, report = inspect_events(logger_files, max_events=max_events)
    destination = Path(destination).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("summary.json", json.dumps(report, ensure_ascii=False, indent=2))
        archive.writestr("events.jsonl", "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in events))
        archive.writestr("LEIA-ME.txt",
            "Brain-SSD: relatório anonimizado por campos permitidos.\n"
            "Sem perguntas, respostas, memórias, caminhos ou rastros de erro.\n"
            "Revise o ZIP antes de compartilhar. Logs locais podem conter IDs aleatórios.\n"
            "Não há envio automático ao GitHub ou à OpenAI.\n")
    return report
