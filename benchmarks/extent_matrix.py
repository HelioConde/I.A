#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmarks" / "extent_benchmark.py"
COMBINATIONS_KIB = ((256, 4096), (256, 8192), (512, 4096), (512, 8192), (1024, 4096), (1024, 8192), (1024, 16384), (2048, 8192), (2048, 16384))


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 2.5 logical-page/storage-extent screening")
    parser.add_argument("--corpus-directory", required=True, type=Path)
    parser.add_argument("--output-directory", required=True, type=Path)
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--seed", type=int, default=20260807)
    parser.add_argument("--logical-mib-per-run", type=int, default=32)
    args = parser.parse_args()
    args.output_directory.mkdir(parents=True, exist_ok=True)
    runs = []
    for logical_kib, extent_kib in COMBINATIONS_KIB:
        accesses = max(16, args.logical_mib_per_run * 1024 // logical_kib)
        for layout in ("colocated", "random"):
            manifest = args.corpus_directory / f"layout-l{logical_kib * 1024}-e{extent_kib * 1024}-{layout}.json"
            for workload in ("associative_walk", "topic_switch"):
                for mode in ("logical_only", "full_extent", "group_required"):
                    for repeat in range(args.repeat):
                        name = f"l{logical_kib}k-e{extent_kib}k-{layout}-{workload}-{mode}-r{repeat + 1}.json"
                        output = args.output_directory / name
                        command = [
                            sys.executable, str(BENCHMARK), "--manifest", str(manifest), "--workload", workload,
                            "--access-mode", mode, "--cache-state", "cold", "--seed", str(args.seed),
                            "--accesses", str(accesses), "--working-set-mib", "256", "--output", str(output),
                        ]
                        result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
                        if result.returncode:
                            raise RuntimeError(f"{name}: {result.stdout}\n{result.stderr}")
                        payload = json.loads(output.read_text())
                        runs.append({
                            "file": name, "logical_kib": logical_kib, "extent_kib": extent_kib,
                            "layout": layout, "workload": workload, "mode": mode, "repeat": repeat + 1,
                            "sequence_sha256": payload["sequence_sha256"], "segments": payload["segments"],
                            "metrics": payload["metrics"],
                        })
    summary = {"schema_version": 1, "experiment": "phase2_5-extent-matrix", "runs": runs}
    (args.output_directory / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"runs": len(runs), "summary": str(args.output_directory / "summary.json")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
