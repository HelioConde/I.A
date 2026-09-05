#!/usr/bin/env python3
"""Reproducible Phase 4E-W Windows Native Validation runner."""
from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brain_ssd.local_runtime.phase4ew import Phase4EWRunner


def main() -> int:
    parser = argparse.ArgumentParser(description="Brain-SSD Phase 4E-W Windows Native Validation")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--audit", action="store_true")
    modes.add_argument("--core-isolation", action="store_true")
    modes.add_argument("--single-shot", action="store_true")
    modes.add_argument("--session", action="store_true")
    modes.add_argument("--repeated-query", action="store_true")
    modes.add_argument("--sustained", action="store_true")
    modes.add_argument("--hud-overhead", action="store_true")
    modes.add_argument("--all", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Print the selected matrix without executing it")
    parser.add_argument("--quick", action="store_true", help="Development matrix; always canonical=false")
    parser.add_argument("--duration-minutes", type=float, help="Sustained duration; full canonical recommendation is 20")
    args = parser.parse_args()

    if platform.system() != "Windows":
        print(json.dumps({"status": "REFUSED", "reason": "Phase 4E-W requires native Windows", "system": platform.system()}))
        return 2
    if args.duration_minutes is not None and args.duration_minutes <= 0:
        parser.error("--duration-minutes must be positive")

    runner = Phase4EWRunner(ROOT, quick=args.quick, duration_minutes=args.duration_minutes)
    if args.dry_run:
        print(json.dumps(runner.matrix_plan(), ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    selected = next((name for name in (
        "audit", "core_isolation", "single_shot", "session", "repeated_query", "sustained", "hud_overhead", "all"
    ) if getattr(args, name)), None)
    if selected is None:
        parser.error("select one mode or use --dry-run")
    result = runner.run_all() if selected == "all" else getattr(runner, selected)()
    print(json.dumps({
        "validation_track": result.get("validation_track"),
        "run_id": result.get("run_id"),
        "status": result.get("status"),
        "phase4ew_canonical": result.get("phase4ew_canonical", False),
        "phase4e_valid": result.get("phase4e_valid"),
        "target_8gb": result.get("target_8gb"),
    }, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("status") in {"PASS", "PASS_WITH_WARNINGS"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
