from __future__ import annotations

import io
import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brain_ssd.backend import GenerationRequest
from brain_ssd.hud.state import HudStateStore
from brain_ssd.local_runtime.core_backend import (
    PERSISTENT_CORE,
    SUBPROCESS_PER_QUERY,
    PersistentCoreBackend,
    generation_configuration,
    resolve_server_executable,
)
from brain_ssd.local_runtime.pipeline import LocalBrainSSD
from brain_ssd.local_runtime.windows_core_experiment import EXPERIMENT, HYPOTHESIS, _memory_stability
from brain_ssd.observability.events import BrainEvent


class FakeProcess:
    def __init__(self) -> None:
        self.pid = os.getpid()
        self.returncode = None
        self.stdout = io.StringIO("")
        self.stderr = io.StringIO("")
        self.terminated = False
        self.killed = False

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self.terminated = True
        self.returncode = 0

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9

    def wait(self, timeout: float | None = None) -> int:
        return int(self.returncode or 0)


class FakeResponse:
    def __init__(self, body: bytes = b"", lines: list[bytes] | None = None) -> None:
        self.body = body
        self.lines = lines or []

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.body

    def __iter__(self):
        return iter(self.lines)


def _backend(tmp_path: Path, urlopen: Any, process: FakeProcess | None = None, timeout: float = 0.1) -> tuple[PersistentCoreBackend, FakeProcess]:
    executable = tmp_path / "llama-server.exe"
    model = tmp_path / "model.gguf"
    executable.write_bytes(b"MZ")
    model.write_bytes(b"GGUF")
    fake = process or FakeProcess()
    backend = PersistentCoreBackend(
        executable, model, port=49123, ready_timeout_s=timeout,
        process_factory=lambda *args, **kwargs: fake, urlopen=urlopen,
    )
    return backend, fake


def test_persistent_command_is_loopback_cpu_only_and_baseline_default_is_separate(tmp_path: Path) -> None:
    backend, _ = _backend(tmp_path, lambda *args, **kwargs: FakeResponse(b'{"status":"ok"}'))
    command = list(backend.command())
    assert command[command.index("--host") + 1] == "127.0.0.1"
    assert command[command.index("--device") + 1] == "none"
    assert command[command.index("--threads") + 1] == "4"
    assert command[command.index("--ctx-size") + 1] == "4096"
    assert "--no-warmup" in command and "--no-webui" in command
    assert command[command.index("--parallel") + 1] == "1"
    assert command[command.index("--cache-ram") + 1] == "0"
    assert "--no-cache-idle-slots" in command
    assert SUBPROCESS_PER_QUERY != PERSISTENT_CORE


def test_persistent_lifecycle_readiness_request_reuse_events_and_shutdown(tmp_path: Path) -> None:
    requests: list[dict[str, Any]] = []

    def urlopen(request: Any, timeout: float) -> FakeResponse:
        if request.full_url.endswith("/health"):
            return FakeResponse(b'{"status":"ok"}')
        payload = json.loads(request.data)
        requests.append(payload)
        events = [
            b'data: {"choices":[{"delta":{"content":"NO_"},"finish_reason":null}]}\n',
            b'data: {"choices":[{"delta":{"content":"KNOWLEDGE"},"finish_reason":"stop"}],"timings":{"prompt_n":5,"prompt_ms":10,"prompt_per_second":500,"predicted_n":2,"predicted_ms":20,"predicted_per_second":100}}\n',
            b'data: [DONE]\n',
        ]
        return FakeResponse(lines=events)

    backend, process = _backend(tmp_path, urlopen)
    events: list[str] = []
    callback = lambda name, metrics: events.append(name)
    first = backend.generate(GenerationRequest("known", max_tokens=8), on_event=callback)
    second = backend.generate(GenerationRequest("unknown", max_tokens=8), on_event=callback)
    backend.close()
    assert first["stdout"] == "NO_KNOWLEDGE"
    assert second["metrics"]["model_loads"] == 1
    assert second["metrics"]["queries_served"] == 2
    assert second["metrics"]["reloads_avoided"] == 1
    assert second["metrics"]["core_reuse_ratio"] == 2.0
    assert all(payload["cache_prompt"] is False for payload in requests)
    assert requests[0]["messages"][0]["content"] == "known" and requests[1]["messages"][0]["content"] == "unknown"
    for expected in ("CORE_PROCESS_STARTING", "CORE_MODEL_LOADING", "CORE_READY", "CORE_REQUEST_STARTED", "CORE_REQUEST_COMPLETED", "CORE_REUSED", "CORE_SHUTDOWN"):
        assert expected in events
    assert process.terminated and backend.process is None and not backend.ready


