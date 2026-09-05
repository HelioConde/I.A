from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import re
import statistics
import subprocess
import threading
import time
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Callable, Iterable

from brain_ssd.backend import GenerationRequest
from brain_ssd.hud.server import create_server
from brain_ssd.hud.state import HudRuntime
from brain_ssd.local_runtime.backend import FROZEN_LLAMA_COMMIT, LocalLlamaCppBackend, probe_llama, resolve_llama_executable
from brain_ssd.local_runtime.capabilities import EnvironmentCapabilities
from brain_ssd.local_runtime.pipeline import (
    INDEX_RELATIVE,
    MANIFEST_RELATIVE,
    MODEL_RELATIVE,
    QA_RELATIVE,
    LocalBrainSSD,
    _run_measured,
    atomic_write_json,
    clean_answer,
    file_sha256,
)
from brain_ssd.local_runtime.windows_metrics import ProcessSnapshot, windows_process_snapshot


VALIDATION_TRACK = "PHASE_4E_W"
ENVIRONMENT = "WINDOWS_NATIVE_FUNCTIONAL"
DEVELOPMENT_STATUS = "EXPERIMENTAL_FUNCTIONAL_RUNTIME"
PHASE4E_INVALID_REASON = "Phase 4E canonical physical baseline requires Debian/Linux native environment."
TARGET_8GB_STATUS = "NOT_TESTED"
RESULTS_RELATIVE = Path("results/phase4ew")
ERROR_TYPES = {
    "STARTUP_ERROR", "MODEL_ERROR", "RETRIEVAL_ERROR", "STORAGE_ERROR", "CONTEXT_ERROR",
    "CORE_ERROR", "TIMEOUT", "OOM", "HUD_ERROR", "CLEANUP_ERROR",
}


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _run_id(prefix: str) -> str:
    return f"{prefix}-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-{uuid.uuid4().hex[:10]}"


def _sha256_json(payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _exclusive_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"immutable result already exists: {path}")
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    with temporary.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
    os.replace(temporary, path)
    return path


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * fraction)]


def _stats(values: Iterable[int | float | None]) -> dict[str, float | None]:
    selected = [float(value) for value in values if isinstance(value, (int, float)) and math.isfinite(float(value))]
    if not selected:
        return {"count": 0, "min": None, "median": None, "p95": None, "max": None, "mean": None, "coefficient_of_variation": None}
    mean = statistics.mean(selected)
    coefficient = statistics.pstdev(selected) / mean if len(selected) > 1 and mean else 0.0
    return {
        "count": len(selected),
        "min": min(selected),
        "median": statistics.median(selected),
        "p95": _percentile(selected, 0.95),
        "max": max(selected),
        "mean": mean,
        "coefficient_of_variation": coefficient,
    }


def _outlier_flags(values: list[float | None]) -> list[bool]:
    present = sorted(float(value) for value in values if isinstance(value, (int, float)))
    if len(present) < 4:
        return [False] * len(values)
    q1 = _percentile(present, 0.25) or 0.0
    q3 = _percentile(present, 0.75) or 0.0
    spread = q3 - q1
    low, high = q1 - 1.5 * spread, q3 + 1.5 * spread
    return [bool(isinstance(value, (int, float)) and (value < low or value > high)) for value in values]


def _snapshot_dict(snapshot: ProcessSnapshot, query_index: int | None = None) -> dict[str, Any]:
    cpu_time = None
    if snapshot.cpu_user_seconds is not None or snapshot.cpu_kernel_seconds is not None:
        cpu_time = (snapshot.cpu_user_seconds or 0.0) + (snapshot.cpu_kernel_seconds or 0.0)
    return {
        "timestamp_monotonic": snapshot.timestamp,
        "query_index": query_index,
        "working_set_bytes": snapshot.working_set_bytes,
        "peak_working_set_bytes": snapshot.peak_working_set_bytes,
        "private_bytes": snapshot.private_bytes,
        "available_system_ram_bytes": snapshot.system_available_ram_bytes,
        "total_system_ram_bytes": snapshot.system_total_ram_bytes,
        "process_cpu_time_seconds": cpu_time,
        "handles": snapshot.handle_count,
        "threads": snapshot.thread_count,
        "process_io_read_transfer_bytes": snapshot.read_transfer_bytes,
        "process_io_write_transfer_bytes": snapshot.write_transfer_bytes,
        "physical_read_bytes": None,
    }


def _error_type(error: BaseException, stage: str) -> str:
    text = f"{type(error).__name__} {error}".casefold()
    if isinstance(error, TimeoutError) or "timeout" in text:
        return "TIMEOUT"
    if isinstance(error, MemoryError) or "out of memory" in text or "oom" in text:
        return "OOM"
    mapping = {
        "startup": "STARTUP_ERROR", "model": "MODEL_ERROR", "retrieval": "RETRIEVAL_ERROR",
        "storage": "STORAGE_ERROR", "context": "CONTEXT_ERROR", "core": "CORE_ERROR",
        "hud": "HUD_ERROR", "cleanup": "CLEANUP_ERROR",
    }
    return mapping.get(stage, "CORE_ERROR")


def _powershell_json(script: str) -> Any:
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", f"$ErrorActionPreference='Stop'; {script} | ConvertTo-Json -Depth 6 -Compress"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return {"status": "NOT_MEASURED", "reason": result.stderr.strip()[-500:] or "PowerShell query returned no data"}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"status": "NOT_MEASURED", "reason": "PowerShell returned non-JSON data", "raw": result.stdout[-500:]}


def _git_commit(root: Path) -> str | None:
    result = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return result.stdout.strip() or None


def _score_answer(answer: str, query: dict[str, Any], retrieved: list[str]) -> dict[str, Any]:
    lower = answer.casefold()
    groups = query.get("required_fact_groups", [])
    facts = sum(any(term.casefold() in lower for term in alternatives) for alternatives in groups)
    source_ids = set(re.findall(r"\[SOURCE:\s*([0-9a-f]{24})\]", answer, re.IGNORECASE))
    expected = set(query.get("expected_record_ids", []))
    unknown_ok = not expected and "no_knowledge" in lower
    return {
        "required_facts_found": facts,
        "required_facts_total": len(groups),
        "required_fact_score": facts / len(groups) if groups else float(unknown_ok),
        "cited_source_ids": sorted(source_ids),
        "source_correct": bool(source_ids & expected) if expected else unknown_ok,
        "retrieval_supports_expected": bool(set(retrieved) & expected) if expected else not retrieved,
        "groundedness_scope": "required-fact and expected-source support only; not a general hallucination detector",
    }


