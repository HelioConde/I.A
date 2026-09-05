#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import resource
import statistics
import sys
import time
import tracemalloc
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brain_ssd.gating import BasalGate, CognitiveState
from brain_ssd.hybrid import HybridContextState, HybridRetrievalV0
from brain_ssd.progressive import LexicalProgressiveRouter
from brain_ssd.router import LexicalRouter, SemanticIndex
from brain_ssd.semantic import generate_semantic_manifest
from brain_ssd.semantic_rescue_dataset import generate_semantic_rescue_dataset
from brain_ssd.storage import MMapStorageBackend, touch_view
from brain_ssd.system_metrics import process_io, process_memory

MIB = 1024**2
SEED = 20260807


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    os.replace(temporary, path)


def metrics(query: dict, pages, status: str, confidence: float, pre_pages=(), pre_confidence=0.0) -> dict:
    active, required = set(pages), set(query["required_pages"])
    relevant = required | set(query["optional_pages"])
    recall = len(active & required) / len(required) if required else 1.0
    precision = len(active & relevant) / len(active) if active else (1.0 if not relevant else 0.0)
    pre_active = set(pre_pages)
    pre_recall = len(pre_active & required) / len(required) if required else 1.0
    return {
        "routing_recall": recall, "routing_precision": precision,
        "active_brain_mib": len(active), "activation_rate": len(active) / 1024,
        "false_confidence": bool(required and recall < 1 and status == "OK" and confidence >= 0.8),
        "false_early_stop": bool(required and recall < 1 and status == "OK"),
        "pre_rescue_recall": pre_recall, "pre_rescue_confidence": pre_confidence,
        "post_rescue_confidence": confidence, "missed_pages": sorted(required - active),
    }


def evaluate_hybrid(router: HybridRetrievalV0, queries: list[dict], semantic_enabled: bool, strategy: str) -> list[dict]:
    states: dict[str, HybridContextState] = defaultdict(HybridContextState)
    records = []
    for query in queries:
        state = None
        if query["sequence_id"]:
            state = states[query["sequence_id"]]
            state.begin_turn()
        cpu_started, started = time.process_time_ns(), time.perf_counter_ns()
        result = router.route(query["query"], state, semantic_enabled)
        route_ms = (time.perf_counter_ns() - started) / 1e6
        state_update_ms = 0.0
        if state is not None:
            update_started = time.perf_counter_ns()
            state.update(result.topics, {topic: 1.0 for topic in result.current_query_topics})
            state_update_ms = (time.perf_counter_ns() - update_started) / 1e6
        cpu_ms = (time.process_time_ns() - cpu_started) / 1e6
        score = metrics(query, result.activate_pages, result.status, result.post_rescue_confidence, result.pre_rescue_pages, result.pre_rescue_confidence)
        relevant = set(query["required_pages"]) | set(query["optional_pages"])
        context_only = {page for page, sources in result.page_provenance.items() if "CONTEXT_EXPANSION" in sources and "CURRENT_QUERY" not in sources}
        alias_pages = {page for page, sources in result.page_provenance.items() if "ALIAS" in sources}
        fuzzy_pages = {page for page, sources in result.page_provenance.items() if "FUZZY_MATCH" in sources}
        records.append({
            "strategy": strategy, "query_id": query["query_id"], "split": query["split"],
            "category": query["category"], "sequence_id": query["sequence_id"], "turn_index": query["turn_index"],
            "status": result.status, "resolved_level": result.resolved_level, "cascade_levels": result.cascade_levels,
            "semantic_used": result.semantic_used, "semantic_method": result.semantic_method,
            "semantic_rescue_without_budget_expansion": result.semantic_rescue_without_budget_expansion,
            "expansion_count": result.expansion_count, "final_budget_mib": result.final_budget_mib,
            "all_domain_used": result.all_domain_used, "reason_for_all_domain": result.reason_for_all_domain,
            "partial_probability": result.partial_probability, "partial_signals": result.partial_signals,
            "current_query_topics": result.current_query_topics, "context_expansion_topics": result.context_expansion_topics,
            "activate_pages": result.activate_pages, "topics": result.topics, "page_provenance": result.page_provenance,
            "evidence": [item.__dict__ for item in result.evidence], "unknown_tokens": result.unknown_tokens,
            "context_helpful_bytes": len(context_only & relevant) * MIB,
            "context_contamination_bytes": len(context_only - relevant) * MIB,
            "alias_expansion_count": result.alias_expansion_count,
            "alias_useful_hits": len(alias_pages & relevant), "alias_false_hits": len(alias_pages - relevant),
            "fuzzy_useful_hits": len(fuzzy_pages & relevant), "fuzzy_false_hits": len(fuzzy_pages - relevant),
            "route_ms": route_ms, "state_update_ms": state_update_ms, "cpu_ms": cpu_ms,
            "timings_ms": result.timings_ms, **score,
        })
    return records


