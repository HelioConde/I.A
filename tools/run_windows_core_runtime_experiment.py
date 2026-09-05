#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brain_ssd.local_runtime.windows_core_experiment import WindowsCoreRuntimeExperiment


def main() -> int:
    parser = argparse.ArgumentParser(description="Run WCRE-1 without changing the frozen cognitive pipeline")
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--audit", action="store_true")
    modes.add_argument("--core-only", action="store_true")
    modes.add_argument("--brain-ssd", action="store_true")
    modes.add_argument("--session", action="store_true")
    modes.add_argument("--sustained", action="store_true")
    modes.add_argument("--contamination", action="store_true")
    modes.add_argument("--all", action="store_true")
    parser.add_argument("--quick", action="store_true", help="Development run; never canonical")
    parser.add_argument("--duration-minutes", type=float, help="Sustained duration; canonical --all requires at least 20")
    args = parser.parse_args()
    if args.duration_minutes is not None and args.duration_minutes <= 0:
        parser.error("--duration-minutes must be positive")
    runner = WindowsCoreRuntimeExperiment(ROOT, quick=args.quick, duration_minutes=args.duration_minutes)
    if args.all:
        result = runner.run_all()
    elif args.audit:
        result = runner.audit()
    elif args.core_only:
        result = runner.core_only()
    elif args.brain_ssd:
        result = runner.brain_ssd_ab()
    elif args.session:
        result = runner.session()
    elif args.sustained:
        result = runner.sustained()
    else:
        result = runner.contamination()
    print(json.dumps({
        "status": result.get("status") or result.get("operational_status"),
        "run_id": result.get("run_id"),
        "artifact": result.get("artifact"),
        "hypothesis_status": result.get("hypothesis_status"),
    }, ensure_ascii=False, indent=2))
    return 0 if str(result.get("status") or result.get("operational_status", "")).startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
