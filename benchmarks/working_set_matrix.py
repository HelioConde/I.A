#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks"))

from storage_matrix import run_case


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 2 working-set curve")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output-directory", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=20260807)
    parser.add_argument("--memory-budget-mib", type=int, default=512)
    args = parser.parse_args()
    args.output_directory.mkdir(parents=True, exist_ok=True)
    page_mib = json.loads(args.manifest.read_text())["page_size_bytes"] // 1024**2
    accesses = max(1, 256 // page_mib)
    runs = []
    for working_set_mib in (64, 256, 512, 1024):
        for workload in ("uniform_random", "clustered"):
            for state in ("cold", "hot"):
                name = f"ws{working_set_mib}m-{workload}-{state}.json"
                payload = run_case(args.manifest, workload, state, args.seed, accesses, working_set_mib, args.memory_budget_mib, args.output_directory / name)
                runs.append({"file": name, "working_set_mib": working_set_mib, "workload": workload, "state": state, "metrics": payload["metrics"], "cache_evidence": payload["cache_evidence"]})
    summary = {
        "schema_version": 1, "experiment": "phase2-working-set-curve",
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "page_mib": page_mib,
        "memory_budget_mib_logical": args.memory_budget_mib, "runs": runs,
    }
    (args.output_directory / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"runs": len(runs), "summary": str(args.output_directory / "summary.json")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