def calibrate(index: SemanticIndex, development: list[dict]) -> dict:
    trials = []
    for method, thresholds, margins in (
        ("tfidf", (0.12, 0.18, 0.24), (0.0, 0.025, 0.05)),
        ("char_ngram", (0.06, 0.10, 0.14), (0.0, 0.015, 0.03)),
    ):
        for threshold in thresholds:
            for margin in margins:
                router = HybridRetrievalV0(index, method, threshold, margin)
                rows = evaluate_hybrid(router, development, True, "calibration")
                required_rows = [row for row in rows if next(q for q in development if q["query_id"] == row["query_id"])["required_pages"]]
                unknown_rows = [row for row in rows if not next(q for q in development if q["query_id"] == row["query_id"])["required_pages"]]
                trial = {
                    "method": method, "semantic_threshold": threshold, "semantic_margin": margin,
                    "recall": statistics.mean(row["routing_recall"] for row in rows),
                    "required_recall": statistics.mean(row["routing_recall"] for row in required_rows),
                    "precision": statistics.mean(row["routing_precision"] for row in rows),
                    "unknown_safe_rate": statistics.mean(row["active_brain_mib"] == 0 and row["status"] == "NO_KNOWLEDGE" for row in unknown_rows),
                    "false_early_stop_rate": statistics.mean(row["false_early_stop"] for row in rows),
                    "active_brain_mib_mean": statistics.mean(row["active_brain_mib"] for row in rows),
                    "route_ms_mean": statistics.mean(row["route_ms"] for row in rows),
                }
                trials.append(trial)
    chosen = max(trials, key=lambda row: (row["unknown_safe_rate"], row["required_recall"], -row["false_early_stop_rate"], row["precision"], -row["active_brain_mib_mean"], row["method"] == "tfidf", row["semantic_threshold"], row["semantic_margin"]))
    chosen_rows = evaluate_hybrid(HybridRetrievalV0(index, chosen["method"], chosen["semantic_threshold"], chosen["semantic_margin"]), development, True, "development_calibration")
    curve = []
    for low, high in ((0, .5), (.5, .7), (.7, .85), (.85, 1.01)):
        rows = [row for row in chosen_rows if low <= row["pre_rescue_confidence"] < high]
        curve.append({"pre_confidence_range": [low, high], "count": len(rows), "pre_rescue_actual_recall": statistics.mean(row["pre_rescue_recall"] for row in rows) if rows else None, "post_rescue_actual_recall": statistics.mean(row["routing_recall"] for row in rows) if rows else None})
    return {"schema_version": 1, "selection_policy": "deterministic lexicographic: OOD safety, required recall, false stop, precision, active MiB, TF-IDF tie preference, higher threshold, higher margin; latency is reported but never a tie-breaker", "development_query_ids": [query["query_id"] for query in development], "trials": trials, "chosen": chosen, "pre_rescue_development_calibration": curve}


