from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import statistics
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Iterable

from brain_ssd.backend import GenerationRequest
from brain_ssd.hud.state import HudRuntime
from brain_ssd.local_runtime.backend import FROZEN_LLAMA_COMMIT, resolve_llama_executable
from brain_ssd.local_runtime.core_backend import (
    PERSISTENT_CORE,
    SUBPROCESS_PER_QUERY,
    PersistentCoreBackend,
    SubprocessPerQueryCore,
    generation_configuration,
    resolve_server_executable,
)
from brain_ssd.local_runtime.phase4ew import _score_answer, _stats
from brain_ssd.local_runtime.pipeline import LocalBrainSSD, clean_answer, file_sha256


EXPERIMENT = "WINDOWS_CORE_RUNTIME_EXPERIMENT"
EXPERIMENT_ALIAS = "WCRE-1"
HYPOTHESIS = "ENG-CORE-001"
RESULTS_RELATIVE = Path("results/windows_core_runtime")
MODEL_RELATIVE = Path("models/Qwen3-0.6B-Q8_0.gguf")
QA_RELATIVE = Path("benchmarks/data/phase4d_real_qa.json")
PHASE4E_INVALID_REASON = "Phase 4E canonical physical baseline requires Debian/Linux native environment."


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _run_id(prefix: str) -> str:
    return f"{prefix}-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-{uuid.uuid4().hex[:10]}"


