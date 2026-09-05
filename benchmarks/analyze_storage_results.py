#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path


def median_rows(rows: list[dict]) -> dict:
    keys = (
        "latency_ms_p50", "latency_ms_p95", "latency_ms_p99", "accesses_per_second",
        "logical_throughput_bytes_per_second", "physical_read_bytes", "physical_read_amplification",
        "rss_bytes_max", "pss_bytes_max", "rss_file_bytes_max", "anonymous_bytes_max",
        "minor_faults", "major_faults", "cpu_percent_avg_single_core_scale",
    )
    return {key: statistics.median(row[key] for row in rows if row.get(key) is not None) for key in keys}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--page-summary", required=True, type=Path)
    parser.add_argument("--working-set-summary", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    page_runs = json.loads(args.page_summary.read_text())["runs"]
    grouped: dict[tuple, list[dict]] = defaultdict(list)
    for run in page_runs:
        grouped[(run["page_mib"], run["workload"], run["state"])].append(run["metrics"])
    medians = [
        {"page_mib": page, "workload": workload, "state": state, **median_rows(rows)}
        for (page, workload, state), rows in sorted(grouped.items())
    ]
    winners = {}
    workloads = sorted({run["workload"] for run in page_runs})
    for workload in workloads:
        candidates = [row for row in medians if row["workload"] == workload]
        cold = [row for row in candidates if row["state"] == "cold"]
        hot = [row for row in candidates if row["state"] == "hot"]
        winners[workload] = {
            "cold_p95_latency_page_mib": min(cold, key=lambda row: row["latency_ms_p95"])["page_mib"],
            "cold_amplification_page_mib": min(cold, key=lambda row: row["physical_read_amplification"])["page_mib"],
            "hot_p95_latency_page_mib": min(hot, key=lambda row: row["latency_ms_p95"])["page_mib"],
        }
    working_runs = json.loads(args.working_set_summary.read_text())["runs"]
    payload = {
        "schema_version": 1,
        "page_matrix": {
            "run_count": len(page_runs),
            "success_count": sum(run["metrics"]["success"] for run in page_runs),
            "checksum_errors": sum(run["metrics"]["checksum_errors"] for run in page_runs),
            "cold_runs_with_nonzero_mapping_before": sum(
                run["cache_evidence"]["mapping_before_precondition"].get("rss_bytes", 0) > 0
                for run in page_runs if run["state"] == "cold"
            ),
            "medians": medians,
            "winners": winners,
        },
        "working_set_curve": {
            "run_count": len(working_runs),
            "success_count": sum(run["metrics"]["success"] for run in working_runs),
            "checksum_errors": sum(run["metrics"]["checksum_errors"] for run in working_runs),
            "runs": working_runs,
            "pgscan_total_delta": sum(run["metrics"].get("cgroup_delta_pgscan") or 0 for run in working_runs),
            "pgsteal_total_delta": sum(run["metrics"].get("cgroup_delta_pgsteal") or 0 for run in working_runs),
        },
        "interpretation_limits": [
            "Per-access latency includes SHA-256 validation of the full page.",
            "Warm state inherits Linux cache state from prior processes and is observational, not controlled to an exact residency ratio.",
            "Cgroup memory metrics cover the whole Codespace cgroup, not only the benchmark process.",
            "Logical memory budget is configuration metadata, not a kernel-enforced hard limit.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

