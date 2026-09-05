from __future__ import annotations

import hashlib
import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from brain_ssd.backend import GenerationRequest
from brain_ssd.local_runtime.backend import LocalLlamaCppBackend, probe_llama, resolve_llama_executable
from brain_ssd.local_runtime.capabilities import EnvironmentCapabilities
from brain_ssd.local_runtime.core_backend import (
    CORE_MODES,
    PERSISTENT_CORE,
    PersistentCoreBackend,
    SubprocessPerQueryCore,
    generation_configuration,
    resolve_server_executable,
)
from brain_ssd.local_runtime.pipeline_support import run_measured
from brain_ssd.local_runtime.windows_metrics import windows_process_snapshot
from brain_ssd.observability.events import BrainEvent, EventStatus
from brain_ssd.real_knowledge import PAGE_SIZE, sha256_bytes
from brain_ssd.record_retrieval import ContextBuilder, RealKnowledgeIndex, build_prompt, retrieve
from brain_ssd.storage import MMapStorageBackend, touch_view


MODEL_RELATIVE = Path("models/Qwen3-0.6B-Q8_0.gguf")
MANIFEST_RELATIVE = Path("brain_data/real_knowledge/semantic/manifest.json")
INDEX_RELATIVE = Path("brain_data/real_knowledge/index/record-index.json.gz")
QA_RELATIVE = Path("benchmarks/data/phase4d_real_qa.json")
RESULTS_RELATIVE = Path("results/windows_native")
DEVELOPMENT_STATUS = "EXPERIMENTAL_FUNCTIONAL_RUNTIME"


def clean_answer(stdout: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", stdout, flags=re.DOTALL).strip()
    text = text.removesuffix(">").strip()
    return text.removesuffix("[end of text]").strip()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)
    return path


def _extract_from_page(page: Any, record: dict[str, Any]) -> dict[str, Any]:
    start = record["offset"]
    payload = bytes(page.data[start:start + record["length"]])
    if sha256_bytes(payload) != record["checksum"]:
        raise ValueError(f"record checksum mismatch: {record['record_id']}")
    extracted = dict(record)
    extracted["text"] = payload.decode("utf-8")
    return extracted


def _run_measured(command: list[str] | tuple[str, ...], on_first_output: Callable[[], None] | None = None) -> dict[str, Any]:
    return run_measured(command, on_first_output=on_first_output)