class Phase4EWRunner:
    def __init__(self, root: Path, *, quick: bool = False, duration_minutes: float | None = None) -> None:
        self.root = root.resolve()
        self.results = self.root / RESULTS_RELATIVE
        self.quick = quick
        self.duration_minutes = duration_minutes if duration_minutes is not None else (5.0 if quick else 20.0)
        self.model = self.root / MODEL_RELATIVE
        self.executable = resolve_llama_executable(self.root)
        self.backend = LocalLlamaCppBackend(self.executable, self.model, threads=4, context_size=4096)
        self.qa = json.loads((self.root / QA_RELATIVE).read_text(encoding="utf-8"))["queries"]
        self.queries = self._query_set()
        self.identity = {
            "git_commit": _git_commit(self.root),
            "llama_cpp_commit": FROZEN_LLAMA_COMMIT,
            "runtime_sha256": file_sha256(self.executable),
            "model_sha256": file_sha256(self.model),
            "model_bytes": self.model.stat().st_size,
        }
        self.environment_fingerprint = _sha256_json({
            "system": platform.system(), "release": platform.release(), "version": platform.version(),
            "machine": platform.machine(), "processor": platform.processor(), "logical_cpus": os.cpu_count(),
            "python": platform.python_version(), **self.identity,
        })

    def _query_set(self) -> list[dict[str, Any]]:
        ids = ["holdout_json_frames", "dev_sql_params", "holdout_python_sqlite", "holdout_eager_paraphrase", "holdout_unknown_near"]
        by_id = {query["query_id"]: query for query in self.qa}
        return [by_id[query_id] for query_id in ids]

    def _base(self, mode: str, run_id: str, matrix_id: str | None) -> dict[str, Any]:
        configuration = {
            "mode": mode,
            "quick": self.quick,
            "duration_minutes": self.duration_minutes if mode == "sustained" else None,
            "threads": 4,
            "context_size": 4096,
            "max_tokens": 96,
            "temperature": 0.0,
            "device": "none",
            "reasoning": "off",
            "model_reuse": False,
            "index_reuse_within_session": mode in {"session", "repeated_query", "sustained"},
        }
        return {
            "schema_version": 1,
            "validation_track": VALIDATION_TRACK,
            "environment": ENVIRONMENT,
            "development_status": DEVELOPMENT_STATUS,
            "phase4e_valid": False,
            "phase4e_invalid_reason": PHASE4E_INVALID_REASON,
            "target_8gb": TARGET_8GB_STATUS,
            "phase4ew_canonical": False,
            "canonical": False,
            "mode": mode,
            "run_id": run_id,
            "matrix_id": matrix_id,
            "timestamp_utc": _utc_now(),
            "identity": self.identity,
            "environment_fingerprint": self.environment_fingerprint,
            "configuration": configuration,
            "config_hash": _sha256_json(configuration),
        }

    def _write(self, category: str, run_id: str, payload: dict[str, Any]) -> Path:
        path = self.results / category / f"{run_id}.json"
        _exclusive_json(path, payload)
        print(json.dumps({"phase4ew": category, "run_id": run_id, "status": payload.get("status"), "path": str(path)}, ensure_ascii=False), flush=True)
        return path

    def matrix_plan(self) -> dict[str, Any]:
        return {
            "validation_track": VALIDATION_TRACK,
            "quick": self.quick,
            "phase4ew_canonical_if_completed": not self.quick and self.duration_minutes >= 20,
            "modes": {
                "audit": {"runs": 1, "model_execution": False},
                "core_isolation": {"classes": ["tiny", "medium"] if self.quick else ["tiny", "short", "medium"], "total_runs": 2 if self.quick else 15, "repetitions_per_class": 1 if self.quick else 5},
                "single_shot": {"queries": [query["query_id"] for query in (self.queries[:3] if self.quick else self.queries)]},
                "session": {"queries": 3 if self.quick else 10},
                "repeated_query": {"repetitions": 3 if self.quick else 10},
                "sustained": {"duration_minutes": self.duration_minutes, "sample_interval_seconds": 1},
                "hud_overhead": {"variants": ["HUD_OFF", "TELEMETRY_ONLY", "HUD_LIVE"]},
            },
            "estimated_note": "Actual duration is dominated by the frozen Qwen CPU backend; no speed threshold determines PASS.",
        }

    def audit(self, matrix_id: str | None = None) -> dict[str, Any]:
        run_id = _run_id("audit")
        payload = self._base("audit", run_id, matrix_id)
        freeze_path = self.root / "results/phase4e/preparation/phase4d-freeze-manifest.json"
        freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
        freeze_results = {}
        for relative, expected in freeze["files"].items():
            path = self.root / relative
            actual = file_sha256(path) if path.is_file() else None
            canonical = None
            if path.is_file() and actual != expected:
                try:
                    canonical = hashlib.sha256(path.read_text(encoding="utf-8").replace("\r\n", "\n").encode("utf-8")).hexdigest()
                except UnicodeDecodeError:
                    pass
            freeze_results[relative] = {"expected": expected, "actual": actual, "canonical_lf": canonical, "ok": actual == expected or canonical == expected}
        canonical_entries = 0
        canonical_failures: list[str] = []
        for manifest in sorted((self.root / "results").rglob("*checksums.sha256")):
            for line in manifest.read_text(encoding="utf-8").splitlines():
                if not line.strip() or line.startswith("#"):
                    continue
                expected, relative = line.split(maxsplit=1)
                path = self.root / relative.lstrip("*")
                canonical_entries += 1
                if not path.is_file():
                    canonical_failures.append(relative)
                    continue
                actual = file_sha256(path)
                try:
                    normalized = hashlib.sha256(path.read_text(encoding="utf-8").replace("\r\n", "\n").encode("utf-8")).hexdigest()
                except UnicodeDecodeError:
                    normalized = None
                if expected not in {actual, normalized}:
                    canonical_failures.append(relative)
        host = self._host_audit()
        capabilities = EnvironmentCapabilities.detect(self.root).to_dict()
        runtime = probe_llama(self.executable)
        all_ok = (
            not canonical_failures
            and all(item["ok"] for item in freeze_results.values())
            and self.identity["model_sha256"] == "9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031"
            and self.identity["model_bytes"] == 639_446_688
            and self.identity["llama_cpp_commit"] == FROZEN_LLAMA_COMMIT
            and runtime["frozen_commit_match"]
            and runtime["cpu_only_build"]
        )
        payload.update({
            "status": "PASS" if all_ok else "FAIL",
            "freeze_id": freeze["freeze_id"],
            "freeze_files": {"count": len(freeze_results), "failures": [key for key, value in freeze_results.items() if not value["ok"]], "details": freeze_results},
            "canonical_checksums": {"entries": canonical_entries, "failures": canonical_failures},
            "runtime": runtime,
            "host": host,
            "capabilities": capabilities,
            "limitations": {
                "linux_pss": "UNSUPPORTED", "cgroup": "UNSUPPORTED", "psi": "UNSUPPORTED",
                "pgscan": "NOT_MEASURED", "pgsteal": "NOT_MEASURED", "mincore_linux": "UNSUPPORTED",
                "madv_cold": "UNSUPPORTED", "madv_pageout": "UNSUPPORTED", "linux_page_cache": "UNSUPPORTED",
                "physical_ssd_bytes": "NOT_MEASURED", "temperature": "NOT_MEASURED",
            },
        })
        self._write("baseline", run_id, payload)
        return payload

    def _host_audit(self) -> dict[str, Any]:
        drive = self.root.drive.rstrip(":")
        processor = _powershell_json("Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed,CurrentClockSpeed")
        os_info = _powershell_json("Get-CimInstance Win32_OperatingSystem | Select-Object Caption,Version,BuildNumber,OSArchitecture,TotalVisibleMemorySize,FreePhysicalMemory,TotalVirtualMemorySize,FreeVirtualMemory")
        page_file = _powershell_json("Get-CimInstance Win32_PageFileUsage | Select-Object Name,AllocatedBaseSize,CurrentUsage,PeakUsage")
        disks = _powershell_json("Get-PhysicalDisk | Select-Object FriendlyName,MediaType,BusType,Size,HealthStatus")
        volume = _powershell_json(f"Get-Volume -DriveLetter '{drive}' | Select-Object DriveLetter,FileSystem,FileSystemLabel,Size,SizeRemaining,HealthStatus")
        process = _powershell_json(f"$p=Get-Process -Id {os.getpid()}; [pscustomobject]@{{PriorityClass=$p.PriorityClass.ToString();ProcessorAffinity=[int64]$p.ProcessorAffinity;HandleCount=$p.HandleCount;ThreadCount=$p.Threads.Count}}")
        power = subprocess.run(["powercfg.exe", "/getactivescheme"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10)
        cmake_candidates = [
            Path(r"C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe"),
            Path("cmake.exe"),
        ]
        cmake_path = next((candidate for candidate in cmake_candidates if candidate.is_file()), None)
        cmake_version = None
        if cmake_path:
            cmake_result = subprocess.run([str(cmake_path), "--version"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10)
            cmake_version = cmake_result.stdout.splitlines()[0] if cmake_result.stdout else None
        return {
            "windows": os_info,
            "architecture": platform.machine(),
            "processor": processor,
            "logical_cpu_count_python": os.cpu_count(),
            "page_file": page_file,
            "physical_disks": disks,
            "project_volume": volume,
            "project_path": str(self.root),
            "python": {"version": platform.python_version(), "executable": os.path.realpath(os.sys.executable)},
            "cmake": {"path": str(cmake_path) if cmake_path else None, "version": cmake_version},
            "compiler_from_runtime": probe_llama(self.executable)["version_output"],
            "active_power_scheme": power.stdout.strip() if power.returncode == 0 else {"status": "NOT_MEASURED", "reason": power.stderr.strip()},
            "current_process": process,
            "settings_changed_automatically": False,
        }

    def _core_prompt(self, prompt_class: str) -> str:
        if prompt_class == "tiny":
            return "Responda apenas: AZUL\n/no_think"
        if prompt_class == "short":
            return "Answer concisely: what is the capital of France?\n/no_think"
        context = ("Measurement context: a compact CPU runtime loads a local model and processes supplied text. " * 105)[:8200]
        return f"Use only this neutral measurement context and answer with the phrase LOCAL CPU.\n\n{context}\n\nAnswer:\n/no_think"

    def _core_once(self, prompt_class: str, repetition: int) -> dict[str, Any]:
        prompt = self._core_prompt(prompt_class)
        started = time.time()
        try:
            measured = _run_measured(self.backend.command(GenerationRequest(prompt=prompt, max_tokens=96, temperature=0.0)))
            answer = clean_answer(str(measured["stdout"]))
            return {
                "prompt_class": prompt_class,
                "repetition": repetition,
                "timestamp": started,
                "status": "PASS" if measured["return_code"] == 0 and bool(answer) else "FAIL",
                "answer": answer,
                "answer_status": "NO_KNOWLEDGE" if "no_knowledge" in answer.casefold() else "ANSWER",
                "prompt_bytes": len(prompt.encode("utf-8")),
                "return_code": measured["return_code"],
                "metrics": measured["metrics"],
                "runtime_report": measured.get("runtime_report", {}),
                "measurement_semantics": measured.get("measurement_semantics", {}),
                "stderr_sha256": hashlib.sha256(str(measured["stderr"]).encode("utf-8")).hexdigest(),
                "error": None,
            }
        except BaseException as error:
            return {"prompt_class": prompt_class, "repetition": repetition, "timestamp": started, "status": "FAIL", "error": {"type": _error_type(error, "core"), "message": str(error)}}

    def core_isolation(self, matrix_id: str | None = None) -> dict[str, Any]:
        run_id = _run_id("core")
        payload = self._base("core_isolation", run_id, matrix_id)
        repetitions = 1 if self.quick else 5
        runs: list[dict[str, Any]] = []
        prompt_classes = ("tiny", "medium") if self.quick else ("tiny", "short", "medium")
        for prompt_class in prompt_classes:
            for repetition in range(1, repetitions + 1):
                print(f"4E-W core {prompt_class} {repetition}/{repetitions}", flush=True)
                runs.append(self._core_once(prompt_class, repetition))
        latencies = [run.get("metrics", {}).get("latency_ms") for run in runs]
        flags = _outlier_flags(latencies)
        for run, flag in zip(runs, flags):
            run["outlier_candidate"] = flag
            run["outlier_rule"] = "1.5*IQR on total latency; preserved in all aggregates"
        per_class = {}
        for prompt_class in ("tiny", "short", "medium"):
            selected = [run for run in runs if run["prompt_class"] == prompt_class and run["status"] == "PASS"]
            per_class[prompt_class] = {
                "runs": len(selected),
                "latency_ms": _stats(run["metrics"].get("latency_ms") for run in selected),
                "model_load_ms": _stats(run["metrics"].get("model_load_ms") for run in selected),
                "ttft_ms": _stats(run["metrics"].get("ttft_ms") for run in selected),
                "prompt_eval_ms": _stats(run["metrics"].get("prompt_eval_ms") for run in selected),
                "prompt_tokens_per_second": _stats(run["metrics"].get("prompt_tokens_per_second") for run in selected),
                "generation_eval_ms": _stats(run["metrics"].get("generation_eval_ms") for run in selected),
                "generation_tokens_per_second": _stats(run["metrics"].get("tokens_per_second") for run in selected),
                "working_set_bytes": _stats(run["metrics"].get("working_set_bytes_max") for run in selected),
                "private_bytes": _stats(run["metrics"].get("private_bytes_max") for run in selected),
                "cpu_average_percent": _stats(run["metrics"].get("cpu_percent_total_average") for run in selected),
                "cpu_peak_percent": _stats(run["metrics"].get("cpu_percent_total_peak") for run in selected),
            }
        successful = [run for run in runs if run["status"] == "PASS"]
        diagnostic_runs = [run for run in successful if run["prompt_class"] == "medium"] or successful
        median_tps = statistics.median([run["metrics"]["tokens_per_second"] for run in diagnostic_runs if run["metrics"].get("tokens_per_second") is not None]) if diagnostic_runs else None
        median_cpu = statistics.median([run["metrics"]["cpu_percent_total_average"] for run in diagnostic_runs if run["metrics"].get("cpu_percent_total_average") is not None]) if diagnostic_runs else None
        configured_capacity = 400.0
        utilization_of_configured = median_cpu / configured_capacity if median_cpu is not None else None
        cpu_flag = None
        if median_tps is not None and median_tps <= 2:
            cpu_flag = "POSSIBLE_CPU_UNDERUTILIZATION" if utilization_of_configured is not None and utilization_of_configured < 0.5 else "CORE_COMPUTE_LIMITED"
        payload.update({
            "status": "PASS" if len(successful) == len(runs) else "FAIL",
            "runs": runs,
            "summary": per_class,
            "thread_audit": {
                "logical_cpu_count": os.cpu_count(), "thread_parameter": 4,
                "runtime_configured_threads": next((run.get("runtime_report", {}).get("configured_threads") for run in successful if run.get("runtime_report")), None),
                "phase_specific_cpu_utilization": "NOT_MEASURED; process-average and sampled peak are recorded",
                "configured_thread_capacity_percent": configured_capacity,
                "median_cpu_percent_total": median_cpu,
                "median_configured_capacity_utilization": utilization_of_configured,
            },
            "cpu_diagnostic": cpu_flag,
            "performance_warning": bool(median_tps is not None and median_tps < 14.0),
            "historical_signal": {"codespace_generation_tps_approx": 28.0, "comparison_scope": "diagnostic signal only; hardware is not comparable"},
        })
        self._write("core_isolation", run_id, payload)
        return payload

    def _brain_once(self, query: dict[str, Any], *, hud_runtime: HudRuntime | None = None) -> dict[str, Any]:
        startup_started = time.perf_counter_ns()
        runtime: LocalBrainSSD | None = None
        try:
            runtime = LocalBrainSSD(self.root)
            startup_ms = (time.perf_counter_ns() - startup_started) / 1e6
            result = runtime.answer(query["query"], hud_runtime=hud_runtime, persist=False)
            result["startup_ms"] = startup_ms
            result["total_with_startup_ms"] = startup_ms + result["timing_ms"]["total"]
            result["query_spec"] = {key: query.get(key) for key in ("query_id", "split", "category", "expected_record_ids")}
            result["answer_status"] = "NO_KNOWLEDGE" if "no_knowledge" in result["answer"].casefold() else "ANSWER"
            result["quality"] = _score_answer(result["answer"], query, result["retrieval"]["record_ids"])
            result["error"] = None
            return result
        except BaseException as error:
            return {
                "query": query["query"], "query_spec": {"query_id": query["query_id"]}, "status": "FAIL",
                "error": {"type": _error_type(error, "startup" if runtime is None else "core"), "message": str(error)},
            }
        finally:
            if runtime is not None:
                runtime.close()

    def single_shot(self, matrix_id: str | None = None) -> dict[str, Any]:
        run_id = _run_id("single")
        payload = self._base("single_shot", run_id, matrix_id)
        selected_queries = self.queries[:3] if self.quick else self.queries
        runs = []
        for index, query in enumerate(selected_queries, 1):
            print(f"4E-W single-shot {index}/{len(selected_queries)} {query['query_id']}", flush=True)
            runs.append(self._brain_once(query))
        successful = [run for run in runs if run.get("error") is None]
        latency_values = [run.get("total_with_startup_ms") for run in runs]
        for run, flag in zip(runs, _outlier_flags(latency_values)):
            run["outlier_candidate"] = flag
            run["outlier_rule"] = "1.5*IQR on startup-inclusive total latency; preserved"
        qwen_only_query = selected_queries[0]
        qwen_prompt = (
            "Answer the technical question from your own internal knowledge. Answer concisely; "
            "if you do not know, reply exactly NO_KNOWLEDGE.\n\nUSER QUESTION:\n"
            f"{qwen_only_query['query']}\n\nANSWER:\n/no_think"
        )
        qwen_measured = _run_measured(self.backend.command(GenerationRequest(qwen_prompt, max_tokens=96, temperature=0.0)))
        qwen_answer = clean_answer(str(qwen_measured["stdout"]))
        qwen_only = {
            "query_id": qwen_only_query["query_id"], "answer": qwen_answer,
            "answer_status": "NO_KNOWLEDGE" if "no_knowledge" in qwen_answer.casefold() else "ANSWER",
            "metrics": qwen_measured["metrics"], "runtime_report": qwen_measured.get("runtime_report", {}),
            "quality": _score_answer(qwen_answer, qwen_only_query, []), "return_code": qwen_measured["return_code"],
            "stderr_sha256": hashlib.sha256(str(qwen_measured["stderr"]).encode()).hexdigest(),
        }
        first_brain = runs[0] if runs else {}
        payload.update({
            "status": "PASS" if len(successful) == len(runs) and qwen_measured["return_code"] == 0 else "FAIL",
            "runs": runs,
            "summary": {
                "startup_ms": _stats(run.get("startup_ms") for run in successful),
                "retrieval_total_ms": _stats(run["retrieval"]["timing_ms"]["retrieval_total"] for run in successful),
                "core_ms": _stats(run["generation"]["metrics"].get("latency_ms") for run in successful),
                "total_with_startup_ms": _stats(run.get("total_with_startup_ms") for run in successful),
                "active_brain_bytes": _stats(run["retrieval"].get("active_brain_bytes") for run in successful),
                "active_pages": _stats(len(run["retrieval"].get("activated_pages", [])) for run in successful),
                "context_tokens": _stats(run["retrieval"]["context"].get("estimated_tokens") for run in successful),
                "generation_tokens_per_second": _stats(run["generation"]["metrics"].get("tokens_per_second") for run in successful),
                "prompt_tokens_per_second": _stats(run["generation"]["metrics"].get("prompt_tokens_per_second") for run in successful),
            },
            "qwen_only_vs_brain_ssd": {
                "qwen_only": qwen_only,
                "brain_ssd": {
                    "query_id": first_brain.get("query_spec", {}).get("query_id"),
                    "answer": first_brain.get("answer"), "quality": first_brain.get("quality"),
                    "metrics": first_brain.get("generation", {}).get("metrics"),
                    "retrieval_cost_ms": first_brain.get("retrieval", {}).get("timing_ms", {}).get("retrieval_total"),
                },
                "objective": "Measure cost and required-fact/source support; not a superiority claim.",
            },
            "standard_rag": {"status": "NOT_RUN", "reason": "No separate Windows wrapper was added to the initial 4E-W matrix; frozen Phase 4D results remain available."},
        })
        self._write("baseline", run_id, payload)
        return payload

    def _llama_process_count(self) -> int | None:
        value = _powershell_json("(Get-Process -Name 'llama-completion' -ErrorAction SilentlyContinue | Measure-Object).Count")
        return int(value) if isinstance(value, (int, float)) else None

    def _memory_analysis(self, trace: list[dict[str, Any]]) -> dict[str, Any]:
        working = [row.get("working_set_bytes") for row in trace]
        private = [row.get("private_bytes") for row in trace]
        baseline_working = working[0] if working else None
        baseline_private = private[0] if private else None
        final_working = next((value for value in reversed(working) if value is not None), None)
        final_private = next((value for value in reversed(private) if value is not None), None)
        working_growth = final_working - baseline_working if final_working is not None and baseline_working is not None else None
        private_growth = final_private - baseline_private if final_private is not None and baseline_private is not None else None
        working_steps = [right - left for left, right in zip(working, working[1:]) if left is not None and right is not None]
        private_steps = [right - left for left, right in zip(private, private[1:]) if left is not None and right is not None]
        working_positive_rate = sum(step > 0 for step in working_steps) / len(working_steps) if working_steps else None
        private_positive_rate = sum(step > 0 for step in private_steps) / len(private_steps) if private_steps else None
        mib = 1024**2
        uncontrolled = bool(
            (working_growth is not None and working_growth > 512 * mib and (working_positive_rate or 0) >= 0.8)
            or (private_growth is not None and private_growth > 512 * mib and (private_positive_rate or 0) >= 0.8)
        )
        potential = bool(
            not uncontrolled and (
                (working_growth is not None and working_growth > 128 * mib and (working_positive_rate or 0) >= 0.7)
                or (private_growth is not None and private_growth > 128 * mib and (private_positive_rate or 0) >= 0.7)
            )
        )
        return {
            "working_set_bytes": _stats(working),
            "private_bytes": _stats(private),
            "available_system_ram_bytes": _stats(row.get("available_system_ram_bytes") for row in trace),
            "process_cpu_time_seconds": _stats(row.get("process_cpu_time_seconds") for row in trace),
            "handles": _stats(row.get("handles") for row in trace),
            "threads": _stats(row.get("threads") for row in trace),
            "working_set_growth_bytes": working_growth,
            "private_bytes_growth_bytes": private_growth,
            "working_set_positive_step_rate": working_positive_rate,
            "private_bytes_positive_step_rate": private_positive_rate,
            "classification": "UNCONTROLLED_MEMORY_GROWTH" if uncontrolled else "POTENTIAL_MEMORY_GROWTH" if potential else "STABLE_OR_BOUNDED",
            "rule": "Uncontrolled: >512 MiB final growth and >=80% positive steps; potential: >128 MiB and >=70%. No samples are discarded.",
        }

    def _session_sequence(self, mode: str, queries: list[dict[str, Any]], matrix_id: str | None) -> dict[str, Any]:
        run_id = _run_id("repeat" if mode == "repeated_query" else "session")
        payload = self._base(mode, run_id, matrix_id)
        runtime: LocalBrainSSD | None = None
        runs: list[dict[str, Any]] = []
        trace: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        children_before = self._llama_process_count()
        startup_started = time.perf_counter_ns()
        try:
            runtime = LocalBrainSSD(self.root)
            startup_ms = (time.perf_counter_ns() - startup_started) / 1e6
            trace.append(_snapshot_dict(windows_process_snapshot(os.getpid()), 0))
            for index, query in enumerate(queries, 1):
                print(f"4E-W {mode} {index}/{len(queries)} {query['query_id']}", flush=True)
                try:
                    result = runtime.answer(query["query"], persist=False)
                    result["query_spec"] = {key: query.get(key) for key in ("query_id", "split", "category", "expected_record_ids")}
                    result["answer_status"] = "NO_KNOWLEDGE" if "no_knowledge" in result["answer"].casefold() else "ANSWER"
                    result["quality"] = _score_answer(result["answer"], query, result["retrieval"]["record_ids"])
                    runs.append(result)
                except BaseException as error:
                    failure = {"query_index": index, "query_id": query["query_id"], "type": _error_type(error, "core"), "message": str(error)}
                    errors.append(failure)
                    runs.append({"query": query["query"], "query_spec": {"query_id": query["query_id"]}, "error": failure})
                trace.append(_snapshot_dict(windows_process_snapshot(os.getpid()), index))
        except BaseException as error:
            errors.append({"query_index": 0, "type": _error_type(error, "startup"), "message": str(error)})
            startup_ms = (time.perf_counter_ns() - startup_started) / 1e6
        finally:
            if runtime is not None:
                try:
                    runtime.close()
                except BaseException as error:
                    errors.append({"type": _error_type(error, "cleanup"), "message": str(error)})
        children_after = self._llama_process_count()
        memory = self._memory_analysis(trace)
        successful = [run for run in runs if "error" not in run]
        latencies = [run.get("timing_ms", {}).get("total") for run in runs]
        for run, flag in zip(runs, _outlier_flags(latencies)):
            run["outlier_candidate"] = flag
            run["outlier_rule"] = "1.5*IQR on query total latency; preserved"
        payload.update({
            "status": "PASS" if not errors and len(successful) == len(queries) and memory["classification"] != "UNCONTROLLED_MEMORY_GROWTH" and (children_after in {0, children_before}) else "FAIL",
            "startup_ms": startup_ms,
            "runs": runs,
            "memory_trace": trace,
            "memory": memory,
            "reuse": {
                "index_reused": True,
                "mmap_reused": True,
                "python_session_reused": True,
                "model_process_reused": False,
                "model_reuse_reason": "Frozen llama-completion backend is single-shot and starts one child per query.",
            },
            "latency_ms": _stats(run["timing_ms"].get("total") for run in successful),
            "ttft_ms": _stats(run["generation"]["metrics"].get("ttft_ms") for run in successful),
            "generation_tokens_per_second": _stats(run["generation"]["metrics"].get("tokens_per_second") for run in successful),
            "active_brain_bytes": _stats(run["retrieval"].get("active_brain_bytes") for run in successful),
            "context_tokens": _stats(run["retrieval"]["context"].get("estimated_tokens") for run in successful),
            "cleanup": {"llama_processes_before": children_before, "llama_processes_after": children_after, "clean": children_after in {0, children_before}},
            "errors": errors,
        })
        self._write("session", run_id, payload)
        return payload

    def session(self, matrix_id: str | None = None) -> dict[str, Any]:
        count = 3 if self.quick else 10
        queries = [self.queries[index % len(self.queries)] for index in range(count)]
        return self._session_sequence("session", queries, matrix_id)

    def repeated_query(self, matrix_id: str | None = None) -> dict[str, Any]:
        count = 3 if self.quick else 10
        return self._session_sequence("repeated_query", [self.queries[0]] * count, matrix_id)

    def sustained(self, matrix_id: str | None = None) -> dict[str, Any]:
        run_id = _run_id("sustained")
        payload = self._base("sustained", run_id, matrix_id)
        target_seconds = self.duration_minutes * 60
        runtime: LocalBrainSSD | None = None
        trace: list[dict[str, Any]] = []
        runs: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        stop = threading.Event()
        query_index = 0

        def monitor() -> None:
            while not stop.is_set():
                trace.append(_snapshot_dict(windows_process_snapshot(os.getpid()), query_index))
                stop.wait(1.0)

        started = time.monotonic()
        children_before = self._llama_process_count()
        monitor_thread: threading.Thread | None = None
        try:
            runtime = LocalBrainSSD(self.root)
            monitor_thread = threading.Thread(target=monitor, daemon=True)
            monitor_thread.start()
            while time.monotonic() - started < target_seconds:
                query = self.queries[query_index % len(self.queries)]
                query_index += 1
                print(f"4E-W sustained query={query_index} elapsed_min={(time.monotonic()-started)/60:.1f}/{self.duration_minutes:.1f}", flush=True)
                try:
                    result = runtime.answer(query["query"], persist=False)
                    runs.append({
                        "query_index": query_index, "query_id": query["query_id"], "query": query["query"],
                        "retrieval_status": result["retrieval"]["status"],
                        "answer_status": "NO_KNOWLEDGE" if "no_knowledge" in result["answer"].casefold() else "ANSWER",
                        "answer_sha256": hashlib.sha256(result["answer"].encode()).hexdigest(),
                        "active_pages": len(result["retrieval"]["activated_pages"]),
                        "active_brain_bytes": result["retrieval"]["active_brain_bytes"],
                        "record_ids": result["retrieval"]["record_ids"],
                        "context_tokens": result["retrieval"]["context"]["estimated_tokens"],
                        "timing_ms": result["timing_ms"],
                        "generation_metrics": result["generation"]["metrics"],
                    })
                except BaseException as error:
                    errors.append({"query_index": query_index, "query_id": query["query_id"], "type": _error_type(error, "core"), "message": str(error)})
        except KeyboardInterrupt:
            errors.append({"query_index": query_index, "type": "CLEANUP_ERROR", "message": "Sustained run interrupted by user"})
        except BaseException as error:
            errors.append({"query_index": query_index, "type": _error_type(error, "startup" if runtime is None else "core"), "message": str(error)})
        finally:
            stop.set()
            if monitor_thread is not None:
                monitor_thread.join(timeout=3)
            if runtime is not None:
                trace.append(_snapshot_dict(windows_process_snapshot(os.getpid()), query_index))
            if runtime is not None:
                try:
                    runtime.close()
                except BaseException as error:
                    errors.append({"type": _error_type(error, "cleanup"), "message": str(error)})
        cleanup_snapshot = _snapshot_dict(windows_process_snapshot(os.getpid()), query_index)
        actual_seconds = time.monotonic() - started
        children_after = self._llama_process_count()
        memory = self._memory_analysis(trace)
        completed_duration = actual_seconds >= target_seconds
        payload.update({
            "status": "PASS" if completed_duration and not errors and runs and memory["classification"] != "UNCONTROLLED_MEMORY_GROWTH" and children_after in {0, children_before} else "FAIL",
            "target_duration_seconds": target_seconds,
            "actual_duration_seconds": actual_seconds,
            "completed_duration": completed_duration,
            "sample_interval_seconds": 1,
            "sample_count": len(trace),
            "runs": runs,
            "memory_trace": trace,
            "memory": memory,
            "latency_ms": _stats(run["timing_ms"].get("total") for run in runs),
            "ttft_ms": _stats(run["generation_metrics"].get("ttft_ms") for run in runs),
            "generation_tokens_per_second": _stats(run["generation_metrics"].get("tokens_per_second") for run in runs),
            "cleanup": {"llama_processes_before": children_before, "llama_processes_after": children_after, "clean": children_after in {0, children_before}},
            "post_cleanup_snapshot": cleanup_snapshot,
            "errors": errors,
        })
        self._write("sustained", run_id, payload)
        return payload

    def hud_overhead(self, matrix_id: str | None = None) -> dict[str, Any]:
        run_id = _run_id("hud")
        payload = self._base("hud_overhead", run_id, matrix_id)
        query = self.queries[0]
        variants: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        for variant in ("HUD_OFF", "TELEMETRY_ONLY", "HUD_LIVE"):
            print(f"4E-W HUD overhead {variant}", flush=True)
            hud: HudRuntime | None = None
            server = None
            poll_stop = threading.Event()
            poll_count = 0

            def poll() -> None:
                nonlocal poll_count
                if server is None:
                    return
                url = f"http://127.0.0.1:{server.server_address[1]}/api/state"
                while not poll_stop.is_set():
                    try:
                        with urllib.request.urlopen(url, timeout=0.8) as response:
                            response.read()
                        poll_count += 1
                    except OSError:
                        pass
                    poll_stop.wait(1.0)

            poll_thread: threading.Thread | None = None
            try:
                if variant != "HUD_OFF":
                    hud = HudRuntime()
                    hud.state.reset(
                        data_source="PHASE 4E-W WINDOWS LIVE",
                        demo_data=False,
                        validation={"track": "PHASE 4E-W", "platform": "Windows Native", "canonical_phase4e": False, "target_8gb": "NOT_TESTED"},
                    )
                if variant == "HUD_LIVE" and hud is not None:
                    server = create_server(hud, self.root / "hud", "127.0.0.1", 0)
                    threading.Thread(target=server.serve_forever, daemon=True).start()
                    poll_thread = threading.Thread(target=poll, daemon=True)
                    poll_thread.start()
                result = self._brain_once(query, hud_runtime=hud)
                signature = {
                    "retrieval_status": result.get("retrieval", {}).get("status"),
                    "activated_pages": result.get("retrieval", {}).get("activated_pages"),
                    "record_ids": result.get("retrieval", {}).get("record_ids"),
                    "context_source_ids": result.get("retrieval", {}).get("context", {}).get("source_ids"),
                    "answer": result.get("answer"),
                }
                variants.append({
                    "variant": variant, "status": "PASS" if result.get("error") is None else "FAIL",
                    "signature": signature, "startup_ms": result.get("startup_ms"),
                    "timing_ms": result.get("timing_ms"), "generation_metrics": result.get("generation", {}).get("metrics"),
                    "hud_event_count": len(hud.bus.snapshot()) if hud else 0,
                    "hud_poll_count": poll_count,
                    "hud_state": hud.state.snapshot() if hud else None,
                    "error": result.get("error"),
                })
            except BaseException as error:
                failure = {"variant": variant, "type": _error_type(error, "hud"), "message": str(error)}
                errors.append(failure)
                variants.append({"variant": variant, "status": "FAIL", "error": failure})
            finally:
                poll_stop.set()
                if poll_thread is not None:
                    poll_thread.join(timeout=2)
                if server is not None:
                    server.shutdown()
                    server.server_close()
                if hud is not None:
                    hud.close()
        base = variants[0] if variants else {}
        base_signature = base.get("signature")
        cognitive_fields = ("retrieval_status", "activated_pages", "record_ids", "context_source_ids")
        selection_equivalent = all(
            all(variant.get("signature", {}).get(field) == (base_signature or {}).get(field) for field in cognitive_fields)
            for variant in variants[1:]
        )
        answer_equivalent = all(variant.get("signature", {}).get("answer") == (base_signature or {}).get("answer") for variant in variants[1:])
        base_latency = base.get("timing_ms", {}).get("total")
        overhead = {}
        for variant in variants:
            latency = variant.get("timing_ms", {}).get("total")
            overhead[variant["variant"]] = {
                "latency_ms": latency,
                "delta_vs_hud_off_ms": latency - base_latency if isinstance(latency, (int, float)) and isinstance(base_latency, (int, float)) else None,
                "ttft_ms": variant.get("generation_metrics", {}).get("ttft_ms"),
                "working_set_bytes_max": variant.get("generation_metrics", {}).get("working_set_bytes_max"),
                "private_bytes_max": variant.get("generation_metrics", {}).get("private_bytes_max"),
                "cpu_percent_total_average": variant.get("generation_metrics", {}).get("cpu_percent_total_average"),
            }
        payload.update({
            "status": "PASS" if not errors and all(variant["status"] == "PASS" for variant in variants) and selection_equivalent else "FAIL",
            "query_id": query["query_id"],
            "variants": variants,
            "overhead": overhead,
            "cognitive_selection_equivalent": selection_equivalent,
            "answer_equivalent": answer_equivalent,
            "interpretation": "Selection equivalence is required. Answer equality is reported separately because output execution may vary; no run is discarded.",
            "errors": errors,
        })
        self._write("hud", run_id, payload)
        return payload

    def run_all(self) -> dict[str, Any]:
        matrix_id = _run_id("matrix")
        print(json.dumps({"phase4ew_matrix_started": matrix_id, "quick": self.quick, "duration_minutes": self.duration_minutes}), flush=True)
        results = {
            "audit": self.audit(matrix_id),
            "core_isolation": self.core_isolation(matrix_id),
            "single_shot": self.single_shot(matrix_id),
            "session": self.session(matrix_id),
            "repeated_query": self.repeated_query(matrix_id),
            "sustained": self.sustained(matrix_id),
            "hud_overhead": self.hud_overhead(matrix_id),
        }
        return self._summarize(matrix_id, results)

    def _summarize(self, matrix_id: str, results: dict[str, dict[str, Any]]) -> dict[str, Any]:
        required_pass = all(result.get("status") == "PASS" for result in results.values())
        canonical_counts = (
            len(results["core_isolation"].get("runs", [])) >= 15
            and len(results["single_shot"].get("runs", [])) >= 5
            and len(results["session"].get("runs", [])) >= 10
            and len(results["repeated_query"].get("runs", [])) >= 10
            and results["sustained"].get("actual_duration_seconds", 0) >= 20 * 60
            and len(results["hud_overhead"].get("variants", [])) == 3
        )
        phase4ew_canonical = bool(not self.quick and required_pass and canonical_counts)
        memory_classes = [results[name].get("memory", {}).get("classification") for name in ("session", "sustained")]
        uncontrolled = "UNCONTROLLED_MEMORY_GROWTH" in memory_classes
        core_tps = results["core_isolation"].get("summary", {}).get("medium", {}).get("generation_tokens_per_second", {})
        single_tps_median = results["single_shot"].get("summary", {}).get("generation_tokens_per_second", {}).get("median")
        performance_warning = bool(results["core_isolation"].get("performance_warning") or (isinstance(single_tps_median, (int, float)) and single_tps_median < 14.0))
        warnings = []
        if performance_warning:
            warnings.append("PERFORMANCE_WARNING: Windows generation throughput is significantly below the historical Codespaces signal; hardware is not directly comparable.")
        if results["core_isolation"].get("cpu_diagnostic"):
            warnings.append(results["core_isolation"]["cpu_diagnostic"])
        for mode, classification in zip(("session", "sustained"), memory_classes):
            if classification == "POTENTIAL_MEMORY_GROWTH":
                warnings.append(f"POTENTIAL_MEMORY_GROWTH in {mode}")
        if not required_pass or uncontrolled:
            status = "FAIL"
        elif not phase4ew_canonical:
            status = "INCOMPLETE" if not self.quick else "PASS_WITH_WARNINGS"
        else:
            status = "PASS_WITH_WARNINGS" if warnings else "PASS"
        single_success = [run for run in results["single_shot"].get("runs", []) if run.get("error") is None]
        cognitive_ms = [run["retrieval"]["timing_ms"]["retrieval_total"] for run in single_success]
        core_ms = [run["generation"]["metrics"]["latency_ms"] for run in single_success]
        total_component = sum(cognitive_ms) + sum(core_ms)
        core_share = 100 * sum(core_ms) / total_component if total_component else None
        no_knowledge = []
        for mode in ("single_shot", "session", "repeated_query"):
            for run in results[mode].get("runs", []):
                if run.get("answer_status") == "NO_KNOWLEDGE":
                    no_knowledge.append({
                        "mode": mode, "query_id": run.get("query_spec", {}).get("query_id"),
                        "retrieval_status": run.get("retrieval", {}).get("status"), "answer_status": "NO_KNOWLEDGE",
                    })
        errors = []
        for mode, result in results.items():
            for error in result.get("errors", []):
                errors.append({"mode": mode, **error})
            for run in result.get("runs", []):
                if run.get("error"):
                    errors.append({"mode": mode, **run["error"]})
        ttft_median = results["single_shot"].get("summary", {}).get("core_ms", {}).get("median")
        actual_ttfts = [run["generation"]["metrics"].get("ttft_ms") for run in single_success if run["generation"]["metrics"].get("ttft_ms") is not None]
        ttft_median = statistics.median(actual_ttfts) if actual_ttfts else ttft_median
        speed = "FAST" if ttft_median is not None and ttft_median <= 5000 else "INTERACTIVE" if ttft_median is not None and ttft_median <= 15000 else "FUNCTIONAL"
        summary = {
            **self._base("all", matrix_id, matrix_id),
            "status": status,
            "phase4ew_canonical": phase4ew_canonical,
            "canonical": phase4ew_canonical,
            "completed_at_utc": _utc_now(),
            "required_sets": {name: result.get("status") for name, result in results.items()},
            "criteria": {"all_sets_pass": required_pass, "canonical_counts_met": canonical_counts, "uncontrolled_memory_growth": uncontrolled},
            "speed_classification": speed,
            "speed_threshold_source": "Existing Phase 4E reporting convention: INTERACTIVE TTFT <=15s, FAST <=5s; speed does not determine PASS.",
            "warnings": warnings,
            "errors": errors,
            "integrity": {
                "freeze_files": results["audit"].get("freeze_files"),
                "canonical_checksums": results["audit"].get("canonical_checksums"),
                "model": self.identity,
            },
            "core_isolation": results["core_isolation"].get("summary"),
            "cpu_diagnostic": results["core_isolation"].get("cpu_diagnostic"),
            "single_shot": results["single_shot"].get("summary"),
            "qwen_only_vs_brain_ssd": results["single_shot"].get("qwen_only_vs_brain_ssd"),
            "session": {
                "queries": len(results["session"].get("runs", [])), "latency_ms": results["session"].get("latency_ms"),
                "memory": results["session"].get("memory"), "reuse": results["session"].get("reuse"), "cleanup": results["session"].get("cleanup"),
            },
            "repeated_query": {
                "queries": len(results["repeated_query"].get("runs", [])), "latency_ms": results["repeated_query"].get("latency_ms"),
                "memory": results["repeated_query"].get("memory"), "cleanup": results["repeated_query"].get("cleanup"),
            },
            "sustained": {
                "queries": len(results["sustained"].get("runs", [])), "duration_seconds": results["sustained"].get("actual_duration_seconds"),
                "memory": results["sustained"].get("memory"), "cleanup": results["sustained"].get("cleanup"),
            },
            "hud_overhead": {
                "overhead": results["hud_overhead"].get("overhead"),
                "cognitive_selection_equivalent": results["hud_overhead"].get("cognitive_selection_equivalent"),
                "answer_equivalent": results["hud_overhead"].get("answer_equivalent"),
            },
            "active_brain": results["single_shot"].get("summary", {}).get("active_brain_bytes"),
            "context_tokens": results["single_shot"].get("summary", {}).get("context_tokens"),
            "computational_work": {
                "cognitive_selection_ms": _stats(cognitive_ms), "core_ms": _stats(core_ms),
                "core_share_percent": core_share,
                "bottleneck": "CORE" if core_share is not None and core_share >= 50 else "COGNITIVE_SELECTION",
            },
            "no_knowledge_cases": no_knowledge,
            "unsupported_metrics": results["audit"].get("limitations"),
            "standard_rag": results["single_shot"].get("standard_rag"),
            "result_run_ids": {name: result["run_id"] for name, result in results.items()},
            "phase4f_started": False,
            "phase5_or_prefetch_started": False,
        }
        immutable_path = self.results / "summaries" / f"{matrix_id}.json"
        _exclusive_json(immutable_path, summary)
        atomic_write_json(self.results / "summary.json", summary)
        markdown = self._summary_markdown(summary)
        markdown_path = self.results / "summaries" / f"{matrix_id}.md"
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        with markdown_path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(markdown)
        temporary = self.results / ".PHASE4EW_SUMMARY.md.tmp"
        temporary.write_text(markdown, encoding="utf-8", newline="\n")
        os.replace(temporary, self.results / "PHASE4EW_SUMMARY.md")
        print(json.dumps({"phase4ew_matrix_complete": matrix_id, "status": status, "phase4ew_canonical": phase4ew_canonical}, ensure_ascii=False), flush=True)
        return summary

    def _summary_markdown(self, summary: dict[str, Any]) -> str:
        session_memory = summary.get("session", {}).get("memory", {})
        core_medium = summary.get("core_isolation", {}).get("medium", {})
        work = summary.get("computational_work", {})
        hud = summary.get("hud_overhead", {})
        lines = [
            "# Phase 4E-W — Windows Native Validation", "",
            f"- Status: `{summary['status']}`", f"- Matrix: `{summary['matrix_id']}`",
            f"- phase4ew_canonical: `{str(summary['phase4ew_canonical']).lower()}`",
            "- Environment: `WINDOWS_NATIVE_FUNCTIONAL`", "- Canonical Phase 4E: `false`",
            "- TARGET_8GB: `NOT_TESTED`", "",
            "## Respostas científicas", "",
            f"1. Estabilidade: conjuntos obrigatórios = `{summary['required_sets']}`.",
            f"2. RAM/Working Set da sessão: `{session_memory.get('working_set_bytes')}`.",
            f"3. Crescimento de memória: `{session_memory.get('classification')}`, WS `{session_memory.get('working_set_growth_bytes')}`, Private `{session_memory.get('private_bytes_growth_bytes')}` bytes.",
            f"4. CPU: diagnóstico `{summary.get('cpu_diagnostic')}`.",
            f"5. Router/Gate/Storage/Context: `{work.get('cognitive_selection_ms')}` ms.",
            f"6. Core: `{work.get('core_ms')}` ms.",
            f"7. Gargalo: `{work.get('bottleneck')}`, participação `{work.get('core_share_percent')}`%.",
            f"8. Qwen puro: `{summary.get('qwen_only_vs_brain_ssd', {}).get('qwen_only', {}).get('metrics')}`.",
            f"9. HUD: `{hud.get('overhead')}`.",
            f"10. Repeated query: `{summary.get('repeated_query', {}).get('latency_ms')}`.",
            f"11. Variância single-shot: `{summary.get('single_shot', {}).get('total_with_startup_ms')}`.",
            f"12. NO_KNOWLEDGE: `{summary.get('no_knowledge_cases')}`.",
            f"13. Active Brain: `{summary.get('active_brain')}` bytes.",
            f"14. Estado final: `{summary['status']}` / velocidade `{summary['speed_classification']}`.",
            "15. Não é a Fase 4E canônica porque Windows não fornece o baseline físico Debian/TARGET_8GB exigido.", "",
            "## Core isolation medium", "", f"`{core_medium}`", "",
            "## Limitações", "", f"`{summary.get('unsupported_metrics')}`", "",
            "Nenhuma otimização, Fase 4F, Fase 5 ou prefetch foi iniciada.", "",
        ]
        return "\n".join(lines)
