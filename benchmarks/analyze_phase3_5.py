#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results/phase3_5"


def main() -> None:
    summary = json.loads((RESULTS / "summary.json").read_text())
    lines = [
        "# Phase 3.5 measured summary", "",
        "| Strategy | Holdout recall | Precision | Median active MiB | Mean active MiB | Activation | False confidence | Decision p50/p95 ms |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in summary["holdout_summaries"]:
        lines.append(
            f"| {item['strategy']} | {item['recall']:.4f} | {item['precision']:.4f} | "
            f"{item['active_brain_mib_median']:.2f} | {item['active_brain_mib_mean']:.2f} | "
            f"{100*item['activation_rate_mean']:.3f}% | {100*item['false_confidence_rate']:.2f}% | "
            f"{item['decision_ms_median']:.4f}/{item['decision_ms_p95']:.4f} |"
        )
    lines += ["", "## Escalation", ""]
    total = sum(summary["progressive_escalation_distribution"].values())
    for count, value in sorted(summary["progressive_escalation_distribution"].items(), key=lambda item: int(item[0])):
        lines.append(f"- {count} expansions: {value}/{total} ({100*value/total:.1f}%)")
    lines += ["", "## Fallback events", ""]
    for name, value in sorted(summary["progressive_fallback_distribution"].items()):
        lines.append(f"- {name}: {value}")
    lines += ["", "Physical reads are best-effort-cold observations. Recall for unknown queries uses required_count=0 and must be read together with NO_KNOWLEDGE status.", ""]
    (RESULTS / "SUMMARY.md").write_text("\n".join(lines))


if __name__ == "__main__":
    main()
