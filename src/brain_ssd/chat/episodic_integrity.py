"""Read-only privacy-safe integrity audit of explicitly saved episodes.

No schema migrations, repairs, autonomous learning or network access.
Reports aggregate counters ONLY, never memory text, IDs, paths or tokens.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import sqlite3
from typing import Any

from brain_ssd.chat.episodic import MAX_EPISODES, MAX_NOTE_CHARS, words


def audit_episodic_database(db_path: Path) -> dict[str, Any]:
    path = Path(db_path).expanduser()
    result: dict[str, Any] = {
        "status":"MISSING", "schema":"episodic-review-v1",
        "episode_count":0, "revision_count":0,
        "index_terms_count":0, "missing_index_terms":0,
        "stale_index_terms":0, "orphan_revisions":0,
        "too_many_revisions":0, "invalid_notes":0,
        "sqlite_ok":False, "read_only":True,
        "discloses_note_content":False,
    }
    if not path.is_file():
        return result
    # Query-only connection prevents changing even the journal mode. Do not
    # open a regular connection that would recreate a missing SQLite file.
    try:
        database = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=10)
        try:
            database.row_factory = sqlite3.Row
            database.execute("PRAGMA query_only=ON")
            quick = database.execute("PRAGMA quick_check(1)").fetchone()
            result["sqlite_ok"] = quick is not None and quick[0] == "ok"
            tables = {x[0] for x in database.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
            if not {"episodes","episode_terms","episode_revisions"} <= tables:
                result["status"] = "INVALID_SCHEMA"
                return result
            notes = database.execute(
                "SELECT id,content,source,confirmed FROM episodes LIMIT ?",
                (MAX_EPISODES+100,)
            ).fetchall()
            result["episode_count"] = len(notes)
            # Never include sensitive content, tokens, UUIDs or local paths in
            # the returned report, even when errors are encountered.
            desired: dict[str,set[str]] = {}
            for row in notes:
                content = row["content"]
                valid = (isinstance(content,str) and 1 <= len(content) <= MAX_NOTE_CHARS
                         and row["source"] == "explicit_user" and row["confirmed"] == 1)
                if not valid:
                    result["invalid_notes"] += 1
                desired[row["id"]] = set(words(content)) if isinstance(content,str) else set()
            actual: dict[str,set[str]] = defaultdict(set)
            for row in database.execute("SELECT episode_id,term FROM episode_terms"):
                actual[row["episode_id"]].add(row["term"])
                result["index_terms_count"] += 1
            for ident, required in desired.items():
                seen = actual.pop(ident,set())
                result["missing_index_terms"] += len(required - seen)
                result["stale_index_terms"] += len(seen - required)
            result["stale_index_terms"] += sum(len(x) for x in actual.values())
            counts: Counter[str] = Counter()
            for row in database.execute("SELECT episode_id FROM episode_revisions"):
                result["revision_count"] += 1
                ident=row["episode_id"]
                if ident not in desired:
                    result["orphan_revisions"] += 1
                counts[ident] += 1
            result["too_many_revisions"] = sum(max(0,count-20) for count in counts.values())
            result["status"] = "OK" if (
                result["sqlite_ok"] and result["episode_count"] <= MAX_EPISODES
                and not any(result[key] for key in (
                    "missing_index_terms","stale_index_terms","orphan_revisions",
                    "too_many_revisions","invalid_notes"
                ))
            ) else "ISSUES_FOUND"
        finally:
            database.close()
    except (sqlite3.Error,OSError,ValueError):
        result["status"] = "UNREADABLE"
    return result
