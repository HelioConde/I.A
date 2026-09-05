#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import resource
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brain_ssd.gating import BasalGate, CognitiveState
from brain_ssd.progressive import LexicalProgressiveRouter
from brain_ssd.recall_dataset import generate_recall_dataset
from brain_ssd.router import BenchmarkRouter, LexicalRouter, SemanticIndex
from brain_ssd.semantic import generate_semantic_manifest
from brain_ssd.storage import MMapStorageBackend, touch_view
from brain_ssd.system_metrics import process_io, process_memory

MIB = 1024**2
SEED = 20260807


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    os.replace(temporary, path)


def score(query: dict, activated: tuple[int, ...], confidence: float, status: str, max_budget: int) -> dict:
    active, required = set(activated), set(query["required_pages"])
    relevant = required | set(query["optional_pages"])
    recall = len(active & required) / len(required) if required else 1.0
    precision = len(active & relevant) / len(active) if active else (1.0 if not relevant else 0.0)
    false_confident = bool(required and recall < 1 and status == "OK" and confidence >= 0.80)
    return {
        "required_count": len(required), "routing_recall": recall, "routing_precision": precision,
        "required_page_miss_rate": 1 - recall, "false_confidence": false_confident,
        "active_pages": len(active), "active_brain_mib": len(active),
        "activation_rate": len(active) / 1024, "budget_available_mib": max_budget,
        "budget_used_mib": len(active), "budget_utilization": len(active) / max_budget if max_budget else 0,
        "recall_per_active_mib": recall / len(active) if active else (1.0 if not required else 0.0),
        "missed_pages": sorted(required - active),
        "required_page_causes_missed": {topic: sorted(set(pages) - active) for topic, pages in query["required_page_causes"].items() if set(pages) - active},
    }


def run_lexical(index: SemanticIndex, query: dict) -> dict:
    router, gate = LexicalRouter(index), BasalGate(index)
    started, cpu_start = time.perf_counter_ns(), time.process_time_ns()
    routed = router.route(query["query"], None)
    route_done = time.perf_counter_ns()
    plan = gate.apply(routed, 8)
    done = time.perf_counter_ns()
    confidence = routed.confidence
    metrics = score(query, plan.activate_pages, confidence, "OK", 8)
    return {
        "strategy": "lexical_phase3_8mib", "query_id": query["query_id"], "split": query["split"], "category": query["category"],
        "sequence_id": query["sequence_id"], "turn_index": query["turn_index"], "status": "OK",
        "confidence": confidence, "query_coverage": None, "final_budget_mib": 8, "expansion_count": 0,
        "fallback_levels": [], "router_ms": (route_done - started) / 1e6, "gate_ms": (done - route_done) / 1e6,
        "state_update_ms": 0.0, "decision_ms": (done - started) / 1e6,
        "cpu_ms": (time.process_time_ns() - cpu_start) / 1e6, "activate_pages": list(plan.activate_pages), **metrics,
    }


