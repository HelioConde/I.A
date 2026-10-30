"""Offline, deterministic Luna GameDev catalog retrieval.

This module retrieves metadata and skill contracts, NOT third-party repository
contents. Never returns held-out sources and never downloads or executes code.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

DEFAULT_BASE = Path(__file__).resolve().parents[2] / "knowledge" / "game_dev"
TOKENS = re.compile(r"[a-zA-ZÀ-ÿ][a-zA-ZÀ-ÿ0-9_-]*")


def _words(value: str) -> set[str]:
    return {match.group().casefold() for match in TOKENS.finditer(value) if len(match.group()) > 2}


def load_catalog(base: Path = DEFAULT_BASE) -> tuple[list[dict], list[dict]]:
    sources = json.loads((base / "sources.json").read_text(encoding="utf-8"))["sources"]
    skills = json.loads((base / "skills.json").read_text(encoding="utf-8"))["skills"]
    if any(s.get("split") not in {"reference", "candidate_train", "eval_holdout"} for s in sources):
        raise ValueError("Invalid source split")
    ids = [s["id"] for s in sources] + [s["id"] for s in skills]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate identifiers")
    return sources, skills


def search(query: str, *, base: Path = DEFAULT_BASE, limit: int = 5) -> list[dict]:
    """Search safe *catalog metadata* only; no filesystem walking or network calls."""
    if not isinstance(query, str) or not query.strip():
        return []
    if not 1 <= limit <= 30:
        raise ValueError("limit must be between 1 and 30")
    sources, skills = load_catalog(base)
    tokens = _words(query)
    if not tokens:
        return []
    candidates: list[dict] = []
    for source in sources:
        if source["split"] == "eval_holdout":
            continue
        text = " ".join(str(source.get(key, "")) for key in ("id", "repository", "role", "license"))
        overlap = tokens & _words(text)
        if overlap:
            candidates.append({"kind": "source", "id": source["id"],
                               "repository": source["repository"], "split": source["split"],
                               "role": source["role"], "score": len(overlap)})
    for skill in skills:
        text = " ".join([skill["id"], skill["input"], skill["output"], *skill["checks"]])
        overlap = tokens & _words(text)
        if overlap:
            candidates.append({"kind": "skill", "id": skill["id"],
                               "input": skill["input"], "output": skill["output"],
                               "checks": skill["checks"], "score": len(overlap)})
    return sorted(candidates, key=lambda x: (-x["score"], x["kind"], x["id"]))[:limit]


def format_for_core(query: str, *, base: Path = DEFAULT_BASE, limit: int = 5) -> dict:
    """Machine-readable grounding for Luna Core, not executable game code."""
    return {"schema_version": 1, "query": query,
            "notice": "Catalog metadata only; no third-party source code ingested or model trained.",
            "results": search(query, base=base, limit=limit)}