def _sha256_json(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _tree_digest(root: Path) -> dict[str, Any]:
    if not root.is_dir():
        return {"exists": False, "files": 0, "sha256": None}
    entries = []
    for path in sorted((item for item in root.rglob("*") if item.is_file()), key=lambda item: item.as_posix()):
        entries.append({"path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size, "sha256": file_sha256(path)})
    return {"exists": True, "files": len(entries), "sha256": _sha256_json(entries)}


def _exclusive_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
    return path


def _atomic_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)
    return path


def _process_count(name: str) -> int | None:
    if os.name != "nt":
        return None
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", f"@((Get-Process -Name '{name}' -ErrorAction SilentlyContinue)).Count"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
    )
    try:
        return int(result.stdout.strip())
    except ValueError:
        return None


def _memory_stability(runs: list[dict[str, Any]]) -> dict[str, Any]:
    metrics = [run.get("generation", {}).get("metrics", run.get("metrics", {})) for run in runs if run.get("status") == "PASS"]
    ws = [item.get("working_set_bytes_max") for item in metrics if isinstance(item.get("working_set_bytes_max"), (int, float))]
    private = [item.get("private_bytes_max") for item in metrics if isinstance(item.get("private_bytes_max"), (int, float))]
    handles = [item.get("handle_count_max") for item in metrics if isinstance(item.get("handle_count_max"), (int, float))]
    threads = [item.get("thread_count_max") for item in metrics if isinstance(item.get("thread_count_max"), (int, float))]
    ws_growth = ws[-1] - ws[0] if len(ws) >= 2 else None
    private_growth = private[-1] - private[0] if len(private) >= 2 else None
    handle_growth = handles[-1] - handles[0] if len(handles) >= 2 else None
    thread_growth = threads[-1] - threads[0] if len(threads) >= 2 else None
    unbounded = bool(
        (isinstance(ws_growth, (int, float)) and ws_growth > 256 * 1024**2)
        or (isinstance(private_growth, (int, float)) and private_growth > 256 * 1024**2)
        or (isinstance(handle_growth, (int, float)) and handle_growth > 32)
        or (isinstance(thread_growth, (int, float)) and thread_growth > 8)
    )
    growth = any(isinstance(value, (int, float)) and value > 32 * 1024**2 for value in (ws_growth, private_growth))
    classification = "UNBOUNDED_GROWTH" if unbounded else "STABLE_WITH_GROWTH" if growth else "STABLE"
    return {
        "classification": classification,
        "working_set_bytes": _stats(ws),
        "private_bytes": _stats(private),
        "working_set_growth_bytes": ws_growth,
        "private_bytes_growth_bytes": private_growth,
        "handles": _stats(handles),
        "handle_growth": handle_growth,
        "threads": _stats(threads),
        "thread_growth": thread_growth,
    }


def _result_row(result: dict[str, Any], query_spec: dict[str, Any], index: int) -> dict[str, Any]:
    quality = _score_answer(result["answer"], query_spec, result["retrieval"]["record_ids"])
    return {
        "index": index,
        "query_spec": query_spec,
        "status": "PASS",
        "answer": result["answer"],
        "answer_status": "NO_KNOWLEDGE" if "no_knowledge" in result["answer"].casefold() else "ANSWER",
        "quality": quality,
        "retrieval": result["retrieval"],
        "context_sha256": result["context_sha256"],
        "generation": result["generation"],
        "timing_ms": result["timing_ms"],
        "bottleneck": result["bottleneck"],
    }


class WindowsCoreRuntimeExperiment:
    def __init__(self, root: Path, *, quick: bool = False, duration_minutes: float | None = None) -> None:
        self.root = root.resolve()
        self.results = self.root / RESULTS_RELATIVE
        self.quick = quick
        self.duration_minutes = duration_minutes if duration_minutes is not None else (0.5 if quick else 20.0)
        self.model = self.root / MODEL_RELATIVE
        self.completion = resolve_llama_executable(self.root)
        self.server = resolve_server_executable(self.root)
        qa = json.loads((self.root / QA_RELATIVE).read_text(encoding="utf-8"))["queries"]
        self.qa = {query["query_id"]: query for query in qa}
        self.queries = [self.qa[name] for name in (
            "holdout_json_frames", "dev_sql_params", "holdout_python_sqlite",
            "holdout_eager_paraphrase", "holdout_unknown_near",
        )]
        self.phase4ew_before = _tree_digest(self.root / "results/phase4ew")
        self.identity = {
            "git_commit": self._git_commit(),
            "llama_cpp_commit": FROZEN_LLAMA_COMMIT,
            "model_bytes": self.model.stat().st_size,
            "model_sha256": file_sha256(self.model),
            "subprocess_runtime": {"path": str(self.completion), "bytes": self.completion.stat().st_size, "sha256": file_sha256(self.completion)},
            "persistent_runtime": {"path": str(self.server), "bytes": self.server.stat().st_size, "sha256": file_sha256(self.server), "experimental_runtime": True},
        }

    def _git_commit(self) -> str | None:
        result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.root, capture_output=True, text=True, encoding="utf-8", errors="replace")
        return result.stdout.strip() or None

    def _base(self, mode: str, run_id: str, matrix_id: str | None) -> dict[str, Any]:
        configuration = {
            "mode": mode,
            "quick": self.quick,
            "duration_minutes": self.duration_minutes if mode == "sustained" else None,
            **generation_configuration(threads=4, context_size=4096, max_tokens=96, temperature=0.0),
        }
        return {
            "schema_version": 1,
            "experiment": EXPERIMENT,
            "experiment_alias": EXPERIMENT_ALIAS,
            "hypothesis": HYPOTHESIS,
            "hypothesis_status": "UNTESTED",
            "phase4e_valid": False,
            "phase4e_invalid_reason": PHASE4E_INVALID_REASON,
            "phase4ew_modified": False,
            "phase4f_started": False,
            "phase5_or_prefetch_started": False,
            "standard_rag": "NOT_RUN",
            "mode": mode,
            "run_id": run_id,
            "matrix_id": matrix_id,
            "timestamp_utc": _utc_now(),
            "identity": self.identity,
            "configuration": configuration,
            "config_hash": _sha256_json(configuration),
        }

    def _write(self, category: str, payload: dict[str, Any]) -> Path:
        path = self.results / category / f"{payload['run_id']}.json"
        _exclusive_json(path, payload)
        payload["artifact"] = {"path": str(path), "sha256": file_sha256(path)}
        return path

    def _core_prompt(self, prompt_class: str) -> str:
        if prompt_class == "tiny":
            return "Responda apenas: AZUL\n/no_think"
        if prompt_class == "short":
            return "Answer concisely: what is the capital of France?\n/no_think"
        context = ("Measurement context: a compact CPU runtime loads a local model and processes supplied text. " * 105)[:8200]
        return f"Use only this neutral measurement context and answer with the phrase LOCAL CPU.\n\n{context}\n\nAnswer:\n/no_think"

    def _new_core(self, backend: str) -> SubprocessPerQueryCore | PersistentCoreBackend:
        if backend == SUBPROCESS_PER_QUERY:
            return SubprocessPerQueryCore(self.completion, self.model, threads=4, context_size=4096)
        return PersistentCoreBackend(self.server, self.model, threads=4, context_size=4096)

    def audit(self, matrix_id: str | None = None) -> dict[str, Any]:
        run_id = _run_id("audit")
        payload = self._base("audit", run_id, matrix_id)
        executables = []
        for path in sorted((self.root / "third_party/llama.cpp").glob("build-win*/**/*.exe")):
            if path.name.casefold().startswith("llama-"):
                executables.append({
                    "name": path.name, "path": str(path.resolve()), "bytes": path.stat().st_size,
                    "sha256": file_sha256(path), "exists": True,
                    "capability": "persistent HTTP Core" if path.name == "llama-server.exe" else "one process per query" if path.name == "llama-completion.exe" else "official auxiliary executable",
                    "required_recompilation": "llama-server.exe" in path.name and "build-win-persistent" in path.as_posix(),
                })
        cache = self.root / "third_party/llama.cpp/build-win-persistent/CMakeCache.txt"
        flags = {}
        if cache.is_file():
            for line in cache.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.startswith(("CMAKE_BUILD_TYPE:", "CMAKE_CXX_COMPILER:", "CMAKE_GENERATOR:", "BUILD_SHARED_LIBS:", "GGML_NATIVE:", "GGML_OPENMP:", "GGML_CUDA:", "GGML_VULKAN:", "LLAMA_CURL:", "LLAMA_BUILD_SERVER:")):
                    key, value = line.split("=", 1)
                    flags[key] = value
        baseline_hash_now = file_sha256(self.completion)
        phase4ew_now = _tree_digest(self.root / "results/phase4ew")
        llama_status = subprocess.run(["git", "status", "--short"], cwd=self.root / "third_party/llama.cpp", capture_output=True, text=True, encoding="utf-8", errors="replace")
        payload.update({
            "status": "PASS" if baseline_hash_now == self.identity["subprocess_runtime"]["sha256"] and phase4ew_now == self.phase4ew_before and not llama_status.stdout.strip() else "FAIL",
            "platform": {"system": platform.system(), "release": platform.release(), "version": platform.version(), "machine": platform.machine(), "logical_cpus": os.cpu_count(), "python": platform.python_version()},
            "backends": executables,
            "experimental_build": {"performed": True, "directory": str(self.root / "third_party/llama.cpp/build-win-persistent"), "flags": flags, "source_commit": FROZEN_LLAMA_COMMIT},
            "baseline_runtime_preserved": baseline_hash_now == self.identity["subprocess_runtime"]["sha256"],
            "phase4ew_before": self.phase4ew_before,
            "phase4ew_after": phase4ew_now,
            "llama_source_tracked_clean": not bool(llama_status.stdout.strip()),
            "network_scope": "127.0.0.1 only; dynamic local port",
        })
        self._write("audit", payload)
        return payload

    def core_only(self, matrix_id: str | None = None) -> dict[str, Any]:
        run_id = _run_id("core-only")
        payload = self._base("core_only", run_id, matrix_id)
        repetitions = 1 if self.quick else 5
        runs: dict[str, list[dict[str, Any]]] = {SUBPROCESS_PER_QUERY: [], PERSISTENT_CORE: []}
        startup: dict[str, dict[str, Any]] = {SUBPROCESS_PER_QUERY: {"persistent_core_ready_ms": 0.0}}
        errors = []
        for backend_name in (SUBPROCESS_PER_QUERY, PERSISTENT_CORE):
            core = self._new_core(backend_name)
            try:
                if backend_name == PERSISTENT_CORE:
                    startup[backend_name] = core.start()
                index = 0
                for prompt_class in ("tiny", "short", "medium"):
                    for repetition in range(1, repetitions + 1):
                        index += 1
                        try:
                            prompt = self._core_prompt(prompt_class)
                            measured = core.generate(GenerationRequest(prompt, max_tokens=96, temperature=0.0))
                            answer = clean_answer(str(measured["stdout"]))
                            runs[backend_name].append({
                                "index": index, "prompt_class": prompt_class, "repetition": repetition,
                                "status": "PASS" if measured["return_code"] == 0 and bool(answer) else "FAIL",
                                "answer": answer, "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                                "metrics": measured["metrics"], "runtime_report": measured.get("runtime_report"),
                            })
                        except BaseException as error:
                            failure = {"backend": backend_name, "prompt_class": prompt_class, "repetition": repetition, "type": type(error).__name__, "message": str(error)}
                            errors.append(failure)
                            runs[backend_name].append({"index": index, "prompt_class": prompt_class, "repetition": repetition, "status": "FAIL", "error": failure})
            finally:
                core.close()
        summary = {}
        for backend_name, backend_runs in runs.items():
            passed = [run for run in backend_runs if run["status"] == "PASS"]
            metrics = [run["metrics"] for run in passed]
            summary[backend_name] = {
                "queries": len(backend_runs),
                "model_loads": len(passed) if backend_name == SUBPROCESS_PER_QUERY else (1 if passed else 0),
                "startup": startup.get(backend_name),
                "ttft_ms": _stats(item.get("ttft_ms") for item in metrics),
                "total_latency_ms": _stats(item.get("latency_ms") for item in metrics),
                "prompt_tokens_per_second": _stats(item.get("prompt_tokens_per_second") for item in metrics),
                "generation_tokens_per_second": _stats(item.get("tokens_per_second") for item in metrics),
                "cpu_time_seconds": sum(item.get("cpu_time_seconds") or (item.get("cpu_user_seconds") or 0) + (item.get("cpu_kernel_seconds") or 0) for item in metrics),
                "working_set_bytes": _stats(item.get("working_set_bytes_max") for item in metrics),
                "private_bytes": _stats(item.get("private_bytes_max") for item in metrics),
                "thread_count": _stats(item.get("thread_count_max") for item in metrics),
                "handle_count": _stats(item.get("handle_count_max") for item in metrics),
            }
        sub_latency = summary[SUBPROCESS_PER_QUERY]["total_latency_ms"]["median"] or 0.0
        persistent_latency = summary[PERSISTENT_CORE]["total_latency_ms"]["median"] or 0.0
        persistent_startup = startup.get(PERSISTENT_CORE, {}).get("persistent_core_ready_ms") or 0.0
        amortized = {}
        for count in (1, 2, 5, 10, 20):
            amortized[str(count)] = {
                SUBPROCESS_PER_QUERY: sub_latency,
                PERSISTENT_CORE: (persistent_startup + count * persistent_latency) / count,
                "measurement": "median per-query estimate plus measured one-time startup",
            }
        persistent_load = startup.get(PERSISTENT_CORE, {}).get("model_load_ms") or 0.0
        model_loads_avoided = max(0, len(runs[PERSISTENT_CORE]) - 1)
        payload.update({
            "status": "PASS" if not errors and all(run["status"] == "PASS" for values in runs.values() for run in values) else "FAIL",
            "a_b_labels": [SUBPROCESS_PER_QUERY, PERSISTENT_CORE],
            "runs": runs,
            "summary": summary,
            "amortized_latency_ms": amortized,
            "model_loads_avoided": model_loads_avoided,
            "estimated_load_time_avoided_ms": model_loads_avoided * persistent_load,
            "wall_time_saved_per_query_ms": sub_latency - persistent_latency,
            "cpu_time_saved_total_seconds": summary[SUBPROCESS_PER_QUERY]["cpu_time_seconds"] - summary[PERSISTENT_CORE]["cpu_time_seconds"],
            "first_query": {backend: runs[backend][0]["metrics"] for backend in runs if runs[backend] and runs[backend][0]["status"] == "PASS"},
            "warm_session_ttft_ms": _stats(run["metrics"].get("ttft_ms") for run in runs[PERSISTENT_CORE][1:] if run["status"] == "PASS"),
            "errors": errors,
        })
        self._write("core_only", payload)
        return payload

    def brain_ssd_ab(self, matrix_id: str | None = None) -> dict[str, Any]:
        run_id = _run_id("brain-ab")
        payload = self._base("brain_ssd_ab", run_id, matrix_id)
        selected = self.queries[:2] if self.quick else self.queries
        runs: dict[str, list[dict[str, Any]]] = {SUBPROCESS_PER_QUERY: [], PERSISTENT_CORE: []}
        errors = []
        hud_state = None
        for backend_name, core_mode in ((SUBPROCESS_PER_QUERY, "subprocess"), (PERSISTENT_CORE, "persistent")):
            hud = HudRuntime() if backend_name == PERSISTENT_CORE else None
            try:
                with LocalBrainSSD(self.root, core_mode=core_mode) as runtime:
                    for index, query in enumerate(selected, 1):
                        try:
                            result = runtime.answer(query["query"], hud_runtime=hud if index == 1 else None, persist=False)
                            runs[backend_name].append(_result_row(result, query, index))
                        except BaseException as error:
                            failure = {"backend": backend_name, "query_id": query["query_id"], "type": type(error).__name__, "message": str(error)}
                            errors.append(failure)
                            runs[backend_name].append({"index": index, "query_spec": query, "status": "FAIL", "error": failure})
                if hud is not None:
                    hud_state = hud.state.snapshot()
            finally:
                if hud is not None:
                    hud.close()
        comparisons = []
        for subprocess_run, persistent_run in zip(runs[SUBPROCESS_PER_QUERY], runs[PERSISTENT_CORE]):
            if subprocess_run["status"] != "PASS" or persistent_run["status"] != "PASS":
                comparisons.append({"query_id": subprocess_run["query_spec"]["query_id"], "equivalent": False, "reason": "failed run"})
                continue
            cognitive_fields = {
                "activated_pages": subprocess_run["retrieval"]["activated_pages"] == persistent_run["retrieval"]["activated_pages"],
                "active_brain_bytes": subprocess_run["retrieval"]["active_brain_bytes"] == persistent_run["retrieval"]["active_brain_bytes"],
                "record_ids": subprocess_run["retrieval"]["record_ids"] == persistent_run["retrieval"]["record_ids"],
                "record_order": subprocess_run["retrieval"]["context"]["source_ids"] == persistent_run["retrieval"]["context"]["source_ids"],
                "context_sha256": subprocess_run["context_sha256"] == persistent_run["context_sha256"],
                "context_tokens": subprocess_run["retrieval"]["context"]["estimated_tokens"] == persistent_run["retrieval"]["context"]["estimated_tokens"],
                "retrieval_status": subprocess_run["retrieval"]["status"] == persistent_run["retrieval"]["status"],
                "generation_config_hash": subprocess_run["generation"]["configuration_hash"] == persistent_run["generation"]["configuration_hash"],
            }
            quality_equivalent = persistent_run["quality"]["required_fact_score"] >= subprocess_run["quality"]["required_fact_score"] and persistent_run["answer_status"] == subprocess_run["answer_status"]
            comparisons.append({
                "query_id": subprocess_run["query_spec"]["query_id"],
                "cognitive_fields": cognitive_fields,
                "cognitive_equivalent": all(cognitive_fields.values()),
                "quality_equivalent_or_better": quality_equivalent,
                "equivalent": all(cognitive_fields.values()) and quality_equivalent,
            })
        def metric_stats(backend: str, field: str) -> dict[str, Any]:
            return _stats(run["generation"]["metrics"].get(field) for run in runs[backend] if run["status"] == "PASS")
        summary = {
            backend: {
                "total_latency_ms": _stats(run["timing_ms"].get("total") for run in runs[backend] if run["status"] == "PASS"),
                "ttft_ms": metric_stats(backend, "ttft_ms"),
                "prompt_tokens_per_second": metric_stats(backend, "prompt_tokens_per_second"),
                "generation_tokens_per_second": metric_stats(backend, "tokens_per_second"),
                "working_set_bytes": metric_stats(backend, "working_set_bytes_max"),
                "private_bytes": metric_stats(backend, "private_bytes_max"),
                "active_brain_bytes": _stats(run["retrieval"].get("active_brain_bytes") for run in runs[backend] if run["status"] == "PASS"),
                "context_tokens": _stats(run["retrieval"]["context"].get("estimated_tokens") for run in runs[backend] if run["status"] == "PASS"),
            } for backend in runs
        }
        payload.update({
            "status": "PASS" if not errors and comparisons and all(item["equivalent"] for item in comparisons) else "FAIL",
            "runs": runs,
            "comparisons": comparisons,
            "cognitive_selection_equivalent": bool(comparisons and all(item.get("cognitive_equivalent") for item in comparisons)),
            "context_hash_equivalent": bool(comparisons and all(item.get("cognitive_fields", {}).get("context_sha256") for item in comparisons)),
            "retrieval_equivalent": bool(comparisons and all(item.get("cognitive_fields", {}).get("retrieval_status") for item in comparisons)),
            "quality_equivalent": bool(comparisons and all(item.get("quality_equivalent_or_better") for item in comparisons)),
            "summary": summary,
            "hud_behavior": {
                "events_integrated": True,
                "core": (hud_state or {}).get("core"),
                "knowledge_active_brain_separate_from_core_resident_memory": True,
                "intelligence_claimed": False,
            },
            "errors": errors,
        })
        self._write("brain_ssd_ab", payload)
        return payload

    def session(self, matrix_id: str | None = None) -> dict[str, Any]:
        run_id = _run_id("session")
        payload = self._base("session", run_id, matrix_id)
        count = 3 if self.quick else 10
        runs = []
        errors = []
        events = []
        before = _process_count("llama-server")
        try:
            with LocalBrainSSD(self.root, core_mode="persistent") as runtime:
                original_generate = runtime.core_backend.generate

                def observed_generate(request: GenerationRequest, **kwargs: Any) -> dict[str, Any]:
                    external = kwargs.get("on_event")
                    def record(name: str, metrics: dict[str, Any]) -> None:
                        events.append({"event": name, "metrics": metrics})
                        if external:
                            external(name, metrics)
                    kwargs["on_event"] = record
                    return original_generate(request, **kwargs)

                runtime.core_backend.generate = observed_generate  # type: ignore[method-assign]
                for index in range(count):
                    query = self.queries[index % len(self.queries)]
                    try:
                        runs.append(_result_row(runtime.answer(query["query"], persist=False), query, index + 1))
                    except BaseException as error:
                        failure = {"query_id": query["query_id"], "type": type(error).__name__, "message": str(error)}
                        errors.append(failure)
                        runs.append({"index": index + 1, "query_spec": query, "status": "FAIL", "error": failure})
        finally:
            after = _process_count("llama-server")
        memory = _memory_stability(runs)
        passed = [run for run in runs if run["status"] == "PASS"]
        payload.update({
            "status": "PASS" if not errors and len(passed) == count and after in {0, before} and memory["classification"] != "UNBOUNDED_GROWTH" else "FAIL",
            "runs": runs,
            "queries": len(runs),
            "first_query_ttft_ms": passed[0]["generation"]["metrics"].get("ttft_ms") if passed else None,
            "warm_session_ttft_ms": _stats(run["generation"]["metrics"].get("ttft_ms") for run in passed[1:]),
            "total_latency_ms": _stats(run["timing_ms"].get("total") for run in passed),
            "generation_tokens_per_second": _stats(run["generation"]["metrics"].get("tokens_per_second") for run in passed),
            "prompt_tokens_per_second": _stats(run["generation"]["metrics"].get("prompt_tokens_per_second") for run in passed),
            "memory": memory,
            "model_loads": passed[-1]["generation"]["metrics"].get("model_loads") if passed else None,
            "reloads_avoided": passed[-1]["generation"]["metrics"].get("reloads_avoided") if passed else None,
            "core_reuse_ratio": passed[-1]["generation"]["metrics"].get("core_reuse_ratio") if passed else None,
            "events": events,
            "cleanup": {"llama_server_before": before, "llama_server_after": after, "clean": after in {0, before}},
            "errors": errors,
        })
        self._write("session", payload)
        return payload

    def contamination(self, matrix_id: str | None = None) -> dict[str, Any]:
        run_id = _run_id("contamination")
        payload = self._base("contamination", run_id, matrix_id)
        sequence = [self.qa[name] for name in ("holdout_json_frames", "holdout_unknown_near", "dev_sql_params", "dev_unknown")]
        runs = []
        errors = []
        with LocalBrainSSD(self.root, core_mode="persistent") as runtime:
            for index, query in enumerate(sequence, 1):
                try:
                    runs.append(_result_row(runtime.answer(query["query"], persist=False), query, index))
                except BaseException as error:
                    failure = {"query_id": query["query_id"], "type": type(error).__name__, "message": str(error)}
                    errors.append(failure)
                    runs.append({"index": index, "query_spec": query, "status": "FAIL", "error": failure})
        unknowns = [run for run in runs if run["status"] == "PASS" and not run["query_spec"].get("expected_record_ids")]
        leaked_terms = ("json.dump", "placeholder", "parameter substitution", "sqlite_busy")
        cross_query_context_leak = any(
            run["answer_status"] != "NO_KNOWLEDGE" or any(term in run["answer"].casefold() for term in leaked_terms)
            for run in unknowns
        )
        payload.update({
            "status": "PASS" if not errors and len(unknowns) == 2 and not cross_query_context_leak else "FAIL",
            "runs": runs,
            "context_reset": "cache_prompt=false for every HTTP completion request",
            "cross_query_context_leak": cross_query_context_leak,
            "expected": False,
            "errors": errors,
        })
        self._write("contamination", payload)
        return payload

    def sustained(self, matrix_id: str | None = None) -> dict[str, Any]:
        run_id = _run_id("sustained")
        payload = self._base("sustained", run_id, matrix_id)
        target_seconds = self.duration_minutes * 60
        started = time.monotonic()
        runs = []
        errors = []
        before = _process_count("llama-server")
        try:
            with LocalBrainSSD(self.root, core_mode="persistent") as runtime:
                index = 0
                while time.monotonic() - started < target_seconds:
                    query = self.queries[index % len(self.queries)]
                    index += 1
                    try:
                        runs.append(_result_row(runtime.answer(query["query"], persist=False), query, index))
                    except BaseException as error:
                        failure = {"query_id": query["query_id"], "type": type(error).__name__, "message": str(error)}
                        errors.append(failure)
                        break
        finally:
            after = _process_count("llama-server")
        actual = time.monotonic() - started
        memory = _memory_stability(runs)
        passed = [run for run in runs if run["status"] == "PASS"]
        payload.update({
            "status": "PASS" if not errors and passed and actual >= target_seconds and memory["classification"] != "UNBOUNDED_GROWTH" and after in {0, before} else "FAIL",
            "target_duration_seconds": target_seconds,
            "actual_duration_seconds": actual,
            "completed_duration": actual >= target_seconds,
            "queries": len(runs),
            "runs": runs,
            "latency_ms": _stats(run["timing_ms"].get("total") for run in passed),
            "ttft_ms": _stats(run["generation"]["metrics"].get("ttft_ms") for run in passed),
            "memory": memory,
            "persistent_reserved_memory": passed[0]["generation"]["metrics"].get("persistent_reserved_memory") if passed else None,
            "cleanup": {"llama_server_before": before, "llama_server_after": after, "clean": after in {0, before}},
            "time_series": [
                {
                    "index": run["index"], "total_latency_ms": run["timing_ms"].get("total"),
                    "ttft_ms": run["generation"]["metrics"].get("ttft_ms"),
                    "working_set_bytes": run["generation"]["metrics"].get("working_set_bytes_max"),
                    "private_bytes": run["generation"]["metrics"].get("private_bytes_max"),
                    "handles": run["generation"]["metrics"].get("handle_count_max"),
                    "threads": run["generation"]["metrics"].get("thread_count_max"),
                } for run in passed
            ],
            "errors": errors,
        })
        self._write("sustained", payload)
        return payload

    def run_all(self) -> dict[str, Any]:
        matrix_id = _run_id("matrix")
        print(json.dumps({"experiment_started": matrix_id, "quick": self.quick, "duration_minutes": self.duration_minutes}), flush=True)
        results = {
            "audit": self.audit(matrix_id),
            "core_only": self.core_only(matrix_id),
            "brain_ssd_ab": self.brain_ssd_ab(matrix_id),
            "session": self.session(matrix_id),
            "contamination": self.contamination(matrix_id),
            "sustained": self.sustained(matrix_id),
        }
        return self.summarize(matrix_id, results)

    def summarize(self, matrix_id: str, results: dict[str, dict[str, Any]]) -> dict[str, Any]:
        phase4ew_after = _tree_digest(self.root / "results/phase4ew")
        phase4ew_modified = phase4ew_after != self.phase4ew_before
        cleanup = all(results[name].get("cleanup", {}).get("clean", True) for name in ("session", "sustained"))
        all_pass = all(result.get("status") == "PASS" for result in results.values())
        canonical_counts = (
            not self.quick
            and len(results["core_only"]["runs"][SUBPROCESS_PER_QUERY]) >= 15
            and len(results["core_only"]["runs"][PERSISTENT_CORE]) >= 15
            and results["session"].get("queries", 0) >= 10
            and results["sustained"].get("actual_duration_seconds", 0) >= 20 * 60
        )
        cognitive = results["brain_ssd_ab"].get("cognitive_selection_equivalent", False)
        context = results["brain_ssd_ab"].get("context_hash_equivalent", False)
        quality = results["brain_ssd_ab"].get("quality_equivalent", False)
        no_leak = results["contamination"].get("cross_query_context_leak") is False
        stable = results["sustained"].get("memory", {}).get("classification") in {"STABLE", "STABLE_WITH_GROWTH"}
        sub_ttft = results["core_only"]["summary"][SUBPROCESS_PER_QUERY]["ttft_ms"].get("median")
        warm_ttft = results["core_only"].get("warm_session_ttft_ms", {}).get("median")
        absolute_gain = sub_ttft - warm_ttft if isinstance(sub_ttft, (int, float)) and isinstance(warm_ttft, (int, float)) else None
        percentage_gain = 100 * absolute_gain / sub_ttft if isinstance(absolute_gain, (int, float)) and sub_ttft else None
        sub_latency = results["core_only"]["summary"][SUBPROCESS_PER_QUERY]["total_latency_ms"].get("median")
        persistent_latency = results["core_only"]["summary"][PERSISTENT_CORE]["total_latency_ms"].get("median")
        total_latency_gain = sub_latency - persistent_latency if isinstance(sub_latency, (int, float)) and isinstance(persistent_latency, (int, float)) else None
        total_latency_percentage = 100 * total_latency_gain / sub_latency if isinstance(total_latency_gain, (int, float)) and sub_latency else None
        significant_gain = bool(
            (isinstance(percentage_gain, (int, float)) and percentage_gain >= 10 and absolute_gain > 0)
            or (isinstance(total_latency_percentage, (int, float)) and total_latency_percentage >= 10 and total_latency_gain > 0)
        )
        support_conditions = all((cognitive, context, quality, no_leak, stable, cleanup, significant_gain))
        if support_conditions:
            hypothesis_status = "SUPPORTED"
        elif all((cognitive, context, quality, no_leak, stable, cleanup)):
            hypothesis_status = "CONDITIONAL"
        else:
            hypothesis_status = "REJECTED"
        operational = "PASS" if all_pass and canonical_counts and not phase4ew_modified else "PASS_QUICK_NON_CANONICAL" if all_pass and self.quick and not phase4ew_modified else "FAIL"
        recommendation = "KEEP" if hypothesis_status == "SUPPORTED" else "CONDITIONAL" if hypothesis_status == "CONDITIONAL" else "REJECT"
        core = results["core_only"]
        brain = results["brain_ssd_ab"]
        persistent_summary = core["summary"][PERSISTENT_CORE]
        subprocess_summary = core["summary"][SUBPROCESS_PER_QUERY]
        summary = {
            **self._base("all", matrix_id, matrix_id),
            "completed_at_utc": _utc_now(),
            "operational_status": operational,
            "status": operational,
            "hypothesis_status": hypothesis_status,
            "recommendation": recommendation,
            "canonical_experiment": canonical_counts and all_pass,
            "required_sets": {name: value.get("status") for name, value in results.items()},
            "criteria": {
                "cognitive_selection_equivalent": cognitive, "context_hash_equivalent": context,
                "quality_equivalent": quality, "cross_query_context_leak": not no_leak,
                "memory_stable_or_bounded": stable, "cleanup": cleanup,
                "significant_gain": significant_gain, "canonical_counts": canonical_counts,
            },
            "runtime_hashes": {"subprocess": self.identity["subprocess_runtime"]["sha256"], "persistent": self.identity["persistent_runtime"]["sha256"]},
            "startup": persistent_summary.get("startup"),
            "core_only": core.get("summary"),
            "first_query": core.get("first_query"),
            "warm_session_ttft_ms": core.get("warm_session_ttft_ms"),
            "gain": {
                "absolute_ttft_ms": absolute_gain,
                "percentage_ttft": percentage_gain,
                "absolute_total_latency_ms": total_latency_gain,
                "percentage_total_latency": total_latency_percentage,
                "wall_time_saved_per_query_ms": core.get("wall_time_saved_per_query_ms"),
                "criterion": "median warm TTFT or median total latency improves by at least 10 percent; threshold is reported, not a hidden adoption rule",
            },
            "amortized_latency_ms": core.get("amortized_latency_ms"),
            "model_loads": {SUBPROCESS_PER_QUERY: subprocess_summary.get("model_loads"), PERSISTENT_CORE: persistent_summary.get("model_loads")},
            "reloads_avoided": core.get("model_loads_avoided"),
            "estimated_load_time_avoided_ms": core.get("estimated_load_time_avoided_ms"),
            "core_reuse_ratio": results["session"].get("core_reuse_ratio"),
            "brain_ssd_ab": brain.get("summary"),
            "brain_equivalence": {
                "active_brain": cognitive, "context_hash": context,
                "retrieval": brain.get("retrieval_equivalent"), "quality": quality,
            },
            "no_knowledge": {
                "preserved": no_leak,
                "cross_query_context_leak": results["contamination"].get("cross_query_context_leak"),
            },
            "session": {key: results["session"].get(key) for key in ("queries", "first_query_ttft_ms", "warm_session_ttft_ms", "total_latency_ms", "memory", "cleanup")},
            "sustained": {key: results["sustained"].get(key) for key in ("queries", "actual_duration_seconds", "latency_ms", "ttft_ms", "memory", "persistent_reserved_memory", "cleanup")},
            "hud_behavior": brain.get("hud_behavior"),
            "resource_tradeoff": {
                "subprocess_working_set_bytes": subprocess_summary.get("working_set_bytes"),
                "persistent_working_set_bytes": persistent_summary.get("working_set_bytes"),
                "subprocess_private_bytes": subprocess_summary.get("private_bytes"),
                "persistent_private_bytes": persistent_summary.get("private_bytes"),
                "persistent_reserved_memory": results["sustained"].get("persistent_reserved_memory"),
                "target_8gb": "NOT_TESTED",
            },
            "phase4ew_before": self.phase4ew_before,
            "phase4ew_after": phase4ew_after,
            "phase4ew_modified": phase4ew_modified,
            "default_core_mode_changed": False,
            "phase4f_started": False,
            "phase5_or_prefetch_started": False,
            "result_run_ids": {name: result["run_id"] for name, result in results.items()},
        }
        immutable = self.results / "summaries" / f"{matrix_id}.json"
        _exclusive_json(immutable, summary)
        _atomic_json(self.results / "summary.json", summary)
        markdown = self._summary_markdown(summary)
        immutable_md = self.results / "summaries" / f"{matrix_id}.md"
        immutable_md.write_text(markdown, encoding="utf-8", newline="\n")
        temporary = self.results / ".SUMMARY.md.tmp"
        temporary.write_text(markdown, encoding="utf-8", newline="\n")
        os.replace(temporary, self.results / "SUMMARY.md")
        print(json.dumps({"experiment_complete": matrix_id, "status": operational, "hypothesis": hypothesis_status}), flush=True)
        return summary

    def _summary_markdown(self, summary: dict[str, Any]) -> str:
        return "\n".join([
            "# Windows Core Runtime Experiment", "",
            f"- Experiment: `{EXPERIMENT}` / `{EXPERIMENT_ALIAS}`",
            f"- Operational status: `{summary['operational_status']}`",
            f"- Hypothesis `{HYPOTHESIS}`: `{summary['hypothesis_status']}`",
            f"- Recommendation: `{summary['recommendation']}`",
            f"- Default remains: `{SUBPROCESS_PER_QUERY}`", "",
            "## Measured result", "",
            f"- Warm TTFT gain: `{summary['gain']}`",
            f"- Startup: `{summary['startup']}`",
            f"- Model loads: `{summary['model_loads']}`",
            f"- Reloads avoided: `{summary['reloads_avoided']}`",
            f"- Core reuse ratio: `{summary['core_reuse_ratio']}`",
            f"- Brain equivalence: `{summary['brain_equivalence']}`",
            f"- NO_KNOWLEDGE / leak: `{summary['no_knowledge']}`",
            f"- Sustained: `{summary['sustained']}`", "",
            "This is a Windows runtime optimization experiment. It is not Phase 4F, Phase 5, prefetch, or a cognitive architecture change.", "",
        ])
