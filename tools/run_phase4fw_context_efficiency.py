#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brain_ssd.local_runtime.phase4fw import Phase4FWRunner


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase 4F-W Context Efficiency on the frozen Windows runtime")
    modes = parser.add_mutually_exclusive_group(required=True)
    for name in ("audit", "baseline", "oracle", "distillation", "budgets", "pruning", "ablation", "quality", "all"):
        modes.add_argument(f"--{name}", action="store_true")
    modes.add_argument("--dry-run", action="store_true")
    parser.add_argument("--quick", action="store_true", help="Small non-canonical integration matrix")
    parser.add_argument("--resume-matrix", help="Resume a matrix using its immutable per-run checkpoints")
    args = parser.parse_args()
    runner = Phase4FWRunner(ROOT, quick=args.quick, resume_matrix=args.resume_matrix)
    if args.dry_run:
        result = runner.dry_run()
    elif args.audit:
        result = runner.audit()
    else:
        stage = next(name for name in ("baseline", "oracle", "distillation", "budgets", "pruning", "ablation", "quality", "all") if getattr(args, name))
        result = runner.run_stage(stage)
    print(json.dumps({"status": result.get("status"), "matrix_id": result.get("matrix_id"), "run_id": result.get("run_id"), "best_variant": result.get("best_variant"), "recommendation": result.get("recommendation")}, ensure_ascii=False, indent=2))
    return 0 if str(result.get("status", "")).startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
