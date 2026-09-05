#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmarks" / "storage_benchmark.py"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output-directory", required=True, type=Path)
    args = parser.parse_args()
    args.output_directory.mkdir(parents=True, exist_ok=True)
    runs = []
    for mode in ("integrity", "first_activation", "performance"):
        for repeat in range(3):
            output = args.output_directory / f"{mode}-r{repeat + 1}.json"
            command = [
                sys.executable, str(BENCHMARK), "--manifest", str(args.manifest),
                "--workload", "hot_set", "--seed", "20260807", "--accesses", "256",
                "--working-set-mib", "256", "--memory-budget-mib", "512", "--cache-state", "cold",
                "--validation-mode", mode, "--output", str(output),
            ]
            result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
            if result.returncode:
                raise RuntimeError(result.stdout + result.stderr)
            payload = json.loads(output.read_text())
            runs.append({"mode": mode, "repeat": repeat + 1, "file": output.name, "metrics": payload["metrics"]})
    (args.output_directory / "summary.json").write_text(json.dumps({"schema_version": 1, "runs": runs}, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"runs": len(runs)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