def run_progressive(router: LexicalProgressiveRouter, query: dict, state: CognitiveState | None, mode: str) -> dict:
    if state is not None:
        state.decay()
    started, cpu_start = time.perf_counter_ns(), time.process_time_ns()
    result = router.route(query["query"], state, use_context=mode == "contextual", use_hysteresis=mode != "stateless")
    route_done = time.perf_counter_ns()
    update_ms = 0.0
    if state is not None:
        update_start = time.perf_counter_ns()
        state.update(router.as_route_result(result), result.activate_pages)
        update_ms = (time.perf_counter_ns() - update_start) / 1e6
    decision_ms = (time.perf_counter_ns() - started) / 1e6
    metrics = score(query, result.activate_pages, result.signals.confidence, result.status, result.final_budget_mib)
    return {
        "strategy": "lexical_progressive_" + mode, "query_id": query["query_id"], "split": query["split"], "category": query["category"],
        "sequence_id": query["sequence_id"], "turn_index": query["turn_index"], "status": result.status,
        "confidence": result.signals.confidence, "query_coverage": result.signals.query_coverage,
        "confidence_signals": result.signals.__dict__, "analysis": {
            "tokens": result.analysis.raw_tokens, "expanded_tokens": result.analysis.expanded_tokens,
            "concepts": result.analysis.concepts, "domains": result.analysis.domains,
            "unknown_tokens": result.analysis.unknown_tokens, "groups": result.analysis.groups,
            "partial_cue": result.analysis.partial_cue, "context_terms": result.analysis.context_terms,
            "new_topic_score": result.analysis.new_topic_score,
        },
        "initial_budget_mib": result.initial_budget_mib, "final_budget_mib": result.final_budget_mib,
        "expansion_count": result.expansion_count, "expansion_reasons": result.expansion_reasons,
        "fallback_levels": result.fallback_levels, "hysteresis_budget_fraction": result.hysteresis_budget_fraction,
        "kept_by_hysteresis": len(result.kept_by_hysteresis),
        "decomposition_ms": result.timings_ms["decomposition"], "ranking_ms": result.timings_ms["ranking"],
        "confidence_ms": result.timings_ms.get("confidence", 0.0),
        "gate_ms": result.timings_ms.get("activation_planning", 0.0),
        "confidence_fallback_ms": result.timings_ms.get("confidence_and_fallback", 0.0),
        "router_ms": (route_done - started) / 1e6, "state_update_ms": update_ms,
        "decision_ms": decision_ms, "cpu_ms": (time.process_time_ns() - cpu_start) / 1e6,
        "activate_pages": list(result.activate_pages), **metrics,
    }


def isolated(manifest: dict, dataset: dict) -> dict:
    index = SemanticIndex(manifest)
    progressive = LexicalProgressiveRouter(index)
    queries = dataset["queries"]
    records = [run_lexical(index, query) for query in queries]
    for mode in ("stateless", "hysteresis", "contextual"):
        states: dict[str, CognitiveState] = defaultdict(CognitiveState)
        for query in queries:
            state = None if mode == "stateless" or not query["sequence_id"] else states[query["sequence_id"]]
            records.append(run_progressive(progressive, query, state, mode))
    without_aliases = LexicalProgressiveRouter(index, aliases={})
    for query in queries:
        row = run_progressive(without_aliases, query, None, "stateless")
        row["strategy"] = "lexical_progressive_no_aliases"
        records.append(row)
    # Evaluation-only ceilings; ground truth is deliberately outside the real Router.
    benchmark_queries = [{**q, "expected_domain": q["expected_domains"][0] if q["expected_domains"] else None} for q in queries]
    oracle = BenchmarkRouter("oracle", index, benchmark_queries)
    for query in benchmark_queries:
        routed = oracle.route(query["query"])
        pages = tuple(page for page, _, _ in routed.candidate_pages)
        records.append({"strategy": "oracle", "query_id": query["query_id"], "split": query["split"], "category": query["category"], "activate_pages": list(pages), **score(query, pages, 1.0, "OK", max(1, len(pages)))})
        domain_pages = tuple(page for domain in query["expected_domains"] for page in index.domain_pages[domain])
        records.append({"strategy": "all_domain_evaluation", "query_id": query["query_id"], "split": query["split"], "category": query["category"], "activate_pages": list(domain_pages), **score(query, domain_pages, 1.0, "OK", max(1, len(domain_pages)))})
    return {"schema_version": 1, "kind": "phase3_5_isolated", "seed": SEED, "brain_pages": 1024, "records": records}


