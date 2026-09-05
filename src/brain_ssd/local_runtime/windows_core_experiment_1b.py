from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import random
import statistics
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Iterable

from brain_ssd.backend import GenerationRequest
from brain_ssd.local_runtime.backend import FROZEN_LLAMA_COMMIT, resolve_llama_executable
from brain_ssd.local_runtime.core_backend import PersistentCoreBackend, SubprocessPerQueryCore, generation_configuration, resolve_server_executable
from brain_ssd.local_runtime.phase4ew import _outlier_flags, _score_answer, _stats
from brain_ssd.local_runtime.pipeline import LocalBrainSSD, file_sha256
from brain_ssd.local_runtime.windows_core_experiment import _memory_stability, _result_row, _tree_digest


EXPERIMENT = "WCRE_1B"
EXPERIMENT_NAME = "WINDOWS_RUNTIME_CAUSALITY_CONTEXT_COST"
RESULTS_RELATIVE = Path("results/windows_core_runtime_1b")
MODEL_RELATIVE = Path("models/Qwen3-0.6B-Q8_0.gguf")
QA_RELATIVE = Path("benchmarks/data/phase4d_real_qa.json")
SEED = 20260821
CONDITION_A = "A_ORIGINAL_SUBPROCESS"
CONDITION_B = "B_EXPERIMENTAL_SUBPROCESS"
CONDITION_C = "C_EXPERIMENTAL_PERSISTENT"
CONDITIONS = (CONDITION_A, CONDITION_B, CONDITION_C)
CONTEXT_SIZES = (0, 128, 256, 512, 768, 1024, 1536, 2048, 3072)
FROZEN_DIRS = (
    "results/phase4d", "results/phase4e", "results/phase4ew",
    "results/windows_native", "results/windows_core_runtime",
)


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _run_id(prefix: str) -> str:
    return f"{prefix}-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-{uuid.uuid4().hex[:10]}"


