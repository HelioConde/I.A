#!/usr/bin/env python3
"""Read-only local SQLite audit; never prints episodic note contents."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from brain_ssd.chat.episodic import default_episodic_path
from brain_ssd.chat.episodic_integrity import audit_episodic_database


def main() -> int:
    parser=argparse.ArgumentParser(description="Auditar integridade da memória episódica sem revelar notas")
    parser.add_argument("--db",type=Path,default=default_episodic_path())
    args=parser.parse_args()
    report=audit_episodic_database(args.db)
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0 if report["status"]=="OK" else 2


if __name__=="__main__":
    raise SystemExit(main())