def test_readiness_timeout_is_visible_and_cleans_process(tmp_path: Path) -> None:
    backend, process = _backend(tmp_path, lambda *args, **kwargs: (_ for _ in ()).throw(OSError("not ready")), timeout=0.01)
    with pytest.raises(TimeoutError):
        backend.start()
    assert process.terminated
    assert backend.process is None


def test_keyboard_interrupt_cleanup_via_context_owner(tmp_path: Path) -> None:
    backend, process = _backend(tmp_path, lambda *args, **kwargs: FakeResponse(b'{"status":"ok"}'))
    backend.start()
    backend._stream_completion = lambda *args, **kwargs: (_ for _ in ()).throw(KeyboardInterrupt())  # type: ignore[method-assign]
    try:
        with pytest.raises(KeyboardInterrupt):
            backend.generate(GenerationRequest("interrupt"))
    finally:
        backend.close()
    assert process.terminated and backend.process is None


def test_generation_configuration_and_context_are_backend_independent() -> None:
    left = generation_configuration(threads=4, context_size=4096, max_tokens=96, temperature=0.0)
    right = generation_configuration(threads=4, context_size=4096, max_tokens=96, temperature=0.0)
    assert left == right
    with LocalBrainSSD(ROOT) as runtime:
        first = runtime.retrieve("Why can repeated json.dump calls create invalid JSON?")
        second = runtime.retrieve("Why can repeated json.dump calls create invalid JSON?")
        unknown = runtime.retrieve("What is the exact cache size of the Python OrionDB driver?")
    assert first["record_ids"] == second["record_ids"]
    assert first["activated_pages"] == second["activated_pages"]
    assert first["context"]["text"] == second["context"]["text"]
    assert unknown["status"] == "NO_KNOWLEDGE" and unknown["context"]["text"] == ""


def test_hud_projects_core_residency_without_changing_active_brain() -> None:
    store = HudStateStore()
    store.apply(BrainEvent("GATE_COMPLETED", "GATE", "SUCCESS", metrics={"active_brain_bytes": 2 * 1024**2, "total_brain_bytes": 64 * 1024**2, "active_pages": 2, "total_pages": 64}))
    store.apply(BrainEvent("CORE_READY", "CORE", "SUCCESS", metrics={"model_loads": 1, "persistent_core_ready_ms": 2200}))
    store.apply(BrainEvent("CORE_REQUEST_COMPLETED", "CORE", "SUCCESS", metrics={"core_mode": PERSISTENT_CORE, "model_loads": 1, "queries_served": 10, "reloads_avoided": 9, "core_reuse_ratio": 10.0}))
    state = store.snapshot()
    assert state["core"]["residency"] == "RESIDENT"
    assert state["core"]["model_loads"] == 1
    assert state["core"]["reloads_avoided"] == 9
    assert state["brain"]["active_bytes"] == 2 * 1024**2


def test_result_schema_and_memory_classification_are_honest() -> None:
    audit_files = sorted((ROOT / "results/windows_core_runtime/audit").glob("*.json"))
    assert audit_files
    payload = json.loads(audit_files[-1].read_text(encoding="utf-8"))
    assert payload["experiment"] == EXPERIMENT
    assert payload["hypothesis"] == HYPOTHESIS
    assert payload["phase4e_valid"] is False
    assert payload["phase4ew_modified"] is False
    assert _memory_stability([])["classification"] == "STABLE"


def test_experimental_server_resolution_never_returns_baseline_completion() -> None:
    server = resolve_server_executable(ROOT)
    assert server.name == "llama-server.exe"
    assert "build-win-persistent" in server.as_posix()
    assert server != ROOT / "third_party/llama.cpp/build-win/bin/llama-completion.exe"
