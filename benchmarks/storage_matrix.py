#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmarks" / "storage_benchmark.py"
WORKLOADS = ("sequential", "uniform_random", "hot_set", "clustered", "topic_switch", "associative_walk")
STATES = ("cold", "warm", "hot")


def run_case(manifest: Path, workload: str, state: str, seed: int, accesses: int, working_set_mib: int, budget_mib: int, output: Path, validation_mode: str = "integrity") -> dict:
    command = [
        sys.executable, str(BENCHMARK), "--manifest", str(manifest), "--workload", workload,
        "--seed", str(seed), "--accesses", str(accesses), "--working-set-mib", str(working_set_mib),
        "--memory-budget-mib", str(budget_mib), "--cache-state", state,
        "--validation-mode", validation_mode, "--output", str(output),
    ]
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"case failed ({output.name}): {result.stdout}\n{result.stderr}")
    return json.loads(output.read_text())


def main() -> int:
    parser = argparse.ArgumentParser(description="Controlled Phase 2 page-size/workload/cache matrix")
    parser.add_argument("--corpus-directory", required=True, type=Path)
    parser.add_argument("--output-directory", required=True, type=Path)
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--seed", type=int, default=20260807)
    parser.add_argument("--logical-mib-per-run", type=int, default=256)
    parser.add_argument("--working-set-mib", type=int, default=256)
    parser.add_argument("--memory-budget-mib", type=int, default=512)
    parser.add_argument("--page-size-mib", type=float, action="append")
    parser.add_argument("--validation-mode", choices=("integrity", "performance", "first_activation"), default="integrity")
    args = parser.parse_args()
    if args.repeat < 1:
        parser.error("--repeat must be >= 1")
    args.output_directory.mkdir(parents=True, exist_ok=True)
    runs = []
    page_sizes = args.page_size_mib or [4, 8, 16, 32]
    for page_mib in page_sizes:
        page_bytes = int(page_mib * 1024**2)
        label = f"{page_mib:g}".replace(".", "_")
        manifest = args.corpus_directory / f"manifest-{page_bytes}.json"
        accesses = max(1, int(args.logical_mib_per_run / page_mib))
        for workload in WORKLOADS:
            for state in STATES:
                for repeat in range(args.repeat):
                    name = f"p{label}m-{workload}-{state}-r{repeat + 1}.json"
                    payload = run_case(
                        manifest, workload, state, args.seed, accesses, args.working_set_mib,
                        args.memory_budget_mib, args.output_directory / name, args.validation_mode,
                    )
                    runs.append({"file": name, "page_mib": page_mib, "workload": workload, "state": state, "repeat": repeat + 1, "metrics": payload["metrics"], "cache_evidence": payload["cache_evidence"]})
    summary = {
        "schema_version": 1, "experiment": "phase2-page-size-matrix",
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "configuration": vars(args) | {"corpus_directory": str(args.corpus_directory), "output_directory": str(args.output_directory)},
        "runs": runs,
    }
    (args.output_directory / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"runs": len(runs), "summary": str(args.output_directory / "summary.json")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
