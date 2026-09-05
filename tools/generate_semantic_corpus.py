#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brain_ssd.semantic import generate_query_dataset, generate_semantic_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate deterministic Phase 3 semantic metadata and queries")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--pages", type=int, default=1024)
    parser.add_argument("--seed", type=int, default=20260807)
    args = parser.parse_args()
    manifest = generate_semantic_manifest(args.manifest, args.pages, args.seed)
    generate_query_dataset(args.queries, manifest, args.seed)
    print(f"pages={args.pages} manifest={args.manifest} queries={args.queries}")


if __name__ == "__main__":
    main()
