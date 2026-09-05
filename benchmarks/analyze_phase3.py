#!/usr/bin/env python3
from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results/phase3"


def mean(items, key):
    return statistics.mean(item[key] for item in items) if items else 0.0


def main() -> None:
    canonical_payload = json.loads((RESULTS / "canonical.json").read_text())
    records = canonical_payload["records"]
    matrix = []
    for router in ("oracle", "all_domain", "random_k", "lexical"):
        for budget in (4, 8, 16, 32, 64):
            rows = [item for item in records if item["router"] == router and item["budget_mib"] == budget]
            matrix.append({
                "router": router, "budget_mib": budget,
                "routing_recall": mean(rows, "routing_recall"),
                "routing_precision": mean(rows, "routing_precision"),
                "required_page_miss_rate": mean(rows, "required_page_miss_rate"),
                "activation_rate": mean(rows, "circuit_activation_rate"),
                "active_brain_size_bytes": mean(rows, "active_brain_size_bytes"),
                "router_latency_ms_p50_across_queries": statistics.median(item["router_latency_ms_p50"] for item in rows),
                "router_latency_ms_p95_across_queries": statistics.median(item["router_latency_ms_p95"] for item in rows),
                "router_cpu_ms_p50_across_queries": statistics.median(item["router_cpu_ms_p50"] for item in rows),
                "avoided_logical_bytes_vs_all_brain": mean(rows, "avoided_logical_bytes_vs_all_brain"),
            })
    category = []
    for budget in (4, 8, 16, 32, 64):
        for query_type in sorted({item["query_type"] for item in records}):
            rows = [item for item in records if item["router"] == "lexical" and item["budget_mib"] == budget and item["query_type"] == query_type]
            category.append({"budget_mib": budget, "query_type": query_type, "count": len(rows), "recall": mean(rows, "routing_recall"), "precision": mean(rows, "routing_precision"), "miss_rate": mean(rows, "required_page_miss_rate")})
    switch_records = json.loads((RESULTS / "topic-switch.json").read_text())["records"]
    switching = []
    for budget in (4, 8, 16):
        for mode in ("stateless", "state", "hysteresis"):
            rows = [item for item in switch_records if item["budget_mib"] == budget and item["mode"] == mode]
            switching.append({
                "budget_mib": budget, "mode": mode, "recall": mean(rows, "routing_recall"),
                "precision": mean(rows, "routing_precision"),
                "activation_churn_pages_total": sum(item["activation_churn_pages"] for item in rows),
                "unnecessary_domain_changes": sum(item["selected_domain"] != item["expected_domain"] for item in rows),
                "kept_by_hysteresis_total": sum(item["kept_by_hysteresis"] for item in rows),
            })
    integrated = json.loads((RESULTS / "integrated-storage.json").read_text())["records"]
    physical = []
    for router in ("oracle", "lexical"):
        for budget in (4, 8, 16):
            rows = [item for item in integrated if item["router"] == router and item["budget_mib"] == budget]
            physical.append({
                "router": router, "budget_mib": budget, "runs": len(rows),
                "latency_ms_median": statistics.median(item["latency_ms"] for item in rows),
                "cpu_ms_median": statistics.median(item["cpu_ms"] for item in rows),
                "logical_bytes_total": sum(item["logical_bytes"] for item in rows),
                "physical_read_bytes_total": sum(item["physical_read_bytes"] for item in rows),
                "best_effort_cold_only": all(item["best_effort_cold"] for item in rows),
            })
    summary = {
        "schema_version": 1, "matrix": matrix, "lexical_by_query_type": category,
        "topic_switch": switching, "physical_integration": physical,
        "index": canonical_payload["index"],
        "cardinality": json.loads((RESULTS / "cardinality.json").read_text())["records"],
        "limitations": [
            "Synthetic metadata and queries are easier and less diverse than natural language.",
            "Cold storage is best-effort POSIX_FADV_DONTNEED, not a guaranteed physical SSD miss.",
            "No private hard 8 GiB cgroup was used; Codespace results do not validate an 8 GiB PC.",
            "The compact cardinality benchmark measures postings, not full Python metadata objects.",
            "Avoided physical bytes versus ALL_BRAIN are not claimed because ALL_BRAIN was not physically read for every query.",
        ],
        "negative_results": [
            "Lexical recall plateaus below 100% over the complete dataset even at 64 MiB.",
            "At 4 MiB, hysteresis reduces churn but introduces additional required-page misses.",
            "State boosts alone did not reduce churn in the canonical explicit topic-switch sequence.",
            "Random-K requires a large budget to approach high recall and remains imprecise.",
            "Ambiguous, distractor and unknown inputs expose lexical routing limitations.",
        ],
    }
    (RESULTS / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")

    lines = ["# Phase 3 measured summary", "", "| Router | Budget MiB | Recall | Precision | Miss rate | Activation | Active MiB | Router p50 ms | Avoided MiB vs all |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for item in matrix:
        lines.append(f"| {item['router']} | {item['budget_mib']} | {item['routing_recall']:.3f} | {item['routing_precision']:.3f} | {item['required_page_miss_rate']:.3f} | {100*item['activation_rate']:.3f}% | {item['active_brain_size_bytes']/1048576:.2f} | {item['router_latency_ms_p50_across_queries']:.4f} | {item['avoided_logical_bytes_vs_all_brain']/1048576:.2f} |")
    lines += ["", "## Topic switch", "", "| Budget MiB | Mode | Recall | Precision | Total churn | Hysteresis-kept | Wrong domain |", "|---:|---|---:|---:|---:|---:|---:|"]
    for item in switching:
        lines.append(f"| {item['budget_mib']} | {item['mode']} | {item['recall']:.3f} | {item['precision']:.3f} | {item['activation_churn_pages_total']} | {item['kept_by_hysteresis_total']} | {item['unnecessary_domain_changes']} |")
    lines += ["", "Physical reads are best-effort-cold observations; they are not proof of a physical SSD miss.", ""]
    (RESULTS / "SUMMARY.md").write_text("\n".join(lines))


if __name__ == "__main__":
    main()
