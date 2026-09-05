#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brain_ssd.local_runtime.windows_core_experiment_1b import WindowsCoreRuntimeExperiment1B


def main() -> int:
    parser = argparse.ArgumentParser(description="Run WCRE-1B causality and context-cost measurements")
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--audit", action="store_true")
    modes.add_argument("--causality", action="store_true")
    modes.add_argument("--context-cost", action="store_true")
    modes.add_argument("--brain-context-reference", action="store_true")
    modes.add_argument("--sustained", action="store_true")
    modes.add_argument("--all", action="store_true")
    parser.add_argument("--quick", action="store_true", help="Development run; never canonical")
    parser.add_argument("--duration-minutes", type=float, help="Persistent sanity duration; canonical default is 5")
    args = parser.parse_args()
    if args.duration_minutes is not None and args.duration_minutes <= 0:
        parser.error("--duration-minutes must be positive")
    runner = WindowsCoreRuntimeExperiment1B(ROOT, quick=args.quick, duration_minutes=args.duration_minutes)
    if args.all:
        result = runner.run_all()
    elif args.audit:
        result = runner.audit()
    elif args.causality:
        result = runner.causality()
    elif args.context_cost:
        result = runner.context_cost()
    elif args.brain_context_reference:
        result = runner.brain_context_reference()
    else:
        result = runner.sustained()
    print(json.dumps({"status": result.get("status"), "run_id": result.get("run_id"), "hypothesis": result.get("hypothesis"), "hypothesis_status": result.get("hypothesis_status"), "eng_core_002": result.get("eng_core_002"), "eng_core_003": result.get("eng_core_003")}, ensure_ascii=False, indent=2))
    return 0 if str(result.get("status", "")).startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
