#!/usr/bin/env python3
"""Query the local Luna GameDev metadata catalog.

Example: python tools/query_game_knowledge.py "gdscript platformer"
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from brain_ssd.game_knowledge import format_for_core


def main() -> int:
    parser = argparse.ArgumentParser(description="Search safe Luna GameDev catalog metadata")
    parser.add_argument("query", help="Search terms for knowledge sources or skill contracts")
    parser.add_argument("--limit", type=int, default=5)
    arguments = parser.parse_args()
    print(json.dumps(format_for_core(arguments.query, limit=arguments.limit),
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
