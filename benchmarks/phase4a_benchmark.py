#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brain_ssd.cache_policy import (
    AdaptiveTwoQueuePolicy, BeladyOraclePolicy, CacheEvent, CognitiveCacheV0,
    LFUPolicy, LRFUPolicy, LRUPolicy, NoCachePolicy,
)
from brain_ssd.cache_simulator import simulate
from brain_ssd.cache_trace import CognitiveTraceGenerator, WORKLOADS, read_trace, write_trace
from brain_ssd.router import SemanticIndex
from brain_ssd.semantic import generate_semantic_manifest

MIB = 1024**2
SEED = 20260807
BUDGETS = (4, 8, 16, 32, 64, 128)


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def ensure_traces(root: Path, generator: CognitiveTraceGenerator) -> list[dict]:
    specifications = [("development", 500), ("development", 1000), ("holdout", 100), ("holdout", 5000)]
    manifest = []
    for split, turns in specifications:
        for workload_index, workload in enumerate(WORKLOADS):
            path = root / split / f"{workload}-{turns}.jsonl.gz"
            if path.exists():
                header, _ = read_trace(path)
                if header["turns"] != turns or header["workload"] != workload or header["split"] != split:
                    raise RuntimeError(f"trace mismatch: {path}")
            else:
                offset = (0 if split == "development" else 1_000_000) + turns * 100 + workload_index
                header, events = generator.generate(workload, turns, split, offset)
                write_trace(path, header, events)
            manifest.append({"path": str(path.relative_to(ROOT)), **header})
    return manifest


WEIGHT_CANDIDATES = {
    "balanced": {"recency": .28, "frequency": .20, "topic": .20, "transition": .12, "reload": .05, "provenance": .08, "hysteresis": .10, "age": .03},
    "recency": {"recency": .45, "frequency": .10, "topic": .18, "transition": .08, "reload": .03, "provenance": .06, "hysteresis": .12, "age": .05},
    "topic_frequency": {"recency": .18, "frequency": .27, "topic": .30, "transition": .10, "reload": .03, "provenance": .08, "hysteresis": .07, "age": .05},
    "association": {"recency": .18, "frequency": .16, "topic": .20, "transition": .28, "reload": .03, "provenance": .08, "hysteresis": .10, "age": .03},
    "simple": {"recency": .40, "frequency": .30, "topic": .20, "transition": 0, "reload": 0, "provenance": 0, "hysteresis": .08, "age": .02},
}


def calibrate(trace_root: Path) -> dict:
    trials = []
    trace_paths = sorted((trace_root / "development").glob("*.jsonl.gz"))
    for name, weights in WEIGHT_CANDIDATES.items():
        miss_bytes = pollution = regret = 0
        decision_us = 0.0
        for path in trace_paths:
            header, events = read_trace(path)
            if header["turns"] not in (500, 1000): continue
            for budget in (8, 16, 32):
                result = simulate(CognitiveCacheV0(budget, weights), events)
                miss_bytes += result["miss_bytes"]
                pollution += result["pollution_bytes"]
                regret += result["eviction_regret"]["8"]["count"]
                decision_us += result["decision_overhead_us"]["cpu_proxy_total_us"]
        trials.append({"name": name, "weights": weights, "miss_bytes": miss_bytes, "pollution_bytes": pollution, "eviction_regret_8_count": regret, "decision_total_us": decision_us})
    chosen = min(trials, key=lambda row: (row["miss_bytes"], row["eviction_regret_8_count"], row["pollution_bytes"], row["name"]))
    return {"schema_version": 1, "selection_policy": "development only: miss bytes, regret@8, pollution, deterministic name", "trace_paths": [str(path.relative_to(ROOT)) for path in trace_paths], "trials": trials, "chosen": chosen}


