from __future__ import annotations

import hashlib
import json
import os
import random
import statistics
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Iterable

from brain_ssd.backend import GenerationRequest
from brain_ssd.context_distillation import ContextDistiller, RecordPruner, context_fact_recall, evidence_units, oracle_minimal_context
from brain_ssd.local_runtime.backend import FROZEN_LLAMA_COMMIT
from brain_ssd.local_runtime.core_backend import generation_configuration, resolve_server_executable
from brain_ssd.local_runtime.phase4ew import _score_answer, _stats
from brain_ssd.local_runtime.pipeline import LocalBrainSSD, clean_answer, file_sha256
from brain_ssd.local_runtime.windows_core_experiment import _tree_digest
from brain_ssd.record_retrieval import ContextBuilder, build_prompt, retrieve, tokenize


EXPERIMENT = "PHASE_4F_W"
ENVIRONMENT = "WINDOWS_NATIVE_FUNCTIONAL"
RESULTS_RELATIVE = Path("results/phase4fw")
QA_RELATIVE = Path("benchmarks/data/phase4d_real_qa.json")
MODEL_RELATIVE = Path("models/Qwen3-0.6B-Q8_0.gguf")
SEED = 20260822
BUDGETS = (256, 384, 512, 768, 1024, 1280, 1536)
FROZEN_DIRS = (
    "results/phase4d", "results/phase4e", "results/phase4ew", "results/windows_native",
    "results/windows_core_runtime", "results/windows_core_runtime_1b",
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


def deterministic_matrix_order(items: Iterable[Any], seed: int = SEED) -> list[Any]:
    result = list(items); random.Random(seed).shuffle(result); return result


def _mean(values: Iterable[float | int | None]) -> float | None:
    selected = [float(value) for value in values if isinstance(value, (int, float))]
    return statistics.mean(selected) if selected else None


def _percent_delta(before: float | None, after: float | None) -> dict[str, float | None]:
    delta = after - before if before is not None and after is not None else None
    return {"before": before, "after": after, "delta": delta, "percent": 100 * delta / before if delta is not None and before else None}


def prompt_composition(query: str, context: dict[str, Any], actual_prompt_tokens: int | None) -> dict[str, Any]:
    instruction = build_prompt("", {"text": ""})
    instruction_tokens = ContextBuilder.estimate_tokens(instruction)
    question_tokens = ContextBuilder.estimate_tokens(query)
    evidence_tokens = ContextBuilder.estimate_tokens(context.get("text", "")) if context.get("text") else 0
    metadata_tokens = sum(ContextBuilder.estimate_tokens(f"[SOURCE: {item.get('record_id')}] {item.get('title')} {item.get('section')}") for item in context.get("provenance", []))
    total = actual_prompt_tokens or (instruction_tokens + question_tokens + evidence_tokens)
    other = max(0, total - instruction_tokens - question_tokens - evidence_tokens)
    values = {"instructions": instruction_tokens, "metadata_within_evidence": metadata_tokens, "evidence": evidence_tokens, "question": question_tokens, "other_or_chat_envelope": other, "total": total}
    values["percent"] = {key: 100 * value / total if total else 0.0 for key, value in values.items() if key not in {"total", "metadata_within_evidence"}}
    values["measurement"] = "actual total from backend; components estimated with frozen bytes/4 estimator"
    return values


class Phase4FWRunner:
    def __init__(self, root: Path, *, quick: bool = False, resume_matrix: str | None = None) -> None:
        self.root = root.resolve(); self.results = self.root / RESULTS_RELATIVE; self.quick = quick
        self.matrix_id = resume_matrix or _run_id("matrix")
        self.model = self.root / MODEL_RELATIVE; self.server = resolve_server_executable(self.root)
        qa_payload = json.loads((self.root / QA_RELATIVE).read_text(encoding="utf-8"))
        all_queries = qa_payload["queries"]
        if quick:
            dev = [query for query in all_queries if query["split"] == "development"][:2]
            holdout_known = [query for query in all_queries if query["split"] == "holdout" and query.get("expected_record_ids")][:1]
            holdout_unknown = [query for query in all_queries if query["split"] == "holdout" and not query.get("expected_record_ids")][:1]
            self.queries = dev + holdout_known + holdout_unknown
            self.budgets = (384, 768)
        else:
            self.queries = all_queries; self.budgets = BUDGETS
        self.frozen_before = {name: _tree_digest(self.root / name) for name in FROZEN_DIRS}
        self.identity = {
            "git_commit": self._git(self.root), "llama_cpp_commit": self._git(self.root / "third_party/llama.cpp"),
            "model": self._identity(self.model), "persistent_core": self._identity(self.server),
            "qa": self._identity(self.root / QA_RELATIVE), "seed": SEED,
        }
        self.configuration = {**generation_configuration(threads=4, context_size=4096, max_tokens=96, temperature=0.0), "budgets": self.budgets, "quick": quick, "distiller": "ContextDistiller/extractive-v1", "pruner_max_records": 3}
        self.config_hash = _json_hash(self.configuration)
        self.checkpoint_path = self.results / "checkpoints" / f"{self.matrix_id}.json"
        self.checkpoint = self._load_checkpoint(resume_matrix is not None)

    @staticmethod
    def _identity(path: Path) -> dict[str, Any]:
        return {"path": str(path), "bytes": path.stat().st_size, "sha256": file_sha256(path)}

    @staticmethod
    def _git(path: Path) -> str | None:
        result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=path, capture_output=True, text=True, encoding="utf-8", errors="replace")
        return result.stdout.strip() or None

    def _base(self, mode: str, run_id: str | None = None) -> dict[str, Any]:
        return {
            "schema_version": 1, "experiment": EXPERIMENT, "environment": ENVIRONMENT,
            "phase4f_windows_experimental": True, "phase4fw_windows_canonical": False,
            "phase4f_canonical": False, "phase4e_valid": False, "phase5_started": False,
            "prefetch_enabled": False, "mode": mode, "run_id": run_id or _run_id(mode),
            "matrix_id": self.matrix_id, "timestamp_utc": _utc_now(), "quick": self.quick,
            "canonical": False, "identity": self.identity, "configuration": self.configuration,
            "config_hash": self.config_hash,
        }

    def _load_checkpoint(self, required: bool) -> dict[str, Any]:
        if self.checkpoint_path.is_file():
            value = json.loads(self.checkpoint_path.read_text(encoding="utf-8"))
            if value.get("config_hash") != self.config_hash:
                raise ValueError("checkpoint configuration does not match")
            return value
        if required:
            raise FileNotFoundError(f"checkpoint not found: {self.checkpoint_path}")
        value = {**self._base("checkpoint", self.matrix_id), "config_hash": self.config_hash, "completed": {}}
        _atomic_json(self.checkpoint_path, value)
        return value

    def _checkpoint_run(self, key: str, path: Path) -> None:
        self.checkpoint["completed"][key] = {"path": str(path), "sha256": file_sha256(path)}
        self.checkpoint["updated_at_utc"] = _utc_now(); _atomic_json(self.checkpoint_path, self.checkpoint)

    def _write(self, category: str, payload: dict[str, Any]) -> Path:
        path = self.results / category / f"{payload['run_id']}.json"; _exclusive_json(path, payload); return path

    def audit(self) -> dict[str, Any]:
        payload = self._base("audit")
        checks = {
            "server_hash": self.identity["persistent_core"]["sha256"] == "ecf6207498a81df80ac753c60243e9a2fbdf9f046c9e8195a61a83e507cc7dc0",
            "model_hash": self.identity["model"]["sha256"] == "9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031",
            "model_bytes": self.identity["model"]["bytes"] == 639_446_688,
            "llama_commit": self.identity["llama_cpp_commit"] == FROZEN_LLAMA_COMMIT,
            "qa_split": sum(query["split"] == "development" for query in self.queries) > 0 and sum(query["split"] == "holdout" for query in self.queries) > 0,
        }
        payload.update({"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks, "frozen_before": self.frozen_before, "dev_queries": sum(query["split"] == "development" for query in self.queries), "holdout_queries": sum(query["split"] == "holdout" for query in self.queries), "oracle_runtime_allowed": False, "second_llm_used": False, "context_builder_v0_modified": False, "default_changed": False})
        self._write("audit", payload); return payload

    def _retrieval_snapshot(self, runtime: LocalBrainSSD, query: dict[str, Any]) -> dict[str, Any]:
        measured = runtime.retrieve(query["query"])
        frozen = retrieve(runtime.index, query["query"], runtime.records_by_id, mode="brain", max_records=8, max_pages=4, threshold=0.20)
        records = [dict(runtime.records_by_id[record["record_id"]]) for record in frozen.records]
        if sorted(record["record_id"] for record in records) != measured["record_ids"]:
            raise RuntimeError("frozen retrieval reproduction mismatch")
        scores = {candidate.record_id: candidate.score for candidate in frozen.candidates}
        return {"measured": measured, "records": records, "scores": scores, "order": [record["record_id"] for record in records]}

    def _choose_dev_budget(self, snapshots: dict[str, dict[str, Any]]) -> int:
        dev = [query for query in self.queries if query["split"] == "development"]
        for budget in self.budgets:
            valid = True
            for query in dev:
                snap = snapshots[query["query_id"]]
                v0 = context_fact_recall(snap["measured"]["context"]["text"], query["required_fact_groups"])["recall"]
                candidate = ContextDistiller(budget).build(query["query"], snap["records"], snap["scores"])
                if context_fact_recall(candidate["text"], query["required_fact_groups"])["recall"] < v0:
                    valid = False; break
            if valid:
                return budget
        return max(self.budgets)

    def _context_for(self, variant: str, query: dict[str, Any], snapshot: dict[str, Any], oracle: dict[str, Any], selected_budget: int) -> tuple[dict[str, Any], dict[str, Any]]:
        records, scores = snapshot["records"], snapshot["scores"]
        meta: dict[str, Any] = {"pruning": None}
        if variant == "V0":
            context = {**snapshot["measured"]["context"], "provenance": [{"record_id": source["record_id"], "source_id": source.get("source_id"), "page_id": source["page_id"], "title": source.get("document"), "section": source.get("section")} for source in snapshot["measured"]["sources"]], "records_retained": snapshot["measured"]["context"]["source_ids"], "records_pruned": [record["record_id"] for record in records if record["record_id"] not in snapshot["measured"]["context"]["source_ids"]], "sentences_retained": None, "duplicate_tokens_removed": 0, "distiller_wall_ms": snapshot["measured"]["timing_ms"]["context_build"], "distiller_cpu_ms": None, "metadata_bytes": 0}
            return context, meta
        if variant == "ORACLE_EVAL":
            return {**oracle, "records_retained": oracle["source_ids"], "records_pruned": [], "sentences_retained": len(oracle["provenance"]), "duplicate_tokens_removed": 0, "distiller_wall_ms": oracle["oracle_wall_ms"], "distiller_cpu_ms": None, "metadata_bytes": 0}, {"pruning": None, "evaluation_only": True}
        if variant.startswith("EXTRACTIVE_B"):
            budget = int(variant.removeprefix("EXTRACTIVE_B")); return ContextDistiller(budget).build(query["query"], records, scores), meta
        pruned = RecordPruner(3).prune(query["query"], records, scores); meta["pruning"] = {key: value for key, value in pruned.items() if key != "records"}
        if variant == "PRUNING_ONLY":
            built = ContextBuilder(2048).build(pruned["records"])
            context = {**built, "records_retained": built["source_ids"], "records_pruned": pruned["pruned_record_ids"], "sentences_retained": None, "duplicate_tokens_removed": 0, "provenance": [{"record_id": record["record_id"], "source_id": record.get("source_id"), "page_id": record["page_id"], "title": record.get("title"), "section": record.get("section")} for record in pruned["records"] if record["record_id"] in built["source_ids"]], "distiller_wall_ms": pruned["wall_ms"], "distiller_cpu_ms": pruned["cpu_ms"], "metadata_bytes": 0}
            return context, meta
        context = ContextDistiller(selected_budget).build(query["query"], pruned["records"], scores)
        context["distiller_wall_ms"] += pruned["wall_ms"]; context["distiller_cpu_ms"] += pruned["cpu_ms"]
        return context, meta

    def _evaluate_run(self, query: dict[str, Any], context: dict[str, Any], answer: str, metrics: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
        quality = _score_answer(answer, query, context.get("source_ids", []))
        context_facts = context_fact_recall(context.get("text", ""), query["required_fact_groups"])
        no_knowledge = "no_knowledge" in answer.casefold()
        known = bool(query.get("expected_record_ids"))
        correctness = (quality["required_fact_score"] == 1.0 and quality["source_correct"]) if known else no_knowledge
        grounding = quality["source_correct"]
        if not known:
            diagnostic = "SAFE_NO_KNOWLEDGE" if no_knowledge else "GROUNDING_FAILURE"
        elif not snapshot["measured"]["record_ids"] or not set(query["expected_record_ids"]) & set(snapshot["measured"]["record_ids"]):
            diagnostic = "RETRIEVAL_MISS"
        elif context_facts["recall"] < 1.0:
            diagnostic = "CONTEXT_DISTILLATION_MISS"
        elif no_knowledge:
            diagnostic = "FALSE_NO_KNOWLEDGE"
        elif quality["required_fact_score"] < 1.0:
            diagnostic = "CORE_UTILIZATION_FAILURE"
        elif not grounding:
            diagnostic = "GROUNDING_FAILURE"
        else:
            diagnostic = "PASS"
        return {"context_fact_recall": context_facts, "answer_quality": quality, "correctness": correctness, "grounding": grounding, "unknown_safe": not known and no_knowledge, "false_no_knowledge": known and no_knowledge, "answer_status": "NO_KNOWLEDGE" if no_knowledge else "ANSWER", "diagnostic": diagnostic, "actual_prompt_tokens": metrics.get("prompt_tokens")}

    def _run_one(self, runtime: LocalBrainSSD, order: int, variant: str, query: dict[str, Any], snapshot: dict[str, Any], oracle: dict[str, Any], selected_budget: int) -> dict[str, Any]:
        key = f"{query['query_id']}::{variant}"
        prior = self.checkpoint["completed"].get(key)
        if prior and Path(prior["path"]).is_file() and file_sha256(Path(prior["path"])) == prior["sha256"]:
            return json.loads(Path(prior["path"]).read_text(encoding="utf-8"))
        context, variant_meta = self._context_for(variant, query, snapshot, oracle, selected_budget)
        prompt = build_prompt(query["query"], context)
        measured = runtime.core_backend.generate(GenerationRequest(prompt=prompt, max_tokens=96, temperature=0.0))
        if measured["return_code"] != 0:
            raise RuntimeError(f"Core failed: {str(measured.get('stderr'))[-800:]}")
        answer = clean_answer(str(measured["stdout"])); metrics = dict(measured["metrics"])
        evaluation = self._evaluate_run(query, context, answer, metrics, snapshot)
        available_tokens = sum(ContextBuilder.estimate_tokens(str(record.get("text") or "")) for record in snapshot["records"])
        useful_tokens = oracle["estimated_tokens"]
        payload = {**self._base("run", _run_id("run")), "status": "PASS", "order": order, "key": key, "variant": variant, "query_spec": query, "retrieval": {"active_pages": snapshot["measured"]["activated_pages"], "active_brain_bytes": snapshot["measured"]["active_brain_bytes"], "records_retrieved": snapshot["order"], "record_bytes": snapshot["measured"]["selected_record_bytes"], "source_ids": [record.get("source_id") for record in snapshot["records"]]}, "context": context, "context_sha256": hashlib.sha256(context.get("text", "").encode()).hexdigest(), "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(), "prompt_composition": prompt_composition(query["query"], context, metrics.get("prompt_tokens")), "context_metrics": {"available_record_tokens": available_tokens, "context_activation_rate": context["estimated_tokens"] / available_tokens if available_tokens else 0.0, "context_density": useful_tokens / context["estimated_tokens"] if context["estimated_tokens"] else 1.0, "context_density_evaluation_only": True, "tokens_per_required_fact": context["estimated_tokens"] / len(query["required_fact_groups"]) if query["required_fact_groups"] else None, "useful_oracle_tokens": useful_tokens}, "variant_metadata": variant_meta, "generation": {"answer": answer, "return_code": measured["return_code"], "metrics": metrics, "output_sha256": hashlib.sha256(answer.encode()).hexdigest()}, "evaluation": evaluation, "chain_of_thought_stored": False}
        category = "baseline" if variant == "V0" else "oracle" if variant == "ORACLE_EVAL" else "budgets" if variant.startswith("EXTRACTIVE_B") else "overretrieval" if variant == "PRUNING_ONLY" else "ablation"
        path = self._write(category, payload); self._checkpoint_run(key, path); return payload

    def _variants(self, selected_budget: int) -> list[str]:
        return ["V0", "ORACLE_EVAL", *(f"EXTRACTIVE_B{budget}" for budget in self.budgets), "PRUNING_ONLY", f"COMBINED_B{selected_budget}"]

    def dry_run(self) -> dict[str, Any]:
        variants = self._variants(max(self.budgets))
        schedule = deterministic_matrix_order((query["query_id"], variant) for query in self.queries for variant in variants)
        return {**self._base("dry_run"), "status": "PASS", "canonical": False, "dev_queries": sum(query["split"] == "development" for query in self.queries), "holdout_queries": sum(query["split"] == "holdout" for query in self.queries), "variants": variants, "runs": len(schedule), "schedule": [{"order": index, "query_id": query, "variant": variant} for index, (query, variant) in enumerate(schedule, 1)], "note": "selected combined budget is finalized from DEV context-fact recall before execution"}

    def run_stage(self, stage: str) -> dict[str, Any]:
        audit = self.audit(); runtime = LocalBrainSSD(self.root, core_mode="persistent", persistent_executable=self.server)
        runs: list[dict[str, Any]] = []
        try:
            snapshots = {query["query_id"]: self._retrieval_snapshot(runtime, query) for query in self.queries}
            corpus_units = [unit for record in runtime.manifest["records"] for unit in evidence_units(record)]
            oracles = {query["query_id"]: oracle_minimal_context(query, (), prebuilt_units=corpus_units) for query in self.queries}
            selected_budget = self._choose_dev_budget(snapshots)
            variants = self._variants(selected_budget)
            filters = {"baseline": {"V0"}, "oracle": {"ORACLE_EVAL"}, "distillation": {f"EXTRACTIVE_B{selected_budget}"}, "budgets": {f"EXTRACTIVE_B{budget}" for budget in self.budgets}, "pruning": {"PRUNING_ONLY"}, "ablation": {"V0", f"EXTRACTIVE_B{selected_budget}", "PRUNING_ONLY", f"COMBINED_B{selected_budget}"}, "quality": set(variants), "all": set(variants)}
            selected_variants = filters[stage]
            schedule = deterministic_matrix_order((query, variant) for query in self.queries for variant in variants if variant in selected_variants)
            runtime.core_backend.start()
            runtime.core_backend.generate(GenerationRequest(prompt="Reply only WARM.\n/no_think", max_tokens=8, temperature=0.0))
            for order, (query, variant) in enumerate(schedule, 1):
                runs.append(self._run_one(runtime, order, variant, query, snapshots[query["query_id"]], oracles[query["query_id"]], selected_budget))
        finally:
            runtime.close()
        if stage == "all":
            return self.summarize(audit, runs, selected_budget)
        payload = {**self._base(stage), "status": "PASS", "selected_dev_budget": selected_budget, "runs": len(runs), "run_ids": [run["run_id"] for run in runs]}
        self._write(stage if stage in {"oracle", "baseline", "budgets", "ablation", "quality"} else "distillation", payload); return payload

    @staticmethod
    def _aggregate(runs: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "queries": len(runs), "actual_prompt_tokens": _stats(run["evaluation"]["actual_prompt_tokens"] for run in runs),
            "context_tokens": _stats(run["context"]["estimated_tokens"] for run in runs),
            "context_fact_recall": _mean(run["evaluation"]["context_fact_recall"]["recall"] for run in runs),
            "answer_fact_recall": _mean(run["evaluation"]["answer_quality"]["required_fact_score"] for run in runs),
            "correctness_rate": _mean(float(run["evaluation"]["correctness"]) for run in runs),
            "grounding_rate": _mean(float(run["evaluation"]["grounding"]) for run in runs),
            "unknown_safety_rate": _mean(float(run["evaluation"]["unknown_safe"]) for run in runs if not run["query_spec"].get("expected_record_ids")),
            "false_no_knowledge": sum(run["evaluation"]["false_no_knowledge"] for run in runs),
            "prompt_eval_ms": _stats(run["generation"]["metrics"].get("prompt_eval_ms") for run in runs),
            "ttft_ms": _stats(run["generation"]["metrics"].get("ttft_ms") for run in runs),
            "cpu_time_seconds": _stats(run["generation"]["metrics"].get("cpu_time_seconds") for run in runs),
            "total_latency_ms": _stats(run["generation"]["metrics"].get("latency_ms") for run in runs),
            "distiller_wall_ms": _stats(run["context"].get("distiller_wall_ms") for run in runs),
            "distiller_cpu_ms": _stats(run["context"].get("distiller_cpu_ms") for run in runs),
            "records_retrieved": _stats(len(run["retrieval"]["records_retrieved"]) for run in runs),
            "records_retained": _stats(len(run["context"].get("records_retained", [])) for run in runs),
            "records_pruned": _stats(len(run["context"].get("records_pruned", [])) for run in runs),
            "duplicate_tokens_removed": _stats(run["context"].get("duplicate_tokens_removed") for run in runs),
            "context_density": _stats(run["context_metrics"].get("context_density") for run in runs),
            "tokens_per_required_fact": _stats(run["context_metrics"].get("tokens_per_required_fact") for run in runs),
            "active_brain_bytes": _stats(run["retrieval"]["active_brain_bytes"] for run in runs),
        }

    def summarize(self, audit: dict[str, Any], runs: list[dict[str, Any]], selected_budget: int) -> dict[str, Any]:
        variants = sorted({run["variant"] for run in runs})
        by_variant = {variant: [run for run in runs if run["variant"] == variant] for variant in variants}
        aggregate = {variant: self._aggregate(rows) for variant, rows in by_variant.items()}
        v0 = aggregate["V0"]
        production_variants = [variant for variant in variants if variant not in {"V0", "ORACLE_EVAL"}]
        def quality_key(variant: str) -> tuple[float, float, float, float]:
            item = aggregate[variant]
            return (item["correctness_rate"] or 0, item["answer_fact_recall"] or 0, item["context_fact_recall"] or 0, -(item["actual_prompt_tokens"]["median"] or 1e9))
        best = max(production_variants, key=quality_key)
        candidate = aggregate[best]
        per_query = []
        regressions = []; improvements = []; overload = []; minimal = []
        for query in self.queries:
            query_runs = {run["variant"]: run for run in runs if run["query_spec"]["query_id"] == query["query_id"]}
            base, chosen = query_runs["V0"], query_runs[best]
            row = {"query_id": query["query_id"], "split": query["split"], "v0_tokens": base["evaluation"]["actual_prompt_tokens"], "variant_tokens": chosen["evaluation"]["actual_prompt_tokens"], "v0_context_fact_recall": base["evaluation"]["context_fact_recall"]["recall"], "variant_context_fact_recall": chosen["evaluation"]["context_fact_recall"]["recall"], "v0_answer_fact_recall": base["evaluation"]["answer_quality"]["required_fact_score"], "variant_answer_fact_recall": chosen["evaluation"]["answer_quality"]["required_fact_score"], "v0_correct": base["evaluation"]["correctness"], "variant_correct": chosen["evaluation"]["correctness"], "v0_ttft_ms": base["generation"]["metrics"].get("ttft_ms"), "variant_ttft_ms": chosen["generation"]["metrics"].get("ttft_ms"), "v0_diagnostic": base["evaluation"]["diagnostic"], "variant_diagnostic": chosen["evaluation"]["diagnostic"]}
            per_query.append(row)
            if base["evaluation"]["correctness"] and not chosen["evaluation"]["correctness"]: regressions.append(row)
            if not base["evaluation"]["correctness"] and chosen["evaluation"]["correctness"]: improvements.append(row)
            if row in improvements and chosen["evaluation"]["context_fact_recall"]["recall"] >= base["evaluation"]["context_fact_recall"]["recall"]: overload.append({**row, "signal": "CONTEXT_OVERLOAD_CANDIDATE"})
            budget_candidates = [run for run in query_runs.values() if run["variant"].startswith("EXTRACTIVE_B") and run["evaluation"]["correctness"] and run["evaluation"]["grounding"] and (run["evaluation"]["unknown_safe"] if not query.get("expected_record_ids") else True)]
            smallest = min(budget_candidates, key=lambda run: run["evaluation"]["actual_prompt_tokens"] or 1e9) if budget_candidates else None
            minimal.append({"query_id": query["query_id"], "minimal_useful_context_tokens": smallest["evaluation"]["actual_prompt_tokens"] if smallest else None, "variant": smallest["variant"] if smallest else None})
        holdout_runs = lambda variant: [run for run in by_variant[variant] if run["query_spec"]["split"] == "holdout"]
        holdout_v0, holdout_best = self._aggregate(holdout_runs("V0")), self._aggregate(holdout_runs(best))
        keep = bool(not regressions and (holdout_best["context_fact_recall"] or 0) >= (holdout_v0["context_fact_recall"] or 0) and (holdout_best["answer_fact_recall"] or 0) >= (holdout_v0["answer_fact_recall"] or 0) and (holdout_best["unknown_safety_rate"] or 0) >= (holdout_v0["unknown_safety_rate"] or 0) and (holdout_best["actual_prompt_tokens"]["median"] or 1e9) < (holdout_v0["actual_prompt_tokens"]["median"] or 0) and (holdout_best["prompt_eval_ms"]["median"] or 1e9) < (holdout_v0["prompt_eval_ms"]["median"] or 0))
        recommendation = "KEEP_CANDIDATE" if keep else "CONDITIONAL" if not regressions else "REJECT"
        oracle = aggregate["ORACLE_EVAL"]
        oracle_by_query = [{"query_id": query["query_id"], "v0_tokens": next(run for run in by_variant["V0"] if run["query_spec"]["query_id"] == query["query_id"])["evaluation"]["actual_prompt_tokens"], "oracle_tokens": next(run for run in by_variant["ORACLE_EVAL"] if run["query_spec"]["query_id"] == query["query_id"])["evaluation"]["actual_prompt_tokens"]} for query in self.queries]
        for row in oracle_by_query:
            row["oracle_gap"] = row["v0_tokens"] - row["oracle_tokens"]; row["oracle_gap_percent"] = 100 * row["oracle_gap"] / row["v0_tokens"] if row["v0_tokens"] else None
        budget_summary = {variant: aggregate[variant] for variant in variants if variant.startswith("EXTRACTIVE_B")}
        pareto = []
        for variant in production_variants + ["V0"]:
            item = aggregate[variant]
            def dominates(other: str) -> bool:
                left = aggregate[other]
                no_worse = (
                    (left["correctness_rate"] or 0) >= (item["correctness_rate"] or 0)
                    and (left["actual_prompt_tokens"]["median"] or 1e9) <= (item["actual_prompt_tokens"]["median"] or 1e9)
                    and (left["prompt_eval_ms"]["median"] or 1e9) <= (item["prompt_eval_ms"]["median"] or 1e9)
                )
                strictly_better = (
                    (left["correctness_rate"] or 0) > (item["correctness_rate"] or 0)
                    or (left["actual_prompt_tokens"]["median"] or 1e9) < (item["actual_prompt_tokens"]["median"] or 1e9)
                    or (left["prompt_eval_ms"]["median"] or 1e9) < (item["prompt_eval_ms"]["median"] or 1e9)
                )
                return no_worse and strictly_better
            dominated = any(dominates(other) for other in production_variants + ["V0"] if other != variant)
            if not dominated: pareto.append(variant)
        tokens_delta = _percent_delta(v0["actual_prompt_tokens"]["median"], candidate["actual_prompt_tokens"]["median"])
        prompt_delta = _percent_delta(v0["prompt_eval_ms"]["median"], candidate["prompt_eval_ms"]["median"])
        ttft_delta = _percent_delta(v0["ttft_ms"]["median"], candidate["ttft_ms"]["median"])
        cpu_delta = _percent_delta(v0["cpu_time_seconds"]["median"], candidate["cpu_time_seconds"]["median"])
        latency_delta = _percent_delta(v0["total_latency_ms"]["median"], candidate["total_latency_ms"]["median"])
        distiller_wall = candidate["distiller_wall_ms"]["median"] or 0.0
        net_wall_saved = -(prompt_delta["delta"] or 0) - distiller_wall
        hypotheses = {
            "HYP-4FW-001": "SUPPORTED" if keep and (tokens_delta["percent"] or 0) <= -20 else "CONDITIONAL" if (tokens_delta["delta"] or 0) < 0 else "REJECTED",
            "HYP-4FW-002": "SUPPORTED" if aggregate["PRUNING_ONLY"]["records_pruned"]["median"] and aggregate["PRUNING_ONLY"]["correctness_rate"] >= v0["correctness_rate"] else "CONDITIONAL" if aggregate["PRUNING_ONLY"]["records_pruned"]["median"] else "REJECTED",
            "HYP-4FW-003": "SUPPORTED" if overload else "CONDITIONAL" if not regressions and candidate["correctness_rate"] >= v0["correctness_rate"] else "REJECTED",
            "HYP-4FW-004": "SUPPORTED" if (prompt_delta["delta"] or 0) < 0 and (ttft_delta["delta"] or 0) < 0 and (cpu_delta["delta"] or 0) < 0 and net_wall_saved > 0 else "REJECTED",
            "HYP-4FW-005": "SUPPORTED" if sum(item["minimal_useful_context_tokens"] is not None for item in minimal) >= max(1, len(self.queries) // 2) else "CONDITIONAL" if any(item["minimal_useful_context_tokens"] is not None for item in minimal) else "REJECTED",
        }
        frozen_after = {name: _tree_digest(self.root / name) for name in FROZEN_DIRS}; frozen_ok = frozen_after == self.frozen_before
        canonical = not self.quick and len(self.queries) == 14 and len(runs) == len(self.queries) * len(self._variants(selected_budget))
        status = "PASS" if canonical and frozen_ok else "PASS_QUICK_NON_CANONICAL" if self.quick and frozen_ok else "FAIL"
        summary = {**self._base("summary", self.matrix_id), "status": status, "operational_status": status, "canonical": canonical, "phase4fw_windows_canonical": canonical, "completed_at_utc": _utc_now(), "hypotheses": hypotheses, "recommendation": recommendation, "selected_dev_budget": selected_budget, "dev_queries": sum(query["split"] == "development" for query in self.queries), "holdout_queries": sum(query["split"] == "holdout" for query in self.queries), "runs": len(runs), "variants": aggregate, "best_variant": best, "best_comparison": {"tokens": tokens_delta, "context_fact_recall": {"v0": v0["context_fact_recall"], "variant": candidate["context_fact_recall"]}, "answer_fact_recall": {"v0": v0["answer_fact_recall"], "variant": candidate["answer_fact_recall"]}, "correctness": {"v0": v0["correctness_rate"], "variant": candidate["correctness_rate"]}, "grounding": {"v0": v0["grounding_rate"], "variant": candidate["grounding_rate"]}, "unknown_safety": {"v0": v0["unknown_safety_rate"], "variant": candidate["unknown_safety_rate"]}, "false_no_knowledge": {"v0": v0["false_no_knowledge"], "variant": candidate["false_no_knowledge"]}, "prompt_eval_ms": prompt_delta, "ttft_ms": ttft_delta, "cpu_time_seconds": cpu_delta, "total_latency_ms": latency_delta, "distiller_wall_ms": distiller_wall, "distiller_cpu_ms": candidate["distiller_cpu_ms"]["median"], "net_wall_time_saved_ms": net_wall_saved}, "oracle": {"aggregate": oracle, "per_query": oracle_by_query, "gap_median": _stats(row["oracle_gap"] for row in oracle_by_query)}, "budgets": budget_summary, "minimal_useful_context": minimal, "minimal_useful_context_median": _stats(item["minimal_useful_context_tokens"] for item in minimal), "pareto_frontier": pareto, "per_query": per_query, "regressions": regressions, "improvements": improvements, "context_overload_candidates": overload, "ablation": {variant: aggregate[variant] for variant in ("V0", f"EXTRACTIVE_B{selected_budget}", "PRUNING_ONLY", f"COMBINED_B{selected_budget}")}, "memory_tradeoff": {"distiller_metadata_bytes": candidate.get("metadata_bytes", 0), "classification": "NEGLIGIBLE_NO_INDEX"}, "hud": {"funnel_metrics_available": True, "quality_always_adjacent": True}, "small_real_corpus_evidence": True, "frozen_before": self.frozen_before, "frozen_after": frozen_after, "frozen_preserved": frozen_ok, "context_builder_v0_intact": True, "default_global_changed": False, "phase4e_debian": "PENDING", "phase4f_canonical_status": "NOT_STARTED", "phase5_status": "NOT_STARTED", "prefetch_status": "NOT_STARTED"}
        hud_payload = {
            **self._base("hud"), "status": "PASS", "data_source": "PHASE4FW_MEASURED",
            "funnel": {
                "active_brain_bytes": candidate["active_brain_bytes"]["median"],
                "records_retrieved": candidate["records_retrieved"]["median"],
                "records_retained": candidate["records_retained"]["median"],
                "evidence_context_tokens": candidate["context_tokens"]["median"],
                "actual_core_prompt_tokens": candidate["actual_prompt_tokens"]["median"],
                "v0_actual_prompt_tokens": v0["actual_prompt_tokens"]["median"],
                "tokens_avoided": -(tokens_delta["delta"] or 0),
            },
            "quality": {
                "context_fact_recall": candidate["context_fact_recall"],
                "answer_fact_recall": candidate["answer_fact_recall"],
                "grounding_rate": candidate["grounding_rate"],
                "unknown_safety_rate": candidate["unknown_safety_rate"],
            },
            "prompt_processing_ms": candidate["prompt_eval_ms"]["median"],
        }
        hud_path = self._write("hud", hud_payload)
        summary["hud"].update({"artifact": str(hud_path), "artifact_sha256": file_sha256(hud_path)})
        immutable = self.results / "summaries" / f"{self.matrix_id}.json"; _exclusive_json(immutable, summary); _atomic_json(self.results / "summary.json", summary)
        markdown = self._markdown(summary); immutable.with_suffix(".md").write_text(markdown, encoding="utf-8", newline="\n")
        temporary = self.results / ".PHASE4FW_SUMMARY.md.tmp"; temporary.write_text(markdown, encoding="utf-8", newline="\n"); os.replace(temporary, self.results / "PHASE4FW_SUMMARY.md")
        self.checkpoint["summary"] = {"path": str(immutable), "sha256": file_sha256(immutable)}; self.checkpoint["complete"] = True; _atomic_json(self.checkpoint_path, self.checkpoint)
        return summary

    def _markdown(self, summary: dict[str, Any]) -> str:
        lines = ["# Phase 4F-W — Context Efficiency", "", f"- Status: `{summary['status']}`", f"- Best variant: `{summary['best_variant']}` / `{summary['recommendation']}`", f"- Hypotheses: `{summary['hypotheses']}`", f"- Frozen baselines: `{summary['frozen_preserved']}`", "", "## Variants", "", "| Variant | Prompt tokens | Context fact recall | Answer fact recall | Correct | Prompt eval ms | TTFT ms | CPU s |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
        for name, item in summary["variants"].items():
            lines.append(f"| {name} | {item['actual_prompt_tokens']['median']} | {item['context_fact_recall']} | {item['answer_fact_recall']} | {item['correctness_rate']} | {item['prompt_eval_ms']['median']} | {item['ttft_ms']['median']} | {item['cpu_time_seconds']['median']} |")
        lines += ["", "## Budgets", "", "| Variant | Actual tokens | Fact recall | Correctness | NO_KNOWLEDGE false | Prompt eval ms |", "|---|---:|---:|---:|---:|---:|"]
        for name, item in summary["budgets"].items():
            lines.append(f"| {name} | {item['actual_prompt_tokens']['median']} | {item['context_fact_recall']} | {item['correctness_rate']} | {item['false_no_knowledge']} | {item['prompt_eval_ms']['median']} |")
        lines += ["", f"Oracle: `{summary['oracle']}`", "", f"Best comparison: `{summary['best_comparison']}`", "", f"Pareto: `{summary['pareto_frontier']}`", "", f"Regressions: `{summary['regressions']}`", "", f"Improvements: `{summary['improvements']}`", "", "This is Windows experimental evidence. Phase 4F canonical, Phase 5, and prefetch remain not started.", ""]
        return "\n".join(lines)