def integrated(manifest: dict, dataset: dict, physical_manifest: Path) -> dict:
    index, progressive = SemanticIndex(manifest), LexicalProgressiveRouter(SemanticIndex(manifest))
    lexical, gate = LexicalRouter(index), BasalGate(index)
    records = []
    queries = [query for query in dataset["queries"] if query["split"] == "holdout"]
    for strategy in ("lexical_phase3_8mib", "lexical_progressive_contextual"):
        states: dict[str, CognitiveState] = defaultdict(CognitiveState)
        for query in queries:
            if strategy == "lexical_phase3_8mib":
                routed = lexical.route(query["query"])
                pages = gate.apply(routed, 8).activate_pages
                decision_ms = 0.0
            else:
                state = states[query["sequence_id"]] if query["sequence_id"] else None
                if state is not None:
                    state.decay()
                tick = time.perf_counter_ns()
                routed = progressive.route(query["query"], state, True, True)
                decision_ms = (time.perf_counter_ns() - tick) / 1e6
                pages = routed.activate_pages
                if state is not None:
                    state.update(progressive.as_route_result(routed), pages)
            backend = MMapStorageBackend(physical_manifest)
            cold = backend.advise_drop_cache()
            io_before, mem_before = process_io(), process_memory()
            usage_before = resource.getrusage(resource.RUSAGE_SELF)
            cpu_start, started = time.process_time_ns(), time.perf_counter_ns()
            first_activation_ms, sink = None, 0
            with backend:
                for page_id in pages:
                    page = backend.get_page(page_id, validate=False)
                    sink ^= touch_view(page.data)
                    backend.release_page(page)
                    if first_activation_ms is None:
                        first_activation_ms = (time.perf_counter_ns() - started) / 1e6
            storage_ms = (time.perf_counter_ns() - started) / 1e6
            cpu_ms = (time.process_time_ns() - cpu_start) / 1e6
            usage_after = resource.getrusage(resource.RUSAGE_SELF)
            io_after, mem_after = process_io(), process_memory()
            records.append({
                "strategy": strategy, "query_id": query["query_id"], "category": query["category"],
                "best_effort_cold": cold, "active_pages": len(pages), "active_brain_mib": len(pages),
                "decision_ms": decision_ms, "tt_first_activation_ms": first_activation_ms,
                "storage_ms": storage_ms, "total_ms": decision_ms + storage_ms, "cpu_ms": cpu_ms,
                "logical_bytes": len(pages) * MIB,
                "physical_read_bytes": max(0, (io_after.get("read_bytes") or 0) - (io_before.get("read_bytes") or 0)),
                "minor_faults": usage_after.ru_minflt - usage_before.ru_minflt,
                "major_faults": usage_after.ru_majflt - usage_before.ru_majflt,
                "rss_delta_bytes": (mem_after.get("rss_bytes") or 0) - (mem_before.get("rss_bytes") or 0),
                "pss_delta_bytes": (mem_after.get("pss_bytes") or 0) - (mem_before.get("pss_bytes") or 0), "sink": sink,
            })
    return {"schema_version": 1, "kind": "phase3_5_integrated", "baseline": {"logical_page_mib": 1, "extent_mib": 4, "access": "logical-only", "custom_cache": False, "prefetch": False}, "records": records}


