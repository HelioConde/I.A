#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks"))

from storage_matrix import run_case


def main() -> int:
    parser = argparse.ArgumentParser(description="Full SHA-256 integrity sweep for every logical page")
    parser.add_argument("--corpus-directory", required=True, type=Path)
    parser.add_argument("--output-directory", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=20260807)
    args = parser.parse_args()
    args.output_directory.mkdir(parents=True, exist_ok=True)
    runs = []
    for page_kib in (256, 512, 1024, 2048, 4096, 8192):
        page_bytes = page_kib * 1024
        manifest = args.corpus_directory / f"manifest-{page_bytes}.json"
        data = json.loads(manifest.read_text())
        output = args.output_directory / f"integrity-{page_kib}kib.json"
        payload = run_case(
            manifest, "sequential", "cold", args.seed, data["page_count"],
            data["corpus_size_bytes"] // 1024**2, 512, output, "integrity",
        )
        runs.append({"page_kib": page_kib, "file": output.name, "metrics": payload["metrics"]})
    summary = {
        "schema_version": 1, "experiment": "phase2_5-full-integrity",
        "all_pages_verified": all(run["metrics"]["verified_pages"] == 1024**2 // run["page_kib"] for run in runs),
        "checksum_errors": sum(run["metrics"]["checksum_errors"] for run in runs),
        "runs": runs,
    }
    (args.output_directory / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"runs": len(runs), "all_pages_verified": summary["all_pages_verified"], "checksum_errors": summary["checksum_errors"]}))
    return 0 if summary["all_pages_verified"] and summary["checksum_errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

