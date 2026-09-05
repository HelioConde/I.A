#!/usr/bin/env python3
from __future__ import annotations

import json
import statistics
from pathlib import Path

from phase4b_benchmark import aggregate


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results/phase4b"
MIB = 1024**2


def med(items, key):
    values = [item[key] for item in items if isinstance(item.get(key), (int, float))]
    return statistics.median(values) if values else None


def main() -> None:
    runs = json.loads((RESULTS / "runs.json").read_text())
    calibration = json.loads((RESULTS / "calibration.json").read_text())
    aggregates = aggregate(runs)
    (RESULTS / "aggregate.json").write_text(json.dumps(aggregates, indent=2, sort_keys=True) + "\n")
    workloads = ("realistic_mix", "long_gap_return", "a_b_a", "random_topics", "zipf_topic_popularity", "stable_topic")
    policies = ("kernel_only", "lru", "lfu", "lrfu", "cognitive_v0")
    by_workload = []
    for workload in workloads:
        row = {"workload": workload, "budget_mib": 64, "policies": {}}
        for policy in policies:
            items = [item for item in runs if item["track"] == "main" and item["workload"] == workload
                     and item["budget_mib"] == 64 and item["policy"] == policy]
            row["policies"][policy] = {
                "physical_read_bytes_median": med(items, "physical_read_bytes"),
                "logical_miss_bytes_median": med(items, "logical_miss_bytes"),
                "major_faults_median": med(items, "major_faults"), "minor_faults_median": med(items, "minor_faults"),
                "resident_hit_rate_median": med(items, "resident_hit_rate"), "policy_hit_rate_median": med(items, "policy_hit_rate"),
                "ghost_hits_median": med(items, "ghost_hit_count"), "false_hot_median": med(items, "false_hot_count"),
                "return_read_bytes_median": med(items, "return_physical_read_bytes"),
                "transition_read_bytes_median": med(items, "transition_physical_read_bytes"),
            }
        lru, cognitive = row["policies"]["lru"], row["policies"]["cognitive_v0"]
        physical_saved = lru["physical_read_bytes_median"] - cognitive["physical_read_bytes_median"]
        logical_saved = lru["logical_miss_bytes_median"] - cognitive["logical_miss_bytes_median"]
        row["cognitive_vs_lru"] = {"physical_saved_bytes": physical_saved, "logical_saved_bytes": logical_saved,
                                    "realized_savings_ratio": physical_saved / logical_saved if logical_saved > 0 else None}
        by_workload.append(row)
    totals = {}
    for policy in policies:
        records = [row["policies"][policy] for row in by_workload]
        totals[policy] = {key: sum(record[key] for record in records if record[key] is not None)
                          for key in ("physical_read_bytes_median", "logical_miss_bytes_median", "major_faults_median", "minor_faults_median")}
    lru_physical = totals["lru"]["physical_read_bytes_median"]
    cog_physical = totals["cognitive_v0"]["physical_read_bytes_median"]
    lru_logical = totals["lru"]["logical_miss_bytes_median"]
    cog_logical = totals["cognitive_v0"]["logical_miss_bytes_median"]
    physical_saved = lru_physical - cog_physical; logical_saved = lru_logical - cog_logical
    shadows = [item for item in runs if item["track"] == "shadow"]
    main_pageout = [item for item in runs if item["track"] == "main" and item["controller"] == "madv_pageout"
                    and item["mode"] == "observability"]
    performance = [item for item in runs if item["track"] == "performance"]
    cardinality = [item for item in runs if item["track"] == "cardinality"]
    summary = {
        "schema_version": 1, "runs": len(runs), "repetitions": 2, "order_seed": 20260807,
        "corpus_bytes": 1024 * MIB, "logical_page_bytes": MIB, "four_gib_materialized": False,
        "child_cgroup": calibration["child_cgroup"], "api_calibration": calibration["apis"],
        "budget_64_by_workload": by_workload, "budget_64_aggregate": totals,
        "cognitive_vs_lru_aggregate": {"physical_saved_bytes": physical_saved, "logical_saved_bytes": logical_saved,
                                           "realized_savings_ratio": physical_saved / logical_saved if logical_saved > 0 else None},
        "shadow": {"runs": len(shadows), "physical_read_bytes_median": med(shadows, "physical_read_bytes"),
                   "resident_hit_rate_median": med(shadows, "resident_hit_rate"),
                   "ghost_hits_median": med(shadows, "ghost_hit_count"), "false_hot_median": med(shadows, "false_hot_count")},
        "pageout": {"eviction_effectiveness_median": med(main_pageout, "eviction_effectiveness_immediate"),
                    "intervention_p50_us_median": statistics.median([x["intervention"]["intervention_us"]["p50"] for x in main_pageout]),
                    "intervention_p95_us_median": statistics.median([x["intervention"]["intervention_us"]["p95"] for x in main_pageout]),
                    "intervention_p99_us_median": statistics.median([x["intervention"]["intervention_us"]["p99"] for x in main_pageout]),
                    "budget_overshoot_p95_bytes_median": statistics.median([x["budget_overshoot_bytes"]["p95"] for x in main_pageout
                                                                             if x["budget_overshoot_bytes"]["p95"] is not None]),
                    "physical_regret_8_total": sum(x["physical_eviction_regret"]["8"] for x in main_pageout)},
        "performance": {policy: {"access_p50_us_median": statistics.median([x["access_latency_us"]["p50"] for x in performance if x["policy"] == policy]),
                                   "access_p95_us_median": statistics.median([x["access_latency_us"]["p95"] for x in performance if x["policy"] == policy]),
                                   "physical_read_bytes_median": statistics.median([x["physical_read_bytes"] for x in performance if x["policy"] == policy])}
                        for policy in ("kernel_only", "lru", "cognitive_v0")},
        "cardinality": cardinality,
        "no_duplication": {"anonymous_rss_growth_bytes_median": med(runs, "anonymous_rss_growth_bytes"),
                           "anonymous_rss_growth_bytes_max": max(x["anonymous_rss_growth_bytes"] for x in runs),
                           "threshold_bytes": 8 * MIB,
                           "passed": max(x["anonymous_rss_growth_bytes"] for x in runs) < 8 * MIB},
        "metadata_100g_estimate": {"pages": 102400, "cognitive_python_bytes": round(259.37 * 102400),
                                   "lru_python_bytes": round(37.42 * 102400),
                                   "caveat": "linear extrapolation of Phase 4A Python-object measurements, not a production representation"},
        "quality_invariant": "Router and trace content/order are frozen; residency runs consume the trace and cannot alter Recall/Precision.",
    }
    (RESULTS / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary["cognitive_vs_lru_aggregate"], sort_keys=True))


if __name__ == "__main__": main()