def _json_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def _exclusive_json(path: Path, value: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
    return path


def _atomic_json(path: Path, value: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)
    return path


def deterministic_order(items: Iterable[Any], seed: int = SEED) -> list[Any]:
    ordered = list(items)
    random.Random(seed).shuffle(ordered)
    return ordered


def context_payload(requested_additional_tokens: int) -> str:
    """Controlled, lexically diverse context; requested size is approximate until backend tokenization."""
    if requested_additional_tokens < 0:
        raise ValueError("requested tokens must be non-negative")
    words = (
        "janela rio pedra nuvem campo livro mesa cobre jardim ponte estrela caminho "
        "cidade bosque areia planeta sinal tecido vidro madeira oceano inverno verão "
        "círculo mapa relógio folha montanha vale norte sul leste oeste claro neutro"
    ).split()
    # Diverse Portuguese words average more than one Qwen token each.  The
    # conservative factor keeps the 3072 point below the frozen 4096 context;
    # the analysis always uses the backend-reported count, never this estimate.
    target_words = round(requested_additional_tokens * 0.55)
    body = " ".join(words[index % len(words)] for index in range(target_words))
    return (
        "Leia o contexto neutro e responda somente com a palavra AZUL.\n\n"
        f"Contexto:\n{body}\n\nResposta:\n/no_think"
    )


def _linear_regression(points: list[tuple[float, float]]) -> dict[str, float | int | None]:
    if len(points) < 2:
        return {"n": len(points), "slope_ms_per_token": None, "intercept_ms": None, "r_squared": None}
    xs, ys = zip(*points)
    x_mean, y_mean = statistics.mean(xs), statistics.mean(ys)
    denominator = sum((x - x_mean) ** 2 for x in xs)
    slope = sum((x - x_mean) * (y - y_mean) for x, y in points) / denominator if denominator else 0.0
    intercept = y_mean - slope * x_mean
    total = sum((y - y_mean) ** 2 for y in ys)
    residual = sum((y - (intercept + slope * x)) ** 2 for x, y in points)
    return {"n": len(points), "slope_ms_per_token": slope, "intercept_ms": intercept, "r_squared": 1 - residual / total if total else 1.0}


def _effect(base: float | None, changed: float | None) -> dict[str, float | None]:
    delta = changed - base if isinstance(base, (int, float)) and isinstance(changed, (int, float)) else None
    return {"delta": delta, "percent_vs_base": 100 * delta / base if delta is not None and base else None}


def _metric_summary(runs: list[dict[str, Any]]) -> dict[str, Any]:
    metrics = [run["metrics"] for run in runs if run.get("status") == "PASS"]
    return {
        "runs": len(metrics),
        "ttft_ms": _stats(item.get("ttft_ms") for item in metrics),
        "total_latency_ms": _stats(item.get("latency_ms") for item in metrics),
        "prompt_eval_ms": _stats(item.get("prompt_eval_ms") for item in metrics),
        "prompt_tokens_per_second": _stats(item.get("prompt_tokens_per_second") for item in metrics),
        "generation_tokens_per_second": _stats(item.get("tokens_per_second") for item in metrics),
        "cpu_time_seconds": _stats(item.get("cpu_time_seconds") for item in metrics),
        "working_set_bytes": _stats(item.get("working_set_bytes_max") for item in metrics),
        "private_bytes": _stats(item.get("private_bytes_max") for item in metrics),
        "model_loads_per_run": _stats(item.get("model_load_ms") for item in metrics),
    }


class WindowsCoreRuntimeExperiment1B:
    def __init__(self, root: Path, *, quick: bool = False, duration_minutes: float | None = None) -> None:
        self.root = root.resolve()
        self.results = self.root / RESULTS_RELATIVE
        self.quick = quick
        self.duration_minutes = duration_minutes if duration_minutes is not None else (0.5 if quick else 5.0)
        self.model = self.root / MODEL_RELATIVE
        self.original_completion = resolve_llama_executable(self.root)
        self.experimental_completion = (self.root / "third_party/llama.cpp/build-win-persistent/bin/llama-completion.exe").resolve()
        self.server = resolve_server_executable(self.root)
        if not self.experimental_completion.is_file():
            raise FileNotFoundError(f"experimental completion target missing: {self.experimental_completion}")
        queries = json.loads((self.root / QA_RELATIVE).read_text(encoding="utf-8"))["queries"]
        by_id = {item["query_id"]: item for item in queries}
        self.queries = [by_id[key] for key in (
            "holdout_json_frames", "dev_sql_params", "holdout_python_sqlite",
            "holdout_eager_paraphrase", "holdout_unknown_near",
        )]
        self.frozen_before = {name: _tree_digest(self.root / name) for name in FROZEN_DIRS}
        self.identity = {
            "git_commit": self._git("rev-parse", "HEAD"),
            "llama_cpp_commit": self._git("rev-parse", "HEAD", cwd=self.root / "third_party/llama.cpp"),
            "model": self._file_identity(self.model),
            "condition_a": self._file_identity(self.original_completion),
            "condition_b": self._file_identity(self.experimental_completion),
            "condition_c": self._file_identity(self.server),
        }

    def _git(self, *args: str, cwd: Path | None = None) -> str | None:
        result = subprocess.run(["git", *args], cwd=cwd or self.root, capture_output=True, text=True, encoding="utf-8", errors="replace")
        return result.stdout.strip() or None

    @staticmethod
    def _file_identity(path: Path) -> dict[str, Any]:
        return {"path": str(path), "bytes": path.stat().st_size, "sha256": file_sha256(path)}

    def _base(self, mode: str, run_id: str, matrix_id: str | None = None) -> dict[str, Any]:
        config = {**generation_configuration(threads=4, context_size=4096, max_tokens=96, temperature=0.0), "seed": SEED, "quick": self.quick}
        return {
            "schema_version": 1, "experiment": EXPERIMENT, "experiment_name": EXPERIMENT_NAME,
            "phase4e_valid": False, "phase4f_started": False, "phase5_started": False,
            "prefetch_enabled": False, "mode": mode, "run_id": run_id, "matrix_id": matrix_id,
            "timestamp_utc": _utc_now(), "identity": self.identity, "configuration": config,
            "config_hash": _json_hash(config), "thermal": "NOT_MEASURED",
        }

    def _write(self, category: str, payload: dict[str, Any]) -> Path:
        path = self.results / category / f"{payload['run_id']}.json"
        _exclusive_json(path, payload)
        return path

    @staticmethod
    def _core_prompt(prompt_class: str) -> str:
        if prompt_class == "tiny":
            return "Responda apenas: AZUL\n/no_think"
        if prompt_class == "short":
            return "Answer concisely: what is the capital of France?\n/no_think"
        neutral = ("Measurement context describes a local CPU, a neutral document, stable clocks, and repeatable text. " * 110)[:8200]
        return f"Use the neutral context and answer LOCAL CPU.\n\n{neutral}\n\nAnswer:\n/no_think"

    def _core(self, condition: str) -> SubprocessPerQueryCore | PersistentCoreBackend:
        if condition == CONDITION_A:
            return SubprocessPerQueryCore(self.original_completion, self.model, threads=4, context_size=4096)
        if condition == CONDITION_B:
            return SubprocessPerQueryCore(self.experimental_completion, self.model, threads=4, context_size=4096)
        if condition == CONDITION_C:
            return PersistentCoreBackend(self.server, self.model, threads=4, context_size=4096)
        raise ValueError(condition)

    def _background(self) -> dict[str, Any]:
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=1.0)
            memory = psutil.virtual_memory()
            return {"measurement": "approximate", "cpu_utilization_percent": cpu, "cpu_idle_percent": 100 - cpu, "available_ram_bytes": memory.available}
        except Exception as error:
            return {"measurement": "NOT_MEASURED", "reason": str(error)}

    def audit(self, matrix_id: str | None = None) -> dict[str, Any]:
        payload = self._base("audit", _run_id("audit"), matrix_id)
        cache_path = self.root / "third_party/llama.cpp/build-win-persistent/CMakeCache.txt"
        prefixes = ("CMAKE_BUILD_TYPE:", "CMAKE_CXX_COMPILER:", "CMAKE_GENERATOR:", "GGML_NATIVE:", "GGML_OPENMP:", "GGML_CUDA:", "GGML_VULKAN:", "LLAMA_BUILD_EXAMPLES:", "LLAMA_BUILD_SERVER:")
        flags = {}
        for line in cache_path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith(prefixes):
                key, value = line.split("=", 1)
                flags[key] = value
        source_status = self._git("status", "--short", cwd=self.root / "third_party/llama.cpp") or ""
        checks = {
            "model_exact": self.identity["model"]["bytes"] == 639_446_688 and self.identity["model"]["sha256"] == "9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031",
            "llama_commit_exact": self.identity["llama_cpp_commit"] == FROZEN_LLAMA_COMMIT,
            "baseline_hash_exact": self.identity["condition_a"]["sha256"] == "b89490a2f25e3d573db8eff43080188d04996b958cdabfef3497a940337bf685",
            "server_hash_preserved": self.identity["condition_c"]["sha256"] == "ecf6207498a81df80ac753c60243e9a2fbdf9f046c9e8195a61a83e507cc7dc0",
            "same_experimental_build_directory": self.experimental_completion.parent == self.server.parent,
            "llama_source_clean": not bool(source_status),
        }
        payload.update({"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks, "build_flags": flags, "background_load": self._background(), "frozen_before": self.frozen_before, "platform": platform.platform(), "cpu_only": True, "threads": 4})
        self._write("audit", payload)
        return payload

    def causality(self, matrix_id: str | None = None) -> dict[str, Any]:
        payload = self._base("causality", _run_id("causality"), matrix_id)
        repetitions = 1 if self.quick else 5
        schedule = deterministic_order((condition, prompt_class, repetition) for repetition in range(1, repetitions + 1) for prompt_class in ("tiny", "short", "medium") for condition in CONDITIONS)
        cores = {condition: self._core(condition) for condition in CONDITIONS}
        runs: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        startup: dict[str, Any] = {CONDITION_A: "PER_QUERY", CONDITION_B: "PER_QUERY"}
        try:
            startup[CONDITION_C] = cores[CONDITION_C].start()
            for order, (condition, prompt_class, repetition) in enumerate(schedule, 1):
                request = GenerationRequest(prompt=self._core_prompt(prompt_class), max_tokens=96, temperature=0.0)
                try:
                    measured = cores[condition].generate(request)
                    metrics = dict(measured["metrics"])
                    metrics["cpu_time_seconds"] = metrics.get("cpu_time_seconds") if metrics.get("cpu_time_seconds") is not None else sum((metrics.get("cpu_user_seconds") or 0, metrics.get("cpu_kernel_seconds") or 0))
                    metrics["process_startup_ms"] = startup[CONDITION_C].get("process_startup_ms") if condition == CONDITION_C and order == 1 else (max(0.0, metrics["latency_ms"] - (metrics.get("backend_total_ms") or metrics["latency_ms"])) if condition != CONDITION_C else 0.0)
                    metrics["ready_time_ms"] = startup[CONDITION_C].get("persistent_core_ready_ms") if condition == CONDITION_C else None
                    runs.append({"order": order, "condition": condition, "prompt_class": prompt_class, "repetition": repetition, "status": "PASS", "metrics": metrics, "return_code": measured["return_code"], "output_sha256": hashlib.sha256(measured["stdout"].encode()).hexdigest(), "runtime_report": measured.get("runtime_report"), "samples": measured.get("samples")})
                except Exception as error:
                    failure = {"order": order, "condition": condition, "type": type(error).__name__, "message": str(error)}
                    errors.append(failure); runs.append({**failure, "status": "FAIL"})
        finally:
            for core in cores.values():
                core.close()
        by_condition = {condition: [run for run in runs if run.get("condition") == condition] for condition in CONDITIONS}
        summary = {condition: _metric_summary(rows) for condition, rows in by_condition.items()}
        medians = {condition: {metric: summary[condition][metric]["median"] for metric in ("ttft_ms", "total_latency_ms", "prompt_tokens_per_second", "generation_tokens_per_second", "cpu_time_seconds", "working_set_bytes", "private_bytes")} for condition in CONDITIONS}
        effects: dict[str, Any] = {}
        for metric in medians[CONDITION_A]:
            effects[metric] = {"build_A_to_B": _effect(medians[CONDITION_A][metric], medians[CONDITION_B][metric]), "persistence_B_to_C": _effect(medians[CONDITION_B][metric], medians[CONDITION_C][metric]), "total_A_to_C": _effect(medians[CONDITION_A][metric], medians[CONDITION_C][metric])}
        total_gain = (medians[CONDITION_A]["total_latency_ms"] or 0) - (medians[CONDITION_C]["total_latency_ms"] or 0)
        persistence_gain = (medians[CONDITION_B]["total_latency_ms"] or 0) - (medians[CONDITION_C]["total_latency_ms"] or 0)
        share = persistence_gain / total_gain if total_gain > 0 else None
        hypothesis = "SUPPORTED" if share is not None and share > 0.6 else "CONDITIONAL" if share is not None and share >= 0.4 else "REJECTED"
        first_c = next((run for run in runs if run.get("condition") == CONDITION_C and run.get("status") == "PASS"), None)
        warm_c = [run for run in by_condition[CONDITION_C] if run.get("status") == "PASS" and run is not first_c]
        payload.update({"status": "PASS" if not errors and len(runs) == 9 * repetitions else "FAIL", "hypothesis": "ENG-CORE-002", "hypothesis_status": hypothesis, "schedule_seed": SEED, "schedule": [{"order": i, "condition": c, "prompt_class": p, "repetition": r} for i, (c, p, r) in enumerate(schedule, 1)], "startup": startup, "runs": runs, "summary": summary, "medians": medians, "effects": effects, "controlled_estimate": {"basis": "median total latency; executable internals still differ", "persistence_share_of_A_to_C_gain": share, "interpretation": "gain mainly due to persistence" if hypothesis == "SUPPORTED" else "build and persistence similar" if hypothesis == "CONDITIONAL" else "gain dominated by build or inconclusive"}, "persistent_first_query": first_c, "persistent_warm_session": _metric_summary(warm_c), "errors": errors})
        self._write("causality", payload)
        return payload

    def context_cost(self, matrix_id: str | None = None) -> dict[str, Any]:
        payload = self._base("context_cost", _run_id("context-cost"), matrix_id)
        repetitions = 1 if self.quick else 5
        schedule = deterministic_order(((size, repetition) for repetition in range(1, repetitions + 1) for size in CONTEXT_SIZES), SEED + 1)
        runs: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        core = self._core(CONDITION_C)
        try:
            startup = core.start()
            warmups = []
            for index in range(2):
                warmups.append(core.generate(GenerationRequest(prompt=context_payload(128), max_tokens=8, temperature=0.0))["metrics"])
            for order, (size, repetition) in enumerate(schedule, 1):
                prompt = context_payload(size)
                try:
                    measured = core.generate(GenerationRequest(prompt=prompt, max_tokens=8, temperature=0.0))
                    metrics = dict(measured["metrics"])
                    runs.append({"order": order, "requested_additional_tokens": size, "repetition": repetition, "status": "PASS", "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(), "actual_prompt_tokens": metrics.get("prompt_tokens"), "metrics": metrics, "return_code": measured["return_code"]})
                except Exception as error:
                    failure = {"order": order, "requested_additional_tokens": size, "type": type(error).__name__, "message": str(error)}
                    errors.append(failure); runs.append({**failure, "status": "FAIL"})
        finally:
            core.close()
        outlier_count = 0
        points = []
        for size in CONTEXT_SIZES:
            selected = [run for run in runs if run.get("requested_additional_tokens") == size and run.get("status") == "PASS"]
            for metric in ("prompt_eval_ms", "ttft_ms", "cpu_time_seconds"):
                flags = _outlier_flags([run["metrics"].get(metric) for run in selected])
                for run, flag in zip(selected, flags):
                    run.setdefault("iqr_outlier_flags", {})[metric] = flag
                    outlier_count += int(flag)
            points.append({"requested_additional_tokens": size, "actual_prompt_tokens": _stats(run.get("actual_prompt_tokens") for run in selected), "prompt_eval_ms": _stats(run["metrics"].get("prompt_eval_ms") for run in selected), "ttft_ms": _stats(run["metrics"].get("ttft_ms") for run in selected), "prompt_tokens_per_second": _stats(run["metrics"].get("prompt_tokens_per_second") for run in selected), "cpu_time_seconds": _stats(run["metrics"].get("cpu_time_seconds") for run in selected), "total_latency_ms": _stats(run["metrics"].get("latency_ms") for run in selected), "working_set_bytes": _stats(run["metrics"].get("working_set_bytes_max") for run in selected), "private_bytes": _stats(run["metrics"].get("private_bytes_max") for run in selected)})
        regression_prompt = _linear_regression([(point["actual_prompt_tokens"]["median"], point["prompt_eval_ms"]["median"]) for point in points if point["actual_prompt_tokens"]["median"] is not None and point["prompt_eval_ms"]["median"] is not None])
        regression_ttft = _linear_regression([(point["actual_prompt_tokens"]["median"], point["ttft_ms"]["median"]) for point in points if point["actual_prompt_tokens"]["median"] is not None and point["ttft_ms"]["median"] is not None])
        regions = []
        by_size = {point["requested_additional_tokens"]: point for point in points}
        for low, high in ((0, 512), (512, 1024), (1024, 2048), (2048, 3072)):
            a, b = by_size[low], by_size[high]
            values = (a["actual_prompt_tokens"]["median"], b["actual_prompt_tokens"]["median"], a["prompt_eval_ms"]["median"], b["prompt_eval_ms"]["median"], a["ttft_ms"]["median"], b["ttft_ms"]["median"], a["cpu_time_seconds"]["median"], b["cpu_time_seconds"]["median"])
            if any(value is None for value in values):
                regions.append({"region": f"{low}-{high}", "status": "NOT_CALCULATED_MISSING_POINT"})
                continue
            token_delta = b["actual_prompt_tokens"]["median"] - a["actual_prompt_tokens"]["median"]
            regions.append({"region": f"{low}-{high}", "status": "CALCULATED", "actual_token_delta": token_delta, "additional_prompt_eval_ms_per_100_tokens": 100 * (b["prompt_eval_ms"]["median"] - a["prompt_eval_ms"]["median"]) / token_delta, "additional_ttft_ms_per_100_tokens": 100 * (b["ttft_ms"]["median"] - a["ttft_ms"]["median"]) / token_delta, "cpu_ms_per_100_prompt_tokens": 100_000 * (b["cpu_time_seconds"]["median"] - a["cpu_time_seconds"]["median"]) / token_delta})
        endpoint_values = (points[-1]["prompt_eval_ms"]["median"], points[0]["prompt_eval_ms"]["median"])
        endpoint_growth = endpoint_values[0] - endpoint_values[1] if all(value is not None for value in endpoint_values) else None
        hypothesis = "SUPPORTED" if isinstance(regression_prompt["slope_ms_per_token"], (int, float)) and regression_prompt["slope_ms_per_token"] > 0 and isinstance(endpoint_growth, (int, float)) and endpoint_growth >= 100 else "CONDITIONAL" if isinstance(endpoint_growth, (int, float)) and endpoint_growth > 0 else "REJECTED"
        payload.update({"status": "PASS" if not errors and len(runs) == len(CONTEXT_SIZES) * repetitions else "FAIL", "hypothesis": "ENG-CORE-003", "hypothesis_status": hypothesis, "phase_4f_context_reduction_priority": "SUPPORTED_BY_MEASUREMENT" if hypothesis == "SUPPORTED" else "NOT_ESTABLISHED", "schedule_seed": SEED + 1, "schedule": [{"order": i, "requested_additional_tokens": s, "repetition": r} for i, (s, r) in enumerate(schedule, 1)], "startup": startup, "warmups_excluded": warmups, "runs": runs, "points": points, "regression": {"prompt_eval": regression_prompt, "ttft": regression_ttft, "model": "ordinary least squares descriptive only; linearity not assumed"}, "marginal_regions": regions, "outliers": {"method": "1.5*IQR per requested size and metric; flagged only, never removed", "flag_count": outlier_count}, "errors": errors})
        self._write("context_cost", payload)
        return payload

    def brain_context_reference(self, matrix_id: str | None = None) -> dict[str, Any]:
        payload = self._base("brain_context_reference", _run_id("brain-context"), matrix_id)
        selected = self.queries[:2] if self.quick else self.queries
        schedule = deterministic_order(((condition, index) for index in range(len(selected)) for condition in CONDITIONS), SEED + 2)
        runtimes = {
            CONDITION_A: LocalBrainSSD(self.root, executable=self.original_completion, core_mode="subprocess"),
            CONDITION_B: LocalBrainSSD(self.root, executable=self.experimental_completion, core_mode="subprocess"),
            CONDITION_C: LocalBrainSSD(self.root, core_mode="persistent", persistent_executable=self.server),
        }
        runs: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        try:
            for order, (condition, index) in enumerate(schedule, 1):
                spec = selected[index]
                try:
                    row = _result_row(runtimes[condition].answer(spec["query"], persist=False), spec, order)
                    row["condition"] = condition; row["query_index"] = index; runs.append(row)
                except Exception as error:
                    failure = {"order": order, "condition": condition, "query_index": index, "type": type(error).__name__, "message": str(error)}
                    errors.append(failure); runs.append({**failure, "status": "FAIL"})
        finally:
            for runtime in runtimes.values():
                runtime.close()
        comparisons = []
        for index, spec in enumerate(selected):
            group = {run["condition"]: run for run in runs if run.get("query_index") == index and run.get("status") == "PASS"}
            if len(group) != 3:
                continue
            signatures = {}
            for condition, run in group.items():
                retrieval = run["retrieval"]
                signatures[condition] = {"page_ids": retrieval.get("page_ids") or retrieval.get("activated_pages"), "record_ids": retrieval.get("record_ids"), "source_ids": retrieval.get("source_ids"), "active_brain_bytes": retrieval.get("active_brain_bytes"), "context_sha256": run["context_sha256"], "generation_config_hash": run["generation"].get("configuration_hash")}
            equal = {key: len({_json_hash(value[key]) for value in signatures.values()}) == 1 for key in next(iter(signatures.values()))}
            quality_ok = all(run["quality"].get("source_correct") for run in group.values())
            comparisons.append({"query_id": spec["query_id"], "signatures": signatures, "equivalent": equal, "quality_sanity": quality_ok, "no_knowledge_sanity": all((run["answer_status"] == "NO_KNOWLEDGE") == (not spec.get("expected_record_ids")) for run in group.values())})
        successful = [run for run in runs if run.get("status") == "PASS"]
        summary = {condition: {"context_tokens": _stats(run["generation"]["metrics"].get("prompt_tokens") for run in successful if run["condition"] == condition), "prompt_eval_ms": _stats(run["generation"]["metrics"].get("prompt_eval_ms") for run in successful if run["condition"] == condition), "ttft_ms": _stats(run["generation"]["metrics"].get("ttft_ms") for run in successful if run["condition"] == condition), "generation_eval_ms": _stats(run["generation"]["metrics"].get("generation_eval_ms") for run in successful if run["condition"] == condition), "total_latency_ms": _stats(run["timing_ms"].get("total") for run in successful if run["condition"] == condition), "active_brain_bytes": _stats(run["retrieval"].get("active_brain_bytes") for run in successful if run["condition"] == condition)} for condition in CONDITIONS}
        all_equal = bool(comparisons) and all(all(item["equivalent"].values()) for item in comparisons)
        payload.update({"status": "PASS" if not errors and all_equal else "FAIL", "schedule_seed": SEED + 2, "runs": runs, "comparisons": comparisons, "summary": summary, "retrieval_equivalent": all_equal, "active_brain_equivalent": all(item["equivalent"]["active_brain_bytes"] for item in comparisons), "context_hash_equivalent": all(item["equivalent"]["context_sha256"] for item in comparisons), "quality_sanity": all(item["quality_sanity"] for item in comparisons), "no_knowledge_sanity": all(item["no_knowledge_sanity"] for item in comparisons), "real_context_not_trimmed": True, "reference_median_context_tokens": 1963, "errors": errors})
        self._write("brain_context_reference", payload)
        return payload

    def sustained(self, matrix_id: str | None = None) -> dict[str, Any]:
        payload = self._base("sustained", _run_id("sustained"), matrix_id)
        target = self.duration_minutes * 60
        started = time.monotonic(); runs = []; errors = []
        runtime = LocalBrainSSD(self.root, core_mode="persistent", persistent_executable=self.server)
        try:
            index = 0
            while time.monotonic() - started < target:
                spec = self.queries[index % len(self.queries)]; index += 1
                try:
                    runs.append(_result_row(runtime.answer(spec["query"], persist=False), spec, index))
                except Exception as error:
                    errors.append({"index": index, "type": type(error).__name__, "message": str(error)}); break
        finally:
            runtime.close()
        actual = time.monotonic() - started
        memory = _memory_stability(runs)
        payload.update({"status": "PASS" if not errors and actual >= target and memory["classification"] != "UNBOUNDED_GROWTH" else "FAIL", "target_duration_seconds": target, "actual_duration_seconds": actual, "queries": len(runs), "runs": runs, "memory": memory, "wcre_1_reference": {"summary_digest_before": self.frozen_before["results/windows_core_runtime"], "canonical_sustained_minutes": 20}, "errors": errors})
        self._write("sustained", payload)
        return payload

    @staticmethod
    def _estimate_at(points: list[dict[str, Any]], requested: int, metric: str) -> float | None:
        exact = next((point for point in points if point["requested_additional_tokens"] == requested), None)
        return exact[metric]["median"] if exact else None

    def summarize(self, matrix_id: str, results: dict[str, dict[str, Any]]) -> dict[str, Any]:
        frozen_after = {name: _tree_digest(self.root / name) for name in FROZEN_DIRS}
        frozen_preserved = self.frozen_before == frozen_after
        context = results["context_cost"]
        brain = results["brain_context_reference"]
        cost_512 = self._estimate_at(context["points"], 512, "prompt_eval_ms")
        real_cost = brain["summary"][CONDITION_C]["prompt_eval_ms"]["median"]
        theoretical = {"label": "THEORETICAL_ONLY", "brain_reference_tokens": 1963, "synthetic_512_prompt_eval_ms": cost_512, "real_persistent_prompt_eval_ms": real_cost, "potential_prompt_eval_savings_ms": real_cost - cost_512 if real_cost is not None and cost_512 is not None else None, "quality_preservation": "NOT_TESTED; no future gain promised"}
        canonical = not self.quick and len(results["causality"]["runs"]) >= 45 and len(context["runs"]) >= 45 and results["sustained"]["actual_duration_seconds"] >= 300
        all_pass = all(item["status"] == "PASS" for item in results.values())
        status = "PASS" if all_pass and canonical and frozen_preserved else "PASS_QUICK_NON_CANONICAL" if all_pass and self.quick and frozen_preserved else "FAIL"
        summary = {**self._base("all", matrix_id, matrix_id), "completed_at_utc": _utc_now(), "status": status, "operational_status": status, "canonical_experiment": canonical, "eng_core_002": results["causality"]["hypothesis_status"], "eng_core_003": context["hypothesis_status"], "phase_4f_context_reduction_priority": context["phase_4f_context_reduction_priority"], "causality": {"medians": results["causality"]["medians"], "effects": results["causality"]["effects"], "controlled_estimate": results["causality"]["controlled_estimate"]}, "context_cost": {"points": context["points"], "regression": context["regression"], "marginal_regions": context["marginal_regions"], "outliers": context["outliers"]}, "brain_context_reference": {key: brain[key] for key in ("summary", "retrieval_equivalent", "active_brain_equivalent", "context_hash_equivalent", "quality_sanity", "no_knowledge_sanity", "real_context_not_trimmed")}, "theoretical_estimate": theoretical, "sustained": {"queries": results["sustained"]["queries"], "actual_duration_seconds": results["sustained"]["actual_duration_seconds"], "memory": results["sustained"]["memory"]}, "frozen_before": self.frozen_before, "frozen_after": frozen_after, "frozen_results_preserved": frozen_preserved, "default_core_mode_changed": False, "phase4f_started": False, "phase5_started": False, "prefetch_enabled": False, "result_run_ids": {name: item["run_id"] for name, item in results.items()}}
        immutable = self.results / "summary" / f"{matrix_id}.json"
        _exclusive_json(immutable, summary)
        _atomic_json(self.results / "summary.json", summary)
        markdown = self._summary_markdown(summary)
        immutable.with_suffix(".md").write_text(markdown, encoding="utf-8", newline="\n")
        temporary = self.results / ".SUMMARY.md.tmp"; temporary.write_text(markdown, encoding="utf-8", newline="\n"); os.replace(temporary, self.results / "SUMMARY.md")
        return summary

    def run_all(self) -> dict[str, Any]:
        matrix_id = _run_id("matrix")
        results = {"audit": self.audit(matrix_id), "causality": self.causality(matrix_id), "context_cost": self.context_cost(matrix_id), "brain_context_reference": self.brain_context_reference(matrix_id), "sustained": self.sustained(matrix_id)}
        return self.summarize(matrix_id, results)

    def _summary_markdown(self, summary: dict[str, Any]) -> str:
        c = summary["causality"]["medians"]
        lines = ["# WCRE-1B — Runtime Causality + Context Cost", "", f"- Status: `{summary['status']}`", f"- ENG-CORE-002: `{summary['eng_core_002']}`", f"- ENG-CORE-003: `{summary['eng_core_003']}`", f"- Frozen results preserved: `{summary['frozen_results_preserved']}`", "", "## Causality medians", "", "| Metric | A Original | B Experimental | C Persistent |", "|---|---:|---:|---:|"]
        for metric in ("ttft_ms", "total_latency_ms", "prompt_tokens_per_second", "generation_tokens_per_second", "cpu_time_seconds", "working_set_bytes", "private_bytes"):
            lines.append(f"| {metric} | {c[CONDITION_A][metric]} | {c[CONDITION_B][metric]} | {c[CONDITION_C][metric]} |")
        lines += ["", "## Context cost", "", "| Requested | Actual tokens | Prompt eval ms | TTFT ms | CPU seconds |", "|---:|---:|---:|---:|---:|"]
        for point in summary["context_cost"]["points"]:
            lines.append(f"| {point['requested_additional_tokens']} | {point['actual_prompt_tokens']['median']} | {point['prompt_eval_ms']['median']} | {point['ttft_ms']['median']} | {point['cpu_time_seconds']['median']} |")
        lines += ["", f"Theoretical estimate: `{summary['theoretical_estimate']}`", "", "WCRE-1B only measures. Phase 4F, Phase 5 and prefetch were not started.", ""]
        return "\n".join(lines)