def run_baselines(index: SemanticIndex, queries: list[dict]) -> list[dict]:
    records = []
    lexical, gate = LexicalRouter(index), BasalGate(index)
    progressive = LexicalProgressiveRouter(index)
    progressive_states: dict[str, CognitiveState] = defaultdict(CognitiveState)
    for query in queries:
        started = time.perf_counter_ns()
        route = lexical.route(query["query"])
        plan = gate.apply(route, 8)
        elapsed = (time.perf_counter_ns() - started) / 1e6
        records.append({"strategy": "lexical_phase3_8mib", "query_id": query["query_id"], "split": query["split"], "category": query["category"], "status": "OK", "activate_pages": plan.activate_pages, "route_ms": elapsed, **metrics(query, plan.activate_pages, "OK", route.confidence)})

        state = None
        if query["sequence_id"]:
            state = progressive_states[query["sequence_id"]]
            state.decay()
        started = time.perf_counter_ns()
        result = progressive.route(query["query"], state, True, True)
        elapsed = (time.perf_counter_ns() - started) / 1e6
        if state:
            state.update(progressive.as_route_result(result), result.activate_pages)
        records.append({"strategy": "progressive_contextual_phase3_5", "query_id": query["query_id"], "split": query["split"], "category": query["category"], "status": result.status, "activate_pages": result.activate_pages, "route_ms": elapsed, **metrics(query, result.activate_pages, result.status, result.signals.confidence)})

        oracle_pages = tuple([*query["required_pages"], *query["optional_pages"]])
        records.append({"strategy": "oracle", "query_id": query["query_id"], "split": query["split"], "category": query["category"], "status": "OK", "activate_pages": oracle_pages, "route_ms": 0.0, **metrics(query, oracle_pages, "OK", 1.0)})
        domain_pages = tuple(page for domain in query["expected_domains"] for page in index.domain_pages[domain])
        records.append({"strategy": "all_domain_evaluation", "query_id": query["query_id"], "split": query["split"], "category": query["category"], "status": "OK", "activate_pages": domain_pages, "route_ms": 0.0, **metrics(query, domain_pages, "OK", 1.0)})
    return records


def semantic_cost(index: SemanticIndex, chosen: dict) -> dict:
    before = process_memory()
    tracemalloc.start()
    started = time.perf_counter_ns()
    router = HybridRetrievalV0(index, chosen["method"], chosen["semantic_threshold"], chosen["semantic_margin"])
    build_ms = (time.perf_counter_ns() - started) / 1e6
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    after = process_memory()
    return {
        "method": chosen["method"], "build_ms": build_ms,
        "serialized_index_bytes": router.semantic.serialized_size_bytes,
        "estimated_resident_bytes": router.semantic.estimated_resident_bytes(),
        "fuzzy_ngram_index_serialized_bytes": router.fuzzy_index_serialized_bytes,
        "tracemalloc_peak_build_bytes": peak,
        "rss_incremental_bytes": (after.get("rss_bytes") or 0) - (before.get("rss_bytes") or 0),
        "pss_incremental_bytes": (after.get("pss_bytes") or 0) - (before.get("pss_bytes") or 0),
    }


def integrated(index: SemanticIndex, queries: list[dict], chosen: dict, physical_manifest: Path) -> dict:
    lexical, gate = LexicalRouter(index), BasalGate(index)
    progressive = LexicalProgressiveRouter(index)
    hybrid = HybridRetrievalV0(index, chosen["method"], chosen["semantic_threshold"], chosen["semantic_margin"])
    progressive_states: dict[str, CognitiveState] = defaultdict(CognitiveState)
    hybrid_states: dict[str, HybridContextState] = defaultdict(HybridContextState)
    records = []
    for query in queries:
        selections = []
        started = time.perf_counter_ns(); route = lexical.route(query["query"]); pages = gate.apply(route, 8).activate_pages; selections.append(("lexical_phase3_8mib", pages, (time.perf_counter_ns() - started) / 1e6))
        pstate = progressive_states[query["sequence_id"]] if query["sequence_id"] else None
        if pstate: pstate.decay()
        started = time.perf_counter_ns(); presult = progressive.route(query["query"], pstate, True, True); pms = (time.perf_counter_ns() - started) / 1e6
        if pstate: pstate.update(progressive.as_route_result(presult), presult.activate_pages)
        selections.append(("progressive_contextual_phase3_5", presult.activate_pages, pms))
        hstate = hybrid_states[query["sequence_id"]] if query["sequence_id"] else None
        if hstate: hstate.begin_turn()
        started = time.perf_counter_ns(); hresult = hybrid.route(query["query"], hstate, True); hms = (time.perf_counter_ns() - started) / 1e6
        if hstate: hstate.update(hresult.topics, {topic: 1 for topic in hresult.current_query_topics})
        selections.append(("hybrid_best_semantic", hresult.activate_pages, hms))
        for strategy, selected, route_ms in selections:
            backend = MMapStorageBackend(physical_manifest)
            cold = backend.advise_drop_cache()
            io_before = process_io(); usage_before = resource.getrusage(resource.RUSAGE_SELF)
            cpu_started, started = time.process_time_ns(), time.perf_counter_ns()
            first_ms, sink = None, 0
            with backend:
                for page_id in selected:
                    page = backend.get_page(page_id, validate=False); sink ^= touch_view(page.data); backend.release_page(page)
                    if first_ms is None: first_ms = (time.perf_counter_ns() - started) / 1e6
            storage_ms = (time.perf_counter_ns() - started) / 1e6
            usage_after = resource.getrusage(resource.RUSAGE_SELF); io_after = process_io()
            records.append({
                "strategy": strategy, "query_id": query["query_id"], "best_effort_cold": cold,
                "active_brain_mib": len(selected), "route_ms": route_ms,
                "tt_first_activation_ms": first_ms, "storage_ms": storage_ms, "total_ms": route_ms + storage_ms,
                "cpu_ms": (time.process_time_ns() - cpu_started) / 1e6,
                "logical_bytes": len(selected) * MIB,
                "physical_read_bytes": max(0, (io_after.get("read_bytes") or 0) - (io_before.get("read_bytes") or 0)),
                "minor_faults": usage_after.ru_minflt - usage_before.ru_minflt,
                "major_faults": usage_after.ru_majflt - usage_before.ru_majflt, "sink": sink,
            })
    return {"schema_version": 1, "kind": "phase3_75_integrated", "records": records}