def make_policy(name: str, budget: int, events: list[CacheEvent], weights: dict[str, float]):
    if name == "no_cache": return NoCachePolicy()
    if name == "lru": return LRUPolicy(budget)
    if name == "lfu": return LFUPolicy(budget)
    if name == "lrfu": return LRFUPolicy(budget)
    if name == "adaptive_2q": return AdaptiveTwoQueuePolicy(budget)
    if name == "cognitive_v0": return CognitiveCacheV0(budget, weights)
    if name == "belady_oracle": return BeladyOraclePolicy(budget, events)
    raise ValueError(name)


def final_matrix(trace_root: Path, weights: dict[str, float]) -> list[dict]:
    records = []
    for path in sorted((trace_root / "holdout").glob("*-5000.jsonl.gz")):
        header, events = read_trace(path)
        for budget in BUDGETS:
            for policy_name in ("no_cache", "lru", "lfu", "lrfu", "adaptive_2q", "cognitive_v0", "belady_oracle"):
                result = simulate(make_policy(policy_name, budget, events, weights), events)
                records.append({"split": "holdout", "workload": header["workload"], "turns": header["turns"], "trace": str(path.relative_to(ROOT)), "requested_budget_mib": budget, **result})
    return records


ABLATIONS = {
    "full": set(), "without_topic": {"topic"}, "without_frequency": {"frequency"},
    "without_transition": {"transition"}, "without_reload": {"reload"},
    "without_hysteresis": {"hysteresis"}, "without_provenance": {"provenance"},
}


def ablation_matrix(trace_root: Path, weights: dict[str, float]) -> list[dict]:
    records = []
    for path in sorted((trace_root / "holdout").glob("*-5000.jsonl.gz")):
        header, events = read_trace(path)
        for name, disabled in ABLATIONS.items():
            result = simulate(CognitiveCacheV0(16, weights, disabled), events)
            records.append({"workload": header["workload"], "budget_mib": 16, "ablation": name, **result})
    return records


def metadata_scaling(weights: dict[str, float]) -> list[dict]:
    records = []
    for name in ("lru", "lfu", "lrfu", "adaptive_2q", "cognitive_v0"):
        policy = make_policy(name, 128, [], weights)
        empty = policy.metadata_bytes()
        for page_id in range(1000):
            item = CacheEvent(page_id, f"m{page_id}", page_id, page_id, "synthetic", (f"topic{page_id % 40}",), ("CURRENT_QUERY",), None, None, 1.0, {"topics": [f"topic{page_id % 40}"]}, MIB, MIB, reload_cost=1.0)
            policy.update_state(page_id, item.cognitive_state); policy.observe_access(item)
        measured = policy.metadata_bytes(); per_page = max(0, measured - empty) / 1000
        records.append({"policy": name, "measured_pages": 1000, "empty_bytes": empty, "measured_metadata_bytes": measured, "incremental_bytes_per_observed_page": per_page, "extrapolated_100k_bytes": empty + per_page * 100_000, "extrapolated_1m_bytes": empty + per_page * 1_000_000, "extrapolation": "linear from 1K unique-page synthetic metadata; excludes page data and allocator nonlinearities"})
    return records


