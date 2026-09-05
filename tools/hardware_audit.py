#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from brain_ssd.hardware import collect_hardware


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture a reproducible Brain-SSD hardware audit")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = json.dumps(collect_hardware(), indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload)
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

