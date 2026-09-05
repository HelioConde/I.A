#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brain_ssd.corpus import create_layout_manifest

COMBINATIONS_KIB = ((256, 4096), (256, 8192), (512, 4096), (512, 8192), (1024, 4096), (1024, 8192), (1024, 16384), (2048, 8192), (2048, 16384))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus-directory", required=True, type=Path)
    args = parser.parse_args()
    for logical_kib, extent_kib in COMBINATIONS_KIB:
        base = args.corpus_directory / f"manifest-{logical_kib * 1024}.json"
        for layout in ("colocated", "random"):
            print(create_layout_manifest(base, extent_kib * 1024, layout))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

