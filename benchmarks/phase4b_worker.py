#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from brain_ssd.physical_replay import run_physical_replay


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--workload", required=True)
    parser.add_argument("--universe-pages", type=int, required=True)
    parser.add_argument("--policy", required=True)
    parser.add_argument("--budget-mib", type=int, required=True)
    parser.add_argument("--controller", required=True)
    parser.add_argument("--performance", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run_physical_replay(args.manifest, args.trace, args.workload, args.universe_pages,
                                         args.policy, args.budget_mib, args.controller, not args.performance), sort_keys=True))


if __name__ == "__main__": main()
