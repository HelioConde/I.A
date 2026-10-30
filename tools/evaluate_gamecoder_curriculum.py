"""Execute trusted benchmark harness against an explicitly supplied candidate JS module.

Candidate code is untrusted: never execute it on the host or GitHub runner.
This tool checks metadata and creates a Node test script for isolated execution
by a separate sandbox provider, and refuses direct candidate execution.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TASKS=ROOT/"benchmarks/gamecoder_curriculum/tasks.json"

def validate_tasks():
    data=json.loads(TASKS.read_text(encoding="utf-8"))
    if data.get("schema_version")!=1:raise ValueError("Unsupported curriculum schema")
    ids=set()
    for task in data["tasks"]:
        if task["id"] in ids:raise ValueError("Duplicate task id")
        ids.add(task["id"])
        if task["language"]!="javascript" or not task["required_exports"]:
            raise ValueError("Invalid benchmark task")
        if task.get("cases") and not all("state" in c or "previous" in c for c in task["cases"]):
            raise ValueError("Invalid input cases")
    return data

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--list",action="store_true")
    args=parser.parse_args()
    data=validate_tasks()
    for task in data["tasks"]:
        print(f'{task["id"]}: {task["skill"]} ({task["language"]})')
    return 0

if __name__=="__main__":
    raise SystemExit(main())