def summarize(records: list[dict], integrated_payload: dict, semantic_cost_payload: dict) -> dict:
    holdout = [row for row in records if row["split"] == "holdout"]
    summaries = []
    for strategy in sorted({row["strategy"] for row in holdout}):
        rows = [row for row in holdout if row["strategy"] == strategy]
        route_values = [row.get("route_ms", 0.0) for row in rows]
        summaries.append({
            "strategy": strategy, "queries": len(rows), "recall": statistics.mean(row["routing_recall"] for row in rows),
            "precision": statistics.mean(row["routing_precision"] for row in rows),
            "active_brain_mib_median": statistics.median(row["active_brain_mib"] for row in rows),
            "active_brain_mib_mean": statistics.mean(row["active_brain_mib"] for row in rows),
            "activation_rate_mean": statistics.mean(row["activation_rate"] for row in rows),
            "false_confidence_rate": statistics.mean(row["false_confidence"] for row in rows),
            "false_early_stop_rate": statistics.mean(row["false_early_stop"] for row in rows),
            "route_ms_mean": statistics.mean(route_values), "route_ms_p50": statistics.median(route_values),
            "route_ms_p95": sorted(route_values)[max(0, int(.95 * len(route_values)) - 1)],
        })
    hybrid = [row for row in holdout if row["strategy"] == "hybrid_best_semantic"]
    fast = [row for row in hybrid if not row["semantic_used"]]
    slow = [row for row in hybrid if row["semantic_used"]]
    semantic_successes = [row for row in slow if row["semantic_rescue_without_budget_expansion"] and row["routing_recall"] == 1]
    calibration = []
    for low, high in ((0, .5), (.5, .7), (.7, .85), (.85, 1.01)):
        rows = [row for row in hybrid if low <= row["pre_rescue_confidence"] < high]
        calibration.append({"pre_confidence_range": [low, high], "count": len(rows), "pre_rescue_actual_recall": statistics.mean(row["pre_rescue_recall"] for row in rows) if rows else None})
    storage = []
    for strategy in sorted({row["strategy"] for row in integrated_payload["records"]}):
        rows = [row for row in integrated_payload["records"] if row["strategy"] == strategy]
        storage.append({
            "strategy": strategy, "runs": len(rows), "active_brain_mib_mean": statistics.mean(row["active_brain_mib"] for row in rows),
            "tt_first_activation_ms_median": statistics.median(row["tt_first_activation_ms"] for row in rows if row["tt_first_activation_ms"] is not None),
            "storage_ms_median": statistics.median(row["storage_ms"] for row in rows), "total_ms_median": statistics.median(row["total_ms"] for row in rows),
            "logical_bytes_total": sum(row["logical_bytes"] for row in rows), "physical_read_bytes_total": sum(row["physical_read_bytes"] for row in rows),
            "minor_faults_total": sum(row["minor_faults"] for row in rows), "major_faults_total": sum(row["major_faults"] for row in rows),
        })
    category = []
    for name in sorted({row["category"] for row in hybrid}):
        rows = [row for row in hybrid if row["category"] == name]
        category.append({"category": name, "count": len(rows), "recall": statistics.mean(row["routing_recall"] for row in rows), "precision": statistics.mean(row["routing_precision"] for row in rows), "active_mib_mean": statistics.mean(row["active_brain_mib"] for row in rows)})
    failures = [{"query_id": row["query_id"], "category": row["category"], "status": row["status"], "recall": row["routing_recall"], "precision": row["routing_precision"], "active_mib": row["active_brain_mib"], "topics": row["topics"]} for row in hybrid if row["routing_recall"] < 1 or row["status"] not in {"OK", "NO_KNOWLEDGE"}]
    return {
        "schema_version": 1, "holdout_summaries": summaries,
        "hybrid_semantic_rescue_rate": len(slow) / len(hybrid),
        "hybrid_rescue_success_rate": len(semantic_successes) / len(slow) if slow else None,
        "hybrid_all_domain_rate": statistics.mean(row["all_domain_used"] for row in hybrid),
        "hybrid_resolved_level_distribution": dict(Counter(row["resolved_level"] for row in hybrid)),
        "context_helpful_bytes": sum(row["context_helpful_bytes"] for row in hybrid),
        "context_contamination_bytes": sum(row["context_contamination_bytes"] for row in hybrid),
        "alias_expansion_count": sum(row["alias_expansion_count"] for row in hybrid),
        "alias_useful_hits": sum(row["alias_useful_hits"] for row in hybrid), "alias_false_hits": sum(row["alias_false_hits"] for row in hybrid),
        "fuzzy_useful_hits": sum(row["fuzzy_useful_hits"] for row in hybrid), "fuzzy_false_hits": sum(row["fuzzy_false_hits"] for row in hybrid),
        "fast_path": {"fraction": len(fast) / len(hybrid), "p50_ms": statistics.median(row["route_ms"] for row in fast), "p95_ms": sorted(row["route_ms"] for row in fast)[max(0, int(.95 * len(fast)) - 1)]},
        "slow_path": {"fraction": len(slow) / len(hybrid), "p50_ms": statistics.median(row["route_ms"] for row in slow), "p95_ms": sorted(row["route_ms"] for row in slow)[max(0, int(.95 * len(slow)) - 1)]},
        "expected_average_routing_cost_ms": statistics.mean(row["route_ms"] for row in hybrid),
        "pre_rescue_calibration": calibration, "hybrid_by_category": category,
        "storage_integration": storage, "semantic_index_cost": semantic_cost_payload, "remaining_failures": failures,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results/phase3_75")
    parser.add_argument("--semantic-manifest", type=Path, default=ROOT / "brain_data/synthetic-1gib-seed-20260807/semantic-manifest.json")
    parser.add_argument("--dataset", type=Path, default=ROOT / "benchmarks/data/phase3_75-queries.json")
    parser.add_argument("--physical-manifest", type=Path, default=ROOT / "brain_data/synthetic-1gib-seed-20260807/manifest-1048576.json")
    args = parser.parse_args()
    manifest = generate_semantic_manifest(args.semantic_manifest, 1024, SEED)
    dataset = generate_semantic_rescue_dataset(args.dataset, manifest, SEED)
    index = SemanticIndex(manifest)
    development = [query for query in dataset["queries"] if query["split"] == "development"]
    holdout = [query for query in dataset["queries"] if query["split"] == "holdout"]
    calibration = calibrate(index, development)
    chosen = calibration["chosen"]
    cost = semantic_cost(index, chosen)
    hybrid = HybridRetrievalV0(index, chosen["method"], chosen["semantic_threshold"], chosen["semantic_margin"])
    records = run_baselines(index, holdout)
    records += evaluate_hybrid(HybridRetrievalV0(index, chosen["method"], chosen["semantic_threshold"], chosen["semantic_margin"]), holdout, False, "hybrid_no_semantic")
    records += evaluate_hybrid(hybrid, holdout, True, "hybrid_best_semantic")
    integrated_payload = integrated(index, holdout, chosen, args.physical_manifest)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    atomic_json(args.output_dir / "calibration.json", calibration)
    atomic_json(args.output_dir / "holdout.json", {"schema_version": 1, "kind": "phase3_75_holdout", "chosen_config": chosen, "records": records})
    atomic_json(args.output_dir / "integrated-storage.json", integrated_payload)
    atomic_json(args.output_dir / "summary.json", summarize(records, integrated_payload, cost))
    print(args.output_dir)


if __name__ == "__main__":
    main()
