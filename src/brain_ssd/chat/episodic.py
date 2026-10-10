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
                CREATE TABLE IF NOT EXISTS episode_revisions (
                    id TEXT PRIMARY KEY,
                    episode_id TEXT NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
                    old_content TEXT NOT NULL,
                    new_content TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    operation TEXT NOT NULL CHECK(operation IN ('EDIT','RESTORE'))
                );
                CREATE INDEX IF NOT EXISTS revisions_by_episode
                    ON episode_revisions(episode_id,created_at DESC,id DESC);
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
        content, terms = self._validated_note(content)
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

    @staticmethod
    def _validated_note(content: Any) -> tuple[str, list[str]]:
        if not isinstance(content, str):
            raise ValueError("A lembrança deve ser texto.")
        normalized = " ".join(content.split())
        if not normalized or len(normalized) > MAX_NOTE_CHARS:
            raise ValueError("Escreva uma nota de 1 a 500 caracteres.")
        indexed = sorted(words(normalized))
        if not indexed:
            raise ValueError("Inclua palavras identificáveis na memória.")
        return normalized, indexed

    def _replace_locked(self, db: sqlite3.Connection, identity: str,
                        content: Any, expected: Any, operation: str) -> dict[str, Any]:
        """Atomically revise note and its search index with optimistic locking."""
        if not isinstance(expected, str):
            raise ValueError("Informe o texto atual para proteger contra edição concorrente.")
        normalized, terms = self._validated_note(content)
        row = db.execute(
            "SELECT id,content,created_at FROM episodes WHERE id=? AND confirmed=1",
            (identity,)
        ).fetchone()
        if row is None:
            raise ValueError("Memória não encontrada.")
        if row["content"] != expected:
            raise ValueError("Memória alterada em outra janela. Atualize antes de editar.")
        if row["content"] == normalized:
            return {"id":identity,"content":normalized,
                    "created_at":row["created_at"],
                    "source":"explicit_user","confirmed":True,"changed":False}
        revision_id = str(uuid.uuid4())
        db.execute("UPDATE episodes SET content=? WHERE id=?", (normalized, identity))
        db.execute("DELETE FROM episode_terms WHERE episode_id=?", (identity,))
        db.executemany(
            "INSERT INTO episode_terms(episode_id,term) VALUES (?,?)",
            ((identity, term) for term in terms)
        )
        db.execute(
            "INSERT INTO episode_revisions VALUES (?,?,?,?,?,?)",
            (revision_id, identity, row["content"], normalized, int(time.time()), operation)
        )
        # Retain at most 20 prior versions per episode. Never silently grow
        # indefinitely on a constrained local SSD.
        db.execute(
            "DELETE FROM episode_revisions WHERE episode_id=? "
            "AND id NOT IN (SELECT id FROM episode_revisions "
            "WHERE episode_id=? ORDER BY rowid DESC LIMIT 20)",
            (identity, identity)
        )
        return {"id":identity, "content":normalized,
                "created_at":row["created_at"],"source":"explicit_user",
                "confirmed":True,"changed":True,"revision_id":revision_id}

    def replace(self, item_id: Any, new_content: Any, *,
                expected_content: Any) -> dict[str, Any]:
        """Explicit user correction. Does not infer facts or update Qwen."""
        identity = self._id(item_id)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            return self._replace_locked(db, identity, new_content,
                                        expected_content, "EDIT")

    def revisions(self, item_id: Any, limit: int = 20) -> list[dict[str, Any]]:
        """Read past versions locally. Deleting an episode cascades to history."""
        identity = self._id(item_id)
        with self._connect() as db:
            rows = db.execute(
                "SELECT id,episode_id,old_content,new_content,created_at,operation "
                "FROM episode_revisions WHERE episode_id=? "
                "ORDER BY rowid DESC LIMIT ?",
                (identity,max(1,min(int(limit),20)))
            ).fetchall()
        return [dict(row) for row in rows]

    def restore(self, item_id: Any, revision_id: Any, *,
                expected_content: Any) -> dict[str, Any]:
        """Explicit restoration from one selected historical version."""
        identity, target = self._id(item_id), self._id(revision_id)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT old_content FROM episode_revisions "
                "WHERE episode_id=? AND id=?", (identity,target)
            ).fetchone()
            if row is None:
                raise ValueError("Revisão não encontrada.")
            return self._replace_locked(db, identity, row["old_content"],
                                        expected_content, "RESTORE")

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

    def recall(self, cue: str, limit: int = 3, *,
               experimental_aliases: bool = False) -> list[dict[str, Any]]:
        """Return selective episodic notes, never model-generated facts.

        Default behavior remains pure lexical retrieval. The separately gated
        synonym bridge uses a handful of exact PT-BR aliases; it is NOT
        embedding-based semantic retrieval. Every alias hit needs >=2 distinct
        query concepts, protecting against single-word semantic collisions.
        No full corpus scan is needed, and the number of candidate rows is
        strictly bounded.
        """
        raw_terms = list(cue_tokens(cue)[-24:])
        if not raw_terms:
            return []
        if experimental_aliases:
            # Deferred import leaves the default path and dependencies intact.
            from brain_ssd.chat.semantic_bridge import (
                concepts, expand_query
            )
            query_concepts = concepts(raw_terms)
            terms = list(expand_query(raw_terms))
        else:
            query_concepts = frozenset(raw_terms)
            terms = raw_terms
        threshold = 2 if len(query_concepts) > 1 else 1
        placeholders = ",".join("?" for _ in terms)
        with self._connect() as db:
            total = db.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
            rows = db.execute(
                "SELECT e.id,e.content,e.created_at,COUNT(*) AS matches "
                "FROM episode_terms t JOIN episodes e ON t.episode_id=e.id "
                f"WHERE t.term IN ({placeholders}) AND e.confirmed=1 "
                "GROUP BY e.id HAVING COUNT(*)>=? "
                "ORDER BY matches DESC,e.created_at DESC,e.id DESC LIMIT 120",
                (*terms,threshold),
            ).fetchall()
            if not rows:
                return []
            counts = db.execute(
                f"SELECT term,COUNT(*) AS n FROM episode_terms WHERE term IN ({placeholders}) GROUP BY term",
                terms,
            ).fetchall()
        df = {row["term"]: row["n"] for row in counts}
        scored: list[dict[str, Any]] = []
        query = set(raw_terms)
        from brain_ssd.chat.memory_safety import disagrees_with_explicit_cue
        for row in rows:
            # "terça" must not recover an episode explicitly corrected to
            # "quinta" solely due to generic topic overlap. Multi-valued
            # or unspecified dates/times remain eligible and are not judged.
            if disagrees_with_explicit_cue(cue, row["content"]):
                continue
            memory_terms = words(row["content"])
            exact = query & memory_terms
            matching = concepts(memory_terms) & query_concepts if experimental_aliases else exact
            if len(matching) < threshold:
                continue
            # Semantic-only one-word bridges are too permissive; allow a
            # single cue only when its literal token is also present.
            if experimental_aliases and not exact and len(matching) < 2:
                continue
            idf = sum(math.log1p((total + 1) / (df.get(t, 0) + 1)) for t in exact)
            # Exact-only score remains compatible with the previous strategy.
            score = round(idf + len(matching) / len(query_concepts), 5)
            hit = {
                "id": row["id"], "content": row["content"],
                "created_at": row["created_at"],
                "source": "explicit_user", "confirmed": True,
                "matched_terms": sorted(exact),
                "score": score,
            }
            if experimental_aliases:
                hit["matched_concepts"] = sorted(matching)
                hit["match_mode"] = "LEXICAL" if len(exact) >= threshold else "SEMANTIC_ALIAS"
            scored.append(hit)
        if experimental_aliases:
            scored.sort(key=lambda x: (
                -len(x["matched_concepts"]),
                -len(x["matched_terms"]),
                -x["score"], -x["created_at"], x["id"]
            ))
        else:
            scored.sort(key=lambda x: (-x["score"], -x["created_at"], x["id"]))
        return scored[:max(1,min(int(limit),3))]

    def get_assistant_name(self) -> str | None:
        """Return only the most recently *explicitly* saved assistant nickname."""
        prefix = "Nome escolhido para o Brain-SSD: "
        with self._connect() as db:
            row = db.execute(
                "SELECT content FROM episodes WHERE confirmed=1 "
                "AND substr(content, 1, ?) = ? ORDER BY rowid DESC LIMIT 1",
                (len(prefix), prefix),
            ).fetchone()
        return row["content"][len(prefix):] if row is not None else None

    def remember_assistant_name(self, name: str) -> dict[str, Any]:
        """Persist an explicit chat command, never auto-infer a nickname.

        Updates an existing nickname in place with revision history rather than
        accumulating contradictory identity memories.
        """
        if not isinstance(name, str):
            raise ValueError("Nome inválido.")
        name = " ".join(name.strip().split())
        if not re.fullmatch(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ -]{0,39}", name):
            raise ValueError("Use um nome de 1 a 40 caracteres, apenas letras, espaços e hífen.")
        name = name[0].upper() + name[1:]
        prefix = "Nome escolhido para o Brain-SSD: "
        content, terms = self._validated_note(prefix + name)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute(
                "SELECT id, content, created_at FROM episodes WHERE confirmed=1 "
                "AND substr(content, 1, ?) = ? ORDER BY rowid DESC LIMIT 1",
                (len(prefix), prefix),
            ).fetchone()
            if previous is not None:
                return self._replace_locked(
                    db, previous["id"], content, previous["content"], "EDIT"
                )
            count = db.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
            if count >= MAX_EPISODES:
                raise ValueError("Limite de memórias atingido; exclua uma nota antes.")
            item = {
                "id": str(uuid.uuid4()), "content": content,
                "created_at": int(time.time()), "source": "explicit_user",
                "confirmed": True,
            }
            db.execute(
                "INSERT INTO episodes VALUES(?,?,?,?,1)",
                (item["id"], content, item["created_at"], item["source"]),
            )
            db.executemany(
                "INSERT INTO episode_terms VALUES(?,?)",
                ((item["id"], term) for term in terms),
            )
            return item

    def replay_candidates(self, limit: int = 10) -> list[dict[str, Any]]:
        """Read-only offline replay *plan*, NOT biological sleep/consolidation."""
        return self.list(limit=min(limit,10))