def summarize(isolated_payload: dict, integrated_payload: dict) -> dict:
    records = isolated_payload["records"]
    summaries = []
    for strategy in sorted({r["strategy"] for r in records}):
        rows = [r for r in records if r["strategy"] == strategy and r["split"] == "holdout"]
        if not rows:
            continue
        summaries.append({
            "strategy": strategy, "queries": len(rows),
            "recall": statistics.mean(r["routing_recall"] for r in rows),
            "precision": statistics.mean(r["routing_precision"] for r in rows),
            "active_brain_mib_median": statistics.median(r["active_brain_mib"] for r in rows),
            "active_brain_mib_mean": statistics.mean(r["active_brain_mib"] for r in rows),
            "activation_rate_mean": statistics.mean(r["activation_rate"] for r in rows),
            "false_confidence_rate": statistics.mean(bool(r["false_confidence"]) for r in rows),
            "decision_ms_median": statistics.median(r.get("decision_ms", 0) for r in rows),
            "decision_ms_p95": sorted(r.get("decision_ms", 0) for r in rows)[max(0, int(.95 * len(rows)) - 1)],
        })
    progressive_rows = [r for r in records if r["strategy"] == "lexical_progressive_contextual" and r["split"] == "holdout"]
    escalation = Counter(str(r["expansion_count"]) for r in progressive_rows)
    fallback = Counter(level for r in progressive_rows for level in r["fallback_levels"] if level != "lexical")
    calibration = []
    for low, high in ((0, .6), (.6, .8), (.8, .9), (.9, 1.01)):
        rows = [r for r in progressive_rows if low <= r["confidence"] < high]
        calibration.append({"confidence_range": [low, high], "count": len(rows), "actual_recall": statistics.mean(r["routing_recall"] for r in rows) if rows else None, "false_confidence_rate": statistics.mean(r["false_confidence"] for r in rows) if rows else None})
    category = []
    for name in sorted({r["category"] for r in progressive_rows}):
        rows = [r for r in progressive_rows if r["category"] == name]
        category.append({"category": name, "count": len(rows), "recall": statistics.mean(r["routing_recall"] for r in rows), "precision": statistics.mean(r["routing_precision"] for r in rows), "active_mib_mean": statistics.mean(r["active_brain_mib"] for r in rows)})
    storage = []
    for strategy in ("lexical_phase3_8mib", "lexical_progressive_contextual"):
        rows = [r for r in integrated_payload["records"] if r["strategy"] == strategy]
        storage.append({"strategy": strategy, "runs": len(rows), "active_mib_mean": statistics.mean(r["active_brain_mib"] for r in rows), "tt_first_activation_ms_median": statistics.median(r["tt_first_activation_ms"] for r in rows if r["tt_first_activation_ms"] is not None), "storage_ms_median": statistics.median(r["storage_ms"] for r in rows), "total_ms_median": statistics.median(r["total_ms"] for r in rows), "logical_bytes_total": sum(r["logical_bytes"] for r in rows), "physical_read_bytes_total": sum(r["physical_read_bytes"] for r in rows), "minor_faults_total": sum(r["minor_faults"] for r in rows), "major_faults_total": sum(r["major_faults"] for r in rows)})
    failures = [{"query_id": r["query_id"], "category": r["category"], "recall": r["routing_recall"], "precision": r["routing_precision"], "status": r["status"], "active_mib": r["active_brain_mib"], "missed_causes": r["required_page_causes_missed"]} for r in progressive_rows if r["routing_recall"] < 1 or r["status"] != "OK"]
    return {"schema_version": 1, "holdout_summaries": summaries, "progressive_escalation_distribution": dict(escalation), "progressive_fallback_distribution": dict(fallback), "confidence_calibration": calibration, "progressive_by_category": category, "storage_integration": storage, "remaining_failures": failures}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results/phase3_5")
    parser.add_argument("--semantic-manifest", type=Path, default=ROOT / "brain_data/synthetic-1gib-seed-20260807/semantic-manifest.json")
    parser.add_argument("--dataset", type=Path, default=ROOT / "benchmarks/data/phase3_5-queries.json")
    parser.add_argument("--physical-manifest", type=Path, default=ROOT / "brain_data/synthetic-1gib-seed-20260807/manifest-1048576.json")
    args = parser.parse_args()
    manifest = generate_semantic_manifest(args.semantic_manifest, 1024, SEED)
    dataset = generate_recall_dataset(args.dataset, manifest, SEED)
    isolated_payload = isolated(manifest, dataset)
    integrated_payload = integrated(manifest, dataset, args.physical_manifest)
    atomic_json(args.output_dir / "isolated.json", isolated_payload)
    atomic_json(args.output_dir / "integrated-storage.json", integrated_payload)
    atomic_json(args.output_dir / "summary.json", summarize(isolated_payload, integrated_payload))
    print(args.output_dir)


if __name__ == "__main__":
    main()
