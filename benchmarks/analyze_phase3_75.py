#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results/phase3_75"


def main() -> None:
    summary = json.loads((RESULTS / "summary.json").read_text())
    calibration = json.loads((RESULTS / "calibration.json").read_text())
    lines = [
        "# Phase 3.75 measured summary", "",
        f"Development selected `{calibration['chosen']['method']}` with threshold {calibration['chosen']['semantic_threshold']} and margin {calibration['chosen']['semantic_margin']}.", "",
        "| Strategy | Recall | Precision | Active median/mean MiB | Activation | False confidence | False early stop | Route p50/p95 ms |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in summary["holdout_summaries"]:
        lines.append(
            f"| {item['strategy']} | {item['recall']:.4f} | {item['precision']:.4f} | "
            f"{item['active_brain_mib_median']:.2f}/{item['active_brain_mib_mean']:.2f} | "
            f"{100*item['activation_rate_mean']:.3f}% | {100*item['false_confidence_rate']:.2f}% | "
            f"{100*item['false_early_stop_rate']:.2f}% | {item['route_ms_p50']:.4f}/{item['route_ms_p95']:.4f} |"
        )
    lines += [
        "", "## Hybrid cascade", "",
        f"- Semantic rescue rate: {100*summary['hybrid_semantic_rescue_rate']:.2f}%",
        f"- Rescue success without budget expansion: {100*summary['hybrid_rescue_success_rate']:.2f}%",
        f"- ALL_DOMAIN rate: {100*summary['hybrid_all_domain_rate']:.2f}%",
        f"- Context helpful bytes: {summary['context_helpful_bytes']}",
        f"- Context contamination bytes: {summary['context_contamination_bytes']}",
        f"- Expected average routing cost: {summary['expected_average_routing_cost_ms']:.4f} ms", "",
        "Cold storage measurements remain best-effort. Unknown recall=1 only denotes zero required pages and must be read with NO_KNOWLEDGE.", "",
    ]
    (RESULTS / "SUMMARY.md").write_text("\n".join(lines))


if __name__ == "__main__":
    main()
