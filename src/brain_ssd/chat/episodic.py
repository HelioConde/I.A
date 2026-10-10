"""Consent-based, brain-*inspired* episodic notes, not simulated human neurons.

Separate SQLite store from both the chat transcript and SSD semantic corpus.
Opt-in only. This does not update Qwen weights or make neuroscience claims.
"""
from __future__ import annotations

from contextlib import contextmanager
import math
import os
from pathlib import Path
import re
import sqlite3
import time
import unicodedata
import uuid
from typing import Any, Iterator

MAX_NOTE_CHARS = 500
MAX_EPISODES = 1000
STOPWORDS = frozenset(
    "a o as os e de da do das dos em no na nos nas para por com que um uma "
    "meu minha meus minhas eu voce você voce qual quais como onde quando "
    "quem porque foi era sao são ser isso isto la lá aqui mais tem ter "
    "the and is it how what which where why when who your this that"
    .split()
)


def default_episodic_path() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    return (Path(base) if base else Path.home() / ".local" / "share") / "BrainSSD" / "episodic-notes.sqlite3"


def cue_tokens(value: str) -> tuple[str, ...]:
    """Normalized unique cues, preserved in sentence order.

    Prefer recent specific terms over alphabetical prefixes when queries
    exceed the limited 24-token retrieval budget.
    """
    plain = unicodedata.normalize("NFKD", value.casefold())
    plain = "".join(c for c in plain if not unicodedata.combining(c))
    seen: set[str] = set()
    ordered: list[str] = []
    for token in re.findall(r"[a-z0-9]{3,}", plain):
        if token not in STOPWORDS and token not in seen:
            ordered.append(token)
            seen.add(token)
    return tuple(ordered)


def words(value: str) -> frozenset[str]:
    return frozenset(cue_tokens(value))


class EpisodicMemory:
    """Explicit episodic memory with conservative lexical partial-cue retrieval."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS episodes (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    source TEXT NOT NULL CHECK(source='explicit_user'),
                    confirmed INTEGER NOT NULL CHECK(confirmed=1)
                );
                CREATE TABLE IF NOT EXISTS episode_terms (
                    episode_id TEXT NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
                    term TEXT NOT NULL,
                    PRIMARY KEY(episode_id, term)
                );
                CREATE INDEX IF NOT EXISTS episode_terms_lookup ON episode_terms(term);
            """)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=10)
        try:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA busy_timeout=10000")
            try:
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise
        finally:
            db.close()

    @staticmethod
    def _id(raw: Any) -> str:
        if not isinstance(raw, str):
            raise ValueError("ID inválido.")
        try:
            if str(uuid.UUID(raw)) != raw:
                raise ValueError()
        except (ValueError, AttributeError):
            raise ValueError("ID inválido.") from None
        return raw

    def add(self, content: Any) -> dict[str, Any]:
        if not isinstance(content, str):
            raise ValueError("A lembrança deve ser texto.")
        content = " ".join(content.split())
        if not content or len(content) > MAX_NOTE_CHARS:
            raise ValueError("Escreva uma nota de 1 a 500 caracteres.")
        terms = sorted(words(content))
        if not terms:
            raise ValueError("Inclua palavras identificáveis na memória.")
        item = {"id": str(uuid.uuid4()), "content": content, "created_at": int(time.time()),
                "source": "explicit_user", "confirmed": True}
        with self._connect() as db:
            n = db.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
            if n >= MAX_EPISODES:
                raise ValueError("Limite de 1.000 memórias atingido. Exclua notas antigas antes de salvar outras.")
            db.execute("INSERT INTO episodes VALUES(?,?,?,?,1)",
                       (item["id"], content, item["created_at"], item["source"]))
            db.executemany("INSERT INTO episode_terms VALUES(?,?)", ((item["id"], term) for term in terms))
        return item

    def list(self, limit: int = 80) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("SELECT id,content,created_at,source,confirmed FROM episodes "
                              "ORDER BY created_at DESC,id DESC LIMIT ?",
                              (max(1,min(int(limit),100)),)).fetchall()
        # SQLite stores CHECK(confirmed=1) as integer 1; external cognitive
        # modules require an actual bool ("is True"), not truthy 1.
        return [{**dict(row), "confirmed": bool(row["confirmed"])} for row in rows]

    def delete(self, item_id: Any) -> bool:
        identifier = self._id(item_id)
        with self._connect() as db:
            result = db.execute("DELETE FROM episodes WHERE id=?", (identifier,))
            return result.rowcount == 1

    def recall(self, cue: str, limit: int = 3) -> list[dict[str, Any]]:
        """Rare-term overlap with a minimum of 2 cues for multiword queries.

        Does not infer new facts or perform neural pattern completion; unrelated
        cues abstain. Always bounded to avoid reading a whole corpus into RAM.
        """
        terms = list(cue_tokens(cue)[-24:])
        if not terms:
            return []
        threshold = 2 if len(terms) > 1 else 1
        placeholders = ",".join("?" for _ in terms)
        with self._connect() as db:
            total = db.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
            rows = db.execute(
                "SELECT e.id,e.content,e.created_at,COUNT(*) AS matches "
                "FROM episode_terms t JOIN episodes e ON t.episode_id=e.id "
                f"WHERE t.term IN ({placeholders}) AND e.confirmed=1 "
                "GROUP BY e.id HAVING COUNT(*)>=? "
                "ORDER BY matches DESC,e.created_at DESC,e.id DESC LIMIT 30",
                (*terms,threshold),
            ).fetchall()
            if not rows:
                return []
            counts = db.execute(
                f"SELECT term,COUNT(*) AS n FROM episode_terms WHERE term IN ({placeholders}) GROUP BY term",
                terms,
            ).fetchall()
        df = {row["term"]: row["n"] for row in counts}
        scored = []
        query = set(terms)
        for row in rows:
            episode_terms = query & words(row["content"])
            if len(episode_terms) < threshold:
                continue
            idf = sum(math.log1p((total + 1) / (df.get(t, 0) + 1)) for t in episode_terms)
            score = round(idf + len(episode_terms) / len(query), 5)
            scored.append({
                "id": row["id"], "content": row["content"], "created_at": row["created_at"],
                "source": "explicit_user", "confirmed": True, "matched_terms": sorted(episode_terms),
                "score": score,
            })
        scored.sort(key=lambda x: (-x["score"], -x["created_at"], x["id"]))
        return scored[:max(1,min(int(limit),3))]

    def replay_candidates(self, limit: int = 10) -> list[dict[str, Any]]:
        """Read-only offline replay *plan*, NOT biological sleep/consolidation."""
        return self.list(limit=min(limit,10))
