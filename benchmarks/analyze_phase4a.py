#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results/phase4a"


def main() -> None:
    summary = json.loads((RESULTS / "summary.json").read_text())
    calibration = json.loads((RESULTS / "calibration.json").read_text())
    budget = 64
    rows = [row for row in summary["aggregate"] if row["budget_mib"] == budget]
    lines = [
        "# Phase 4A measured summary", "",
        f"Development selected Cognitive weights `{calibration['chosen']['name']}`.", "",
        f"## Aggregate at {budget} MiB", "",
        "| Policy | Hit rate | Miss GiB | Evictions | Regret@8 | Pollution GiB | Churn pages | Decision p95 us | Metadata KiB |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['policy']} | {row['page_hit_rate_mean']:.4f} | {row['miss_bytes_total']/1024**3:.3f} | "
            f"{row['eviction_count_total']} | {row['eviction_regret_8_rate_mean']:.4f} | "
            f"{row['pollution_bytes_total']/1024**3:.3f} | {row['cache_churn_pages_total']} | "
            f"{row['decision_total_p95_us_mean']:.2f} | {row['metadata_bytes_mean']/1024:.2f} |"
        )
    lines += ["", "## Cognitive versus LRU by workload at 64 MiB", "", "| Workload | LRU miss MiB | Cognitive miss MiB | Saved MiB | Oracle miss MiB | Gap closed |", "|---|---:|---:|---:|---:|---:|"]
    for row in summary["lru_oracle_gaps"]:
        if row["budget_mib"] != budget: continue
        gap = "n/a" if row["lru_oracle_gap_closed"] is None else f"{100*row['lru_oracle_gap_closed']:.1f}%"
        lines.append(f"| {row['workload']} | {row['lru_miss_bytes']/1024**2:.0f} | {row['cognitive_miss_bytes']/1024**2:.0f} | {row['cognitive_vs_lru_saved_bytes']/1024**2:.0f} | {row['oracle_miss_bytes']/1024**2:.0f} | {gap} |")
    lines += ["", "This is policy simulation only. No mmap residency, page copying, mlock, or prefetch is performed.", ""]
    (RESULTS / "SUMMARY.md").write_text("\n".join(lines))


if __name__ == "__main__":
    main()
