#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brain_ssd.corpus import ensure_corpus


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate deterministic synthetic Brain-SSD corpus")
    parser.add_argument("--directory", required=True, type=Path)
    parser.add_argument("--size-gib", required=True, type=int, choices=(1, 4, 8))
    parser.add_argument("--seed", type=int, default=20260807)
    parser.add_argument("--page-size-mib", type=float, action="append", required=True)
    args = parser.parse_args()
    paths = ensure_corpus(
        args.directory, args.size_gib * 1024**3, args.seed,
        [int(size * 1024**2) for size in args.page_size_mib],
    )
    for path in paths:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
