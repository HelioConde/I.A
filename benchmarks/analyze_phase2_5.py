#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path

PAGES = (.25, .5, 1, 2, 4, 8)


def median(rows: list[dict], key: str):
    values = [row[key] for row in rows if row.get(key) is not None]
    return statistics.median(values) if values else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--performance", required=True, type=Path)
    parser.add_argument("--integrity", required=True, type=Path)
    parser.add_argument("--extents", required=True, type=Path)
    parser.add_argument("--phase2", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    performance = json.loads(args.performance.read_text())["runs"]
    integrity = json.loads(args.integrity.read_text())
    extents = json.loads(args.extents.read_text())["runs"]
    phase2 = json.loads(args.phase2.read_text())["page_matrix"]["medians"]

    page_medians = []
    for page in PAGES:
        for state in ("cold", "warm", "hot"):
            rows = [run["metrics"] for run in performance if run["page_mib"] == page and run["state"] == state]
            sample_run = next(run for run in performance if run["page_mib"] == page)
            sample = json.loads((args.performance.parent / sample_run["file"]).read_text())
            page_medians.append({
                "page_mib": page, "state": state,
                **{key: median(rows, key) for key in (
                    "latency_ms_p50", "latency_ms_p95", "latency_ms_p99", "accesses_per_second",
                    "physical_read_amplification", "useful_byte_ratio", "minor_faults_per_access",
                    "cpu_ms_per_access", "rss_bytes_max", "pss_bytes_max",
                )},
                "activation_cost_score": statistics.median(row["activation_cost"]["score_ms_plus_mib_plus_cpu_ms"] for row in rows),
                "manifest_bytes": sample["configuration"]["manifest_bytes"],
                "metadata_bytes_per_page": sample["configuration"]["metadata_bytes_per_page"],
            })
    workload_winners = {}
    for workload in sorted({run["workload"] for run in performance}):
        candidates = {
            page: [run["metrics"] for run in performance if run["state"] == "cold" and run["page_mib"] == page and run["workload"] == workload]
            for page in PAGES
        }
        workload_winners[workload] = {
            "p95_page_mib": min(PAGES, key=lambda page: median(candidates[page], "latency_ms_p95")),
            "activation_cost_page_mib": min(PAGES, key=lambda page: statistics.median(row["activation_cost"]["score_ms_plus_mib_plus_cpu_ms"] for row in candidates[page])),
            "amplification_page_mib": min(PAGES, key=lambda page: median(candidates[page], "physical_read_amplification")),
        }

    sha_impact = {}
    for page in (4, 8):
        old = statistics.median(row["latency_ms_p95"] for row in phase2 if row["page_mib"] == page and row["state"] == "cold")
        new = next(row["latency_ms_p95"] for row in page_medians if row["page_mib"] == page and row["state"] == "cold")
        sha_impact[str(page)] = {"integrity_p95_ms": old, "performance_p95_ms": new, "reduction_percent": 100 * (old - new) / old}

    extent_groups: dict[tuple, list[dict]] = defaultdict(list)
    sequence_groups: dict[tuple, set[str]] = defaultdict(set)
    for run in extents:
        key = (run["logical_kib"], run["extent_kib"], run["layout"], run["workload"], run["mode"])
        extent_groups[key].append(run["metrics"])
        sequence_groups[(run["logical_kib"], run["extent_kib"], run["workload"])].add(run["sequence_sha256"])
    extent_medians = []
    for key, rows in sorted(extent_groups.items()):
        extent_medians.append({
            "logical_kib": key[0], "extent_kib": key[1], "layout": key[2], "workload": key[3], "mode": key[4],
            **{metric: median(rows, metric) for metric in (
                "latency_ms_p95", "physical_read_bytes", "physical_read_amplification", "useful_byte_ratio",
                "coalesced_touch_amplification", "cpu_ms_per_access", "minor_faults_per_access",
            )},
            "activation_cost_score": statistics.median(row["activation_cost"]["score_ms_plus_mib_plus_cpu_ms"] for row in rows),
        })

    def extent_row(logical, extent, layout, workload, mode):
        return next(row for row in extent_medians if (row["logical_kib"], row["extent_kib"], row["layout"], row["workload"], row["mode"]) == (logical, extent, layout, workload, mode))

    representative = {}
    for layout in ("colocated", "random"):
        representative[layout] = {
            mode: extent_row(1024, 4096, layout, "associative_walk", mode)
            for mode in ("logical_only", "full_extent", "group_required")
        }

    topic_return = {}
    for layout in ("colocated", "random"):
        selected = [run for run in extents if run["logical_kib"] == 512 and run["extent_kib"] == 8192 and run["layout"] == layout and run["workload"] == "topic_switch" and run["mode"] == "full_extent"]
        a1 = statistics.median(next(segment for segment in run["segments"] if segment["segment"] == "A1")["physical_read_bytes"] for run in selected)
        a2 = statistics.median(next(segment for segment in run["segments"] if segment["segment"] == "A2")["physical_read_bytes"] for run in selected)
        topic_return[layout] = {"A1_physical_bytes": a1, "A2_physical_bytes": a2, "return_reduction_percent": 100 * (a1 - a2) / a1}

    payload = {
        "schema_version": 1,
        "integrity": integrity,
        "performance": {
            "run_count": len(performance), "success_count": sum(run["metrics"]["success"] for run in performance),
            "checksum_errors": sum(run["metrics"]["checksum_errors"] for run in performance),
            "page_medians": page_medians, "workload_winners": workload_winners, "sha_impact": sha_impact,
        },
        "extents": {
            "run_count": len(extents), "success_count": sum(run["metrics"]["success"] for run in extents),
            "checksum_errors": sum(run["metrics"]["checksum_errors"] for run in extents),
            "sequence_mismatch_count": sum(len(hashes) != 1 for hashes in sequence_groups.values()),
            "medians": extent_medians, "representative_l1m_e4m_associative": representative,
            "topic_return_l512k_e8m_full_extent": topic_return,
        },
        "recommended_baseline": {
            "logical_page_kib": 1024,
            "storage_extent_kib": 4096,
            "default_access_mode": "logical_only",
            "reason": "1 MiB is the measured latency/amplification/metadata knee; 4 MiB is the least harmful screened extent, but whole-extent reads remain opt-in experimental.",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