def summarize(records: list[dict], ablations: list[dict], metadata: list[dict]) -> dict:
    aggregate = []
    for policy in sorted({record["policy"] for record in records}):
        for budget in BUDGETS:
            rows = [record for record in records if record["policy"] == policy and record["requested_budget_mib"] == budget]
            aggregate.append({
                "policy": policy, "budget_mib": budget,
                "page_hit_rate_mean": statistics.mean(row["page_hit_rate"] for row in rows),
                "byte_hit_rate_mean": statistics.mean(row["byte_hit_rate"] for row in rows),
                "miss_bytes_total": sum(row["miss_bytes"] for row in rows),
                "cold_load_count_total": sum(row["cold_load_count"] for row in rows),
                "eviction_count_total": sum(row["eviction_count"] for row in rows),
                "eviction_regret_8_rate_mean": statistics.mean(row["eviction_regret"]["8"]["rate"] for row in rows),
                "pollution_bytes_total": sum(row["pollution_bytes"] for row in rows),
                "cache_churn_pages_total": sum(row["cache_churn_pages_total"] for row in rows),
                "return_cost_bytes_total": sum(row["return_cost_bytes"] for row in rows),
                "topic_transition_cost_bytes_total": sum(row["topic_transition_cost_bytes"] for row in rows),
                "decision_total_p50_us_mean": statistics.mean(row["decision_overhead_us"]["total_p50"] for row in rows),
                "decision_total_p95_us_mean": statistics.mean(row["decision_overhead_us"]["total_p95"] for row in rows),
                "decision_total_p99_us_mean": statistics.mean(row["decision_overhead_us"]["total_p99"] for row in rows),
                "metadata_bytes_mean": statistics.mean(row["metadata_bytes"] for row in rows),
            })
    gaps = []
    for workload in WORKLOADS:
        for budget in BUDGETS:
            lookup = {(row["policy"]): row for row in records if row["workload"] == workload and row["requested_budget_mib"] == budget}
            lru, cognitive, oracle = lookup["lru"], lookup["cognitive_v0"], lookup["belady_oracle"]
            denominator = lru["miss_bytes"] - oracle["miss_bytes"]
            gaps.append({"workload": workload, "budget_mib": budget, "lru_miss_bytes": lru["miss_bytes"], "cognitive_miss_bytes": cognitive["miss_bytes"], "oracle_miss_bytes": oracle["miss_bytes"], "cognitive_vs_lru_saved_bytes": lru["miss_bytes"] - cognitive["miss_bytes"], "lru_oracle_gap_closed": (lru["miss_bytes"] - cognitive["miss_bytes"]) / denominator if denominator > 0 else None})
    ablation_summary = []
    for name in ABLATIONS:
        rows = [row for row in ablations if row["ablation"] == name]
        ablation_summary.append({"ablation": name, "miss_bytes_total": sum(row["miss_bytes"] for row in rows), "pollution_bytes_total": sum(row["pollution_bytes"] for row in rows), "regret_8_rate_mean": statistics.mean(row["eviction_regret"]["8"]["rate"] for row in rows), "decision_p95_us_mean": statistics.mean(row["decision_overhead_us"]["total_p95"] for row in rows)})
    best_budget = {}
    for policy in ("lru", "lfu", "lrfu", "adaptive_2q", "cognitive_v0", "belady_oracle"):
        rows = [row for row in aggregate if row["policy"] == policy]
        minimum = min(row["miss_bytes_total"] for row in rows)
        eligible = [row for row in rows if row["miss_bytes_total"] <= minimum * 1.01]
        best_budget[policy] = min(eligible, key=lambda row: row["budget_mib"])["budget_mib"]
    return {"schema_version": 1, "aggregate": aggregate, "lru_oracle_gaps": gaps, "ablation": ablation_summary, "metadata_scaling": metadata, "diminishing_return_budget_within_1pct_minimum": best_budget}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results/phase4a")
    parser.add_argument("--semantic-manifest", type=Path, default=ROOT / "brain_data/synthetic-1gib-seed-20260807/semantic-manifest.json")
    args = parser.parse_args()
    manifest = generate_semantic_manifest(args.semantic_manifest, 1024, SEED)
    index = SemanticIndex(manifest)
    generator = CognitiveTraceGenerator(index)
    trace_root = args.output_dir / "traces"
    trace_manifest = ensure_traces(trace_root, generator)
    calibration = calibrate(trace_root)
    weights = calibration["chosen"]["weights"]
    records = final_matrix(trace_root, weights)
    ablations = ablation_matrix(trace_root, weights)
    metadata = metadata_scaling(weights)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    atomic_json(args.output_dir / "trace-manifest.json", {"schema_version": 1, "traces": trace_manifest})
    atomic_json(args.output_dir / "calibration.json", calibration)
    atomic_json(args.output_dir / "matrix.json", {"schema_version": 1, "kind": "phase4a_policy_matrix", "records": records})
    atomic_json(args.output_dir / "ablations.json", {"schema_version": 1, "records": ablations})
    atomic_json(args.output_dir / "summary.json", summarize(records, ablations, metadata))
    print(args.output_dir)


if __name__ == "__main__":
    main()
