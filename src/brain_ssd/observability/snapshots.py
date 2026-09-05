from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any


def privacy_snapshot(
    state: dict[str, Any], *, hide_query: bool = False, hide_records: bool = False, hide_answer: bool = False
) -> dict[str, Any]:
    snapshot = copy.deepcopy(state)
    snapshot["privacy"] = {"query_hidden": hide_query, "records_hidden": hide_records, "answer_hidden": hide_answer}
    if hide_query:
        snapshot["query"] = "[QUERY HIDDEN]"
    if hide_records:
        for record in snapshot.get("knowledge", {}).get("records", []):
            record["excerpt"] = "[RECORD TEXT HIDDEN]"
    if hide_answer:
        snapshot["answer"] = "[ANSWER HIDDEN]"
    return snapshot


def write_snapshot(path: Path, state: dict[str, Any], **privacy: bool) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(privacy_snapshot(state, **privacy), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    return path


def read_snapshot(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("HUD snapshot must be a JSON object")
    return payload
