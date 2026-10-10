"""Offline consolidation review *queue*: not biological sleep or LLM training.

A draft is a link between existing confirmed episodes, not automatically
generated semantic knowledge. Only the human can approve an extractive summary.
Approved notes remain in this sidecar queue, NEVER in Qwen/core retrieval.
"""
from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import time
import uuid
from typing import Any, Iterator

from brain_ssd.chat.episodic import EpisodicMemory, words


class ConsolidationQueue:
    def __init__(self, filename: Path, episodes: EpisodicMemory) -> None:
        self.path=Path(filename).expanduser().resolve()
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.episodes=episodes
        with self._db() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS review_candidates (
                    id TEXT PRIMARY KEY,
                    source_ids TEXT NOT NULL,
                    shared_cues TEXT NOT NULL,
                    summary TEXT,
                    state TEXT NOT NULL CHECK(state IN ('DRAFT','REVIEWED','REVOKED','REJECTED')),
                    created_at INTEGER NOT NULL,
                    reviewed_at INTEGER
                );
                CREATE INDEX IF NOT EXISTS review_state
                  ON review_candidates(state, created_at DESC);
            """)

    @contextmanager
    def _db(self) -> Iterator[sqlite3.Connection]:
        conn=sqlite3.connect(self.path,timeout=10)
        try:
            conn.row_factory=sqlite3.Row
            conn.execute("PRAGMA busy_timeout=10000")
            try:
                yield conn
                conn.commit()
            except BaseException:
                conn.rollback()
                raise
        finally:
            conn.close()

    @staticmethod
    def _check_uuid(value: Any) -> str:
        if not isinstance(value,str):
            raise ValueError("ID inválido.")
        try:
            if str(uuid.UUID(value)) != value:
                raise ValueError()
        except (TypeError,ValueError,AttributeError):
            raise ValueError("ID inválido.") from None
        return value

    def _source_notes(self, ids: list[str]) -> list[dict[str,Any]]:
        if not 2 <= len(ids) <= 6 or len(ids) != len(set(ids)):
            raise ValueError("Selecione entre 2 e 6 memórias distintas.")
        ids=[self._check_uuid(x) for x in ids]
        placeholders=",".join("?" for _ in ids)
        with self.episodes._connect() as conn:
            rows=conn.execute(
                f"SELECT id,content,source,confirmed FROM episodes WHERE id IN ({placeholders})",
                ids,
            ).fetchall()
        mapping={row["id"]:dict(row) for row in rows}
        if len(mapping) != len(ids) or any(
            mapping[x]["source"]!="explicit_user" or mapping[x]["confirmed"]!=1
            for x in ids
        ):
            raise ValueError("Uma fonte deixou de ser uma memória confirmada.")
        return [mapping[x] for x in ids]

    def create_draft(self, source_ids: list[str]) -> dict[str,Any]:
        if not isinstance(source_ids,list):
            raise ValueError("Escolha uma lista de memórias.")
        notes=self._source_notes(source_ids)
        shared=set(words(notes[0]["content"]))
        for row in notes[1:]:
            shared.intersection_update(words(row["content"]))
        if len(shared)<2:
            raise ValueError("Não há pistas em comum suficientes para propor consolidação.")
        item={"id":str(uuid.uuid4()),"source_ids":list(source_ids),
              "shared_cues":sorted(shared)[:20],"state":"DRAFT",
              "summary":None,"created_at":int(time.time())}
        with self._db() as db:
            db.execute(
                "INSERT INTO review_candidates VALUES (?,?,?,?,?,?,?)",
                (item["id"],json.dumps(item["source_ids"]),
                 json.dumps(item["shared_cues"]),None,"DRAFT",item["created_at"],None),
            )
        return item

    def _row(self, id: str) -> dict[str,Any] | None:
        identity=self._check_uuid(id)
        with self._db() as db:
            row=db.execute("SELECT * FROM review_candidates WHERE id=?",(identity,)).fetchone()
        if row is None:
            return None
        data=dict(row)
        data["source_ids"]=json.loads(data["source_ids"])
        data["shared_cues"]=json.loads(data["shared_cues"])
        return data

    def review(self, draft_id: str, decision: str, summary: str | None = None) -> dict[str,Any]:
        draft=self._row(draft_id)
        if draft is None or draft["state"] != "DRAFT":
            raise ValueError("Rascunho não encontrado ou já revisado.")
        if decision not in ("approve","reject"):
            raise ValueError("Use approve ou reject.")
        if decision=="approve":
            if not isinstance(summary,str) or not 1 <= len(summary.strip()) <= 500:
                raise ValueError("A revisão precisa de resumo explícito de 1 a 500 caracteres.")
            self._source_notes(draft["source_ids"])
            state="REVIEWED"
            saved=summary.strip()
        else:
            state="REJECTED"
            saved=None
        with self._db() as db:
            db.execute(
                "UPDATE review_candidates SET state=?,summary=?,reviewed_at=? WHERE id=? AND state='DRAFT'",
                (state,saved,int(time.time()),draft_id),
            )
        return self._row(draft_id)

    def revoke(self, reviewed_id: str) -> bool:
        identity=self._check_uuid(reviewed_id)
        with self._db() as db:
            change=db.execute(
                "UPDATE review_candidates SET state='REVOKED',reviewed_at=? WHERE id=? AND state='REVIEWED'",
                (int(time.time()),identity),
            )
            return change.rowcount==1

    def list(self, limit:int=50) -> list[dict[str,Any]]:
        with self._db() as db:
            rows=db.execute(
                "SELECT id FROM review_candidates ORDER BY created_at DESC,id DESC LIMIT ?",
                (max(1,min(int(limit),100)),),
            ).fetchall()
        return [self._row(x["id"]) for x in rows]

    def delete(self, draft_id: str) -> bool:
        identity=self._check_uuid(draft_id)
        with self._db() as db:
            return db.execute("DELETE FROM review_candidates WHERE id=?",(identity,)).rowcount==1