class LocalBrainSSD:
    """Functional local orchestration; all cognitive algorithms remain frozen imports."""

    def __init__(
        self,
        root: Path,
        *,
        executable: Path | None = None,
        threads: int = 4,
        core_mode: str = "subprocess",
        persistent_executable: Path | None = None,
        persistent_port: int | None = None,
        ready_timeout_s: float = 90.0,
    ) -> None:
        self.root = root.resolve()
        self.model_path = self.root / MODEL_RELATIVE
        self.manifest_path = self.root / MANIFEST_RELATIVE
        self.index_path = self.root / INDEX_RELATIVE
        self.qa_path = self.root / QA_RELATIVE
        normalized_mode = core_mode.casefold().replace("-", "_")
        if normalized_mode not in CORE_MODES:
            raise ValueError(f"unknown core mode: {core_mode}")
        self.core_mode = CORE_MODES[normalized_mode]
        self.results_dir = self.root / (Path("results/windows_core_runtime/manual") if self.core_mode == PERSISTENT_CORE else RESULTS_RELATIVE)
        self.capabilities = EnvironmentCapabilities.detect(self.root)
        self.executable = resolve_llama_executable(self.root, executable)
        self.backend = LocalLlamaCppBackend(self.executable, self.model_path, threads=threads, context_size=4096)
        if not self.model_path.is_file():
            raise FileNotFoundError(f"GGUF model not found: {self.model_path}")
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        self.manifest = manifest
        self.records_by_id = {record["record_id"]: record for record in manifest["records"]}
        self.index = RealKnowledgeIndex.load(self.index_path, manifest["records"])
        self.storage = MMapStorageBackend(self.manifest_path)
        self.storage.open_brain()
        if self.core_mode == PERSISTENT_CORE:
            server_executable = resolve_server_executable(self.root, persistent_executable)
            self.core_backend = PersistentCoreBackend(
                server_executable, self.model_path, threads=threads, context_size=4096,
                port=persistent_port, ready_timeout_s=ready_timeout_s,
            )
        else:
            self.core_backend = SubprocessPerQueryCore(self.executable, self.model_path, threads=threads, context_size=4096)
        self._closed = False

    def close(self) -> None:
        if not self._closed:
            try:
                self.core_backend.close()
            finally:
                self.storage.close_brain()
                self._closed = True

    def __enter__(self) -> "LocalBrainSSD":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def startup_audit(self) -> dict[str, Any]:
        model_sha256 = file_sha256(self.model_path)
        runtime = probe_llama(self.executable)
        audit = {
            "schema_version": 1,
            "generated_at": time.time(),
            "development_status": DEVELOPMENT_STATUS,
            **self.capabilities.to_dict(),
            "model": {
                "path": str(self.model_path),
                "bytes": self.model_path.stat().st_size,
                "sha256": model_sha256,
            },
            "runtime": runtime,
            "core_backend": {
                "mode": self.core_mode,
                "name": self.core_backend.name,
                "runtime": str(self.core_backend.runtime_path),
                "experimental_runtime": self.core_mode == PERSISTENT_CORE,
            },
            "brain": {
                "manifest": str(self.manifest_path),
                "index": str(self.index_path),
                "corpus_bytes": self.manifest["corpus_size_bytes"],
                "page_size_bytes": self.manifest["page_size_bytes"],
                "page_count": self.manifest["page_count"],
                "record_count": len(self.records_by_id),
            },
        }
        atomic_write_json(self.results_dir / "startup-audit.json", audit)
        return audit

    def storage_smoke(self) -> dict[str, Any]:
        before = self.storage.stats()
        page = self.storage.get_page(0, validate="first")
        try:
            sink = touch_view(page.data)
        finally:
            self.storage.release_page(page)
        after = self.storage.stats()
        return {
            "status": "PASS" if after["checksum_errors"] == 0 else "FAIL",
            "page_id": 0,
            "logical_bytes": after["logical_bytes_requested"] - before["logical_bytes_requested"],
            "checksum_errors": after["checksum_errors"] - before["checksum_errors"],
            "sink": sink,
        }

    def retrieve(self, query: str, *, emit: Callable[[BrainEvent], Any] | None = None, run_id: str = "", query_id: str = "") -> dict[str, Any]:
        publish = emit or (lambda event: event)
        common = {"run_id": run_id, "query_id": query_id}
        publish(BrainEvent("ROUTER_STARTED", "ROUTER", EventStatus.RUNNING, **common))
        route_started = time.perf_counter_ns()
        result = retrieve(
            self.index,
            query,
            self.records_by_id,
            mode="brain",
            max_records=8,
            max_pages=4,
            threshold=0.20,
        )
        routed = time.perf_counter_ns()
        candidates = [
            {
                "record_id": candidate.record_id,
                "score": candidate.score,
                "lexical_score": candidate.lexical_score,
                "tfidf_score": candidate.tfidf_score,
                "matched_terms": list(candidate.matched_terms),
                "query_coverage": candidate.query_coverage,
            }
            for candidate in result.candidates[:8]
        ]
        routing_ms = (routed - route_started) / 1e6
        publish(BrainEvent("ROUTER_CANDIDATES", "ROUTER", payload_summary={"candidates": candidates}, **common))
        publish(BrainEvent("ROUTER_COMPLETED", "ROUTER", EventStatus.SUCCESS, duration_ms=routing_ms, metrics={"candidate_count": len(result.candidates)}, **common))

        publish(BrainEvent("GATE_STARTED", "GATE", EventStatus.RUNNING, **common))
        for page_id in result.activated_pages:
            page_record = next(record for record in result.records if record["page_id"] == page_id)
            publish(BrainEvent(
                "PAGE_ACTIVATED",
                "BRAIN",
                EventStatus.SUCCESS,
                payload_summary={
                    "page_id": page_id,
                    "domain": page_record.get("domain", "knowledge"),
                    "topic": page_record.get("section", "Relevant knowledge"),
                    "reasons": ["frozen Phase 4D retrieval selected this page"],
                },
                **common,
            ))
        publish(BrainEvent(
            "GATE_COMPLETED",
            "GATE",
            EventStatus.SUCCESS if result.status == "OK" else EventStatus.SKIPPED,
            metrics={
                "active_brain_bytes": len(result.activated_pages) * PAGE_SIZE,
                "total_brain_bytes": self.manifest["corpus_size_bytes"],
                "active_pages": len(result.activated_pages),
                "total_pages": self.manifest["page_count"],
            },
            payload_summary={"retrieval_status": result.status, "measurement": "combined_with_frozen_retrieve"},
            **common,
        ))

        before_stats = self.storage.stats()
        process_before = windows_process_snapshot(os.getpid()) if os.name == "nt" else None
        storage_started = time.perf_counter_ns()
        publish(BrainEvent("STORAGE_READ_STARTED", "BRAIN", EventStatus.RUNNING, **common))
        extracted: list[dict[str, Any]] = []
        sink = 0
        for page_id in result.activated_pages:
            page = self.storage.get_page(page_id, validate="first")
            try:
                sink ^= touch_view(page.data)
                for record in result.records:
                    if record["page_id"] == page_id:
                        extracted.append(_extract_from_page(page, record))
            finally:
                self.storage.release_page(page)
        storage_finished = time.perf_counter_ns()
        process_after = windows_process_snapshot(os.getpid()) if os.name == "nt" else None
        after_stats = self.storage.stats()
        logical_bytes = after_stats["logical_bytes_requested"] - before_stats["logical_bytes_requested"]
        process_read_transfer = None
        if process_before and process_after and process_before.read_transfer_bytes is not None and process_after.read_transfer_bytes is not None:
            process_read_transfer = max(0, process_after.read_transfer_bytes - process_before.read_transfer_bytes)
        storage_ms = (storage_finished - storage_started) / 1e6
        publish(BrainEvent(
            "STORAGE_READ_COMPLETED",
            "BRAIN",
            EventStatus.SUCCESS,
            duration_ms=storage_ms,
            metrics={
                "logical_bytes": logical_bytes,
                "physical_bytes": None,
                "cache_state": "NOT_MEASURED",
                "process_read_transfer_bytes": process_read_transfer,
            },
            **common,
        ))
        for record in extracted:
            candidate = next((item for item in candidates if item["record_id"] == record["record_id"]), None)
            publish(BrainEvent(
                "KNOWLEDGE_RECORD_SELECTED",
                "BRAIN",
                EventStatus.SUCCESS,
                payload_summary={
                    "record_id": record["record_id"],
                    "source": record.get("source_id", "unknown"),
                    "section": record.get("section", "KnowledgeRecord"),
                    "excerpt": " ".join(record["text"].split())[:280],
                    "score": candidate["score"] if candidate else None,
                },
                **common,
            ))

        publish(BrainEvent("CONTEXT_BUILD_STARTED", "CONTEXT", EventStatus.RUNNING, **common))
        context_started = time.perf_counter_ns()
        context = ContextBuilder(2048).build(extracted)
        context_finished = time.perf_counter_ns()
        context_ms = (context_finished - context_started) / 1e6
        publish(BrainEvent(
            "CONTEXT_BUILD_COMPLETED",
            "CONTEXT",
            EventStatus.SUCCESS,
            duration_ms=context_ms,
            metrics={
                "tokens": context["estimated_tokens"],
                "token_budget": 2048,
                "bytes": context["bytes"],
                "records_used": len(context["source_ids"]),
                "records_discarded": max(0, len(extracted) - len(context["source_ids"])),
                "records_retrieved": len(extracted),
            },
            **common,
        ))
        retrieval_total_ms = (context_finished - route_started) / 1e6
        sources = [
            {
                "record_id": record["record_id"],
                "source_id": record.get("source_id"),
                "document": record.get("document"),
                "section": record.get("section"),
                "page_id": record["page_id"],
                "excerpt": " ".join(record["text"].split())[:280],
            }
            for record in extracted
            if record["record_id"] in context["source_ids"]
        ]
        return {
            "status": result.status,
            "record_ids": sorted(record["record_id"] for record in result.records),
            "activated_pages": list(result.activated_pages),
            "active_brain_bytes": len(result.activated_pages) * PAGE_SIZE,
            "selected_record_bytes": sum(record["length"] for record in result.records),
            "candidates": candidates,
            "context": context,
            "sources": sources,
            "timing_ms": {
                "routing_and_gate": routing_ms,
                "gate_separate": None,
                "storage": storage_ms,
                "context_build": context_ms,
                "retrieval_total": retrieval_total_ms,
            },
            "timing_semantics": {
                "gate_separate": "NOT_MEASURED: frozen retrieve() returns routing and gate selection together.",
            },
            "storage": {
                "logical_page_bytes": logical_bytes,
                "process_read_transfer_bytes": process_read_transfer,
                "physical_read_bytes": None,
                "physical_read_semantics": "NOT_MEASURED on Windows; process transfer counters are not physical SSD reads.",
                "checksum_errors": after_stats["checksum_errors"] - before_stats["checksum_errors"],
                "sink": sink,
            },
        }

    def answer(self, query: str, *, hud_runtime: Any | None = None, persist: bool = True) -> dict[str, Any]:
        if not query.strip():
            raise ValueError("query cannot be empty")
        run_id = f"win-{uuid.uuid4().hex[:12]}"
        query_id = uuid.uuid4().hex[:12]
        emit = hud_runtime.emit if hud_runtime else None
        publish = emit or (lambda event: event)
        common = {"run_id": run_id, "query_id": query_id}
        run_started = time.perf_counter_ns()
        publish(BrainEvent("QUERY_RECEIVED", "INPUT", EventStatus.SUCCESS, payload_summary={"query": query}, **common))
        try:
            retrieval = self.retrieve(query, emit=emit, run_id=run_id, query_id=query_id)
            prompt = build_prompt(query, retrieval["context"])
            configuration = generation_configuration(threads=self.backend.threads, context_size=self.backend.context_size, max_tokens=96, temperature=0.0)
            configuration_hash = hashlib.sha256(json.dumps(configuration, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
            context_hash = hashlib.sha256(retrieval["context"]["text"].encode("utf-8")).hexdigest()
            publish(BrainEvent("CORE_STARTED", "CORE", EventStatus.RUNNING, metrics={"model": self.model_path.name, "mode": self.core_mode}, **common))
            publish(BrainEvent("CORE_PROMPT_PROCESSING", "CORE", EventStatus.RUNNING, metrics={"input_tokens": retrieval["context"]["estimated_tokens"]}, **common))
            generating_sent = False

            def first_output() -> None:
                nonlocal generating_sent
                if not generating_sent:
                    generating_sent = True
                    publish(BrainEvent("CORE_GENERATING", "CORE", EventStatus.RUNNING, **common))

            lifecycle_status = {
                "CORE_READY": EventStatus.SUCCESS,
                "CORE_REQUEST_COMPLETED": EventStatus.SUCCESS,
                "CORE_SHUTDOWN": EventStatus.SUCCESS,
            }

            def core_event(event_type: str, metrics: dict[str, Any]) -> None:
                publish(BrainEvent(event_type, "CORE", lifecycle_status.get(event_type, EventStatus.RUNNING), metrics=metrics, **common))

            measured = self.core_backend.generate(
                GenerationRequest(prompt=prompt, max_tokens=96, temperature=0.0),
                on_first_output=first_output,
                on_event=core_event,
            )
            answer = clean_answer(str(measured["stdout"]))
            metrics = dict(measured["metrics"])
            if measured["return_code"] != 0:
                raise RuntimeError(f"llama.cpp exited with code {measured['return_code']}: {str(measured['stderr'])[-1200:]}")
            if not answer:
                raise RuntimeError("llama.cpp returned an empty answer")
            core_metrics = {
                "model": "Qwen3-0.6B Q8_0",
                "mode": "CPU ONLY",
                "ttft_ms": metrics.get("ttft_ms"),
                "tokens_per_second": metrics.get("tokens_per_second"),
                "input_tokens": metrics.get("prompt_tokens") or retrieval["context"]["estimated_tokens"],
                "output_tokens": metrics.get("generated_tokens"),
                "total_latency_ms": metrics.get("latency_ms"),
                "cpu_average_percent": metrics.get("cpu_percent_total_average"),
                "cpu_peak_percent": metrics.get("cpu_percent_total_peak"),
                "ram_bytes": metrics.get("working_set_bytes_max") or metrics.get("rss_bytes_max"),
                "working_set_peak_bytes": metrics.get("working_set_bytes_max") or metrics.get("rss_bytes_max"),
                "private_bytes": metrics.get("private_bytes_max"),
                "available_system_ram_bytes": metrics.get("system_available_ram_bytes_min"),
                "pss_bytes": None,
                "threads_used": metrics.get("thread_count_max"),
                "threads_total": os.cpu_count(),
                "temperature_c": None,
            }
            publish(BrainEvent("CORE_COMPLETED", "CORE", EventStatus.SUCCESS, duration_ms=metrics.get("latency_ms"), metrics=core_metrics, **common))
            total_ms = (time.perf_counter_ns() - run_started) / 1e6
            publish(BrainEvent("ANSWER_READY", "ANSWER", EventStatus.SUCCESS, duration_ms=total_ms, payload_summary={"answer": answer}, metrics={"quality_status": "NOT_SCORED"}, **common))

            stages = {
                "routing_and_gate": retrieval["timing_ms"]["routing_and_gate"],
                "storage": retrieval["timing_ms"]["storage"],
                "context_build": retrieval["timing_ms"]["context_build"],
                "qwen_core": metrics.get("latency_ms"),
            }
            measured_stages = {key: value for key, value in stages.items() if isinstance(value, (int, float))}
            bottleneck_name = max(measured_stages, key=measured_stages.get) if measured_stages else "NOT_MEASURED"
            safe_retrieval = dict(retrieval)
            safe_retrieval["context"] = {key: value for key, value in retrieval["context"].items() if key != "text"}
            result = {
                "schema_version": 1,
                "generated_at": time.time(),
                "run_id": run_id,
                "query_id": query_id,
                "environment_type": self.capabilities.environment_type,
                "development_status": DEVELOPMENT_STATUS,
                "phase4e_valid": False,
                "phase4e_invalid_reason": self.capabilities.phase4e_invalid_reason,
                "canonical_baseline": False,
                "query": query,
                "answer": answer,
                "retrieval": safe_retrieval,
                "generation": {
                    "backend": self.core_backend.name,
                    "core_mode": self.core_mode,
                    "executable": str(self.core_backend.runtime_path),
                    "model": str(self.model_path),
                    "configuration": configuration,
                    "configuration_hash": configuration_hash,
                    "return_code": measured["return_code"],
                    "metrics": metrics,
                    "measurement_semantics": measured.get("measurement_semantics", {}),
                    "runtime_report": measured.get("runtime_report", {}),
                    "stderr_sha256": hashlib.sha256(str(measured["stderr"]).encode("utf-8")).hexdigest(),
                },
                "timing_ms": {**stages, "total": total_ms},
                "context_sha256": context_hash,
                "bottleneck": {"component": bottleneck_name, "duration_ms": measured_stages.get(bottleneck_name)},
                "capability_status": {key: value.status for key, value in self.capabilities.capabilities.items()},
            }
            if persist:
                filename = f"run-{time.strftime('%Y%m%d-%H%M%S')}-{query_id}.json"
                atomic_write_json(self.results_dir / filename, result)
            return result
        except BaseException as error:
            publish(BrainEvent("ERROR", "SYSTEM", EventStatus.ERROR, payload_summary={"message": str(error)}, **common))
            raise

    def qwen_smoke(self) -> dict[str, Any]:
        prompt = "Reply with exactly OK and nothing else.\n/no_think"
        measured = self.core_backend.generate(GenerationRequest(prompt=prompt, max_tokens=16, temperature=0.0))
        answer = clean_answer(str(measured["stdout"]))
        return {
            "status": "PASS" if measured["return_code"] == 0 and bool(answer) else "FAIL",
            "return_code": measured["return_code"],
            "answer": answer,
            "latency_ms": measured["metrics"].get("latency_ms"),
            "working_set_bytes_max": measured["metrics"].get("working_set_bytes_max") or measured["metrics"].get("rss_bytes_max"),
            "tokens_per_second": measured["metrics"].get("tokens_per_second"),
            "stderr_sha256": hashlib.sha256(str(measured["stderr"]).encode("utf-8")).hexdigest(),
        }

    def retrieval_smoke(self) -> dict[str, Any]:
        query = "Why can repeated json.dump calls create invalid JSON?"
        result = self.retrieve(query)
        return {
            "status": "PASS" if result["status"] == "OK" and bool(result["record_ids"]) and result["storage"]["checksum_errors"] == 0 else "FAIL",
            "query": query,
            "retrieval_status": result["status"],
            "record_ids": result["record_ids"],
            "activated_pages": result["activated_pages"],
            "logical_page_bytes": result["storage"]["logical_page_bytes"],
            "checksum_errors": result["storage"]["checksum_errors"],
        }

    def run_smoke_suite(self) -> dict[str, Any]:
        tests = {
            "storage_mmap": self.storage_smoke(),
            "real_retrieval": self.retrieval_smoke(),
            "qwen_cpu": self.qwen_smoke(),
        }
        payload = {
            "schema_version": 1,
            "generated_at": time.time(),
            "environment_type": self.capabilities.environment_type,
            "development_status": DEVELOPMENT_STATUS,
            "phase4e_valid": False,
            "phase4e_invalid_reason": self.capabilities.phase4e_invalid_reason,
            "status": "PASS" if all(test["status"] == "PASS" for test in tests.values()) else "FAIL",
            "tests": tests,
        }
        atomic_write_json(self.results_dir / "smoke-tests.json", payload)
        return payload
