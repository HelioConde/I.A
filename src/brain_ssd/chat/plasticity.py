"""Explicit, reversible preference/association feedback in a sidecar SQLite ledger.

This is NOT training of language-model weights. The ledger only computes a
bounded ranking bias for offline/shadow experiments; never changes facts,
evidence, SSD pages or model behavior automatically.
"""
from __future__ import annotations

from contextlib import contextmanager
import math
from pathlib import Path
import sqlite3
import time
import uuid
from typing import Any, Iterator

from brain_ssd.chat.episodic import EpisodicMemory

MIN_EVIDENCE = 3
MAX_EVENTS = 5000
MAX_SCORE_ADJUSTMENT = 0.15


class PlasticityLedger:
    def __init__(self, path: Path, episodes: EpisodicMemory) -> None:
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.episodes = episodes
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS feedback (
                    id TEXT PRIMARY KEY,
                    episode_id TEXT NOT NULL,
                    signal INTEGER NOT NULL CHECK(signal IN (-1, 1)),
                    created_at INTEGER NOT NULL,
                    revoked_at INTEGER
                );
                CREATE INDEX IF NOT EXISTS feedback_episode
                    ON feedback(episode_id, revoked_at);
            """)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=10)
        try:
            conn.row_factory = sqlite3.Row
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
        if not isinstance(value, str):
            raise ValueError("ID inválido.")
        try:
            if str(uuid.UUID(value)) != value:
                raise ValueError()
        except (ValueError, TypeError, AttributeError):
            raise ValueError("ID inválido.") from None
        return value

    def add_feedback(self, episode_id: str, signal: int) -> str:
        ident = self._check_uuid(episode_id)
        if type(signal) is not int or signal not in (-1, 1):
            raise ValueError("O feedback precisa ser +1 ou -1, explicitamente.")
        # No feedback for unapproved/generated text or notes no longer present.
        if not any(note["id"] == ident for note in self.episodes.list(limit=100)):
            # More than 100 episodes: membership check without loading notes.
            with self.episodes._connect() as db:
                row = db.execute("SELECT id FROM episodes WHERE id=? AND confirmed=1", (ident,)).fetchone()
            if row is None:
                raise ValueError("Memória confirmada não encontrada.")
        event_id = str(uuid.uuid4())
        with self._connect() as db:
            count = db.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
            if count >= MAX_EVENTS:
                raise ValueError("Limite de feedback atingido.")
            db.execute("INSERT INTO feedback VALUES (?,?,?,?,NULL)",
                       (event_id, ident, signal, int(time.time())))
        return event_id

    def revoke(self, event_id: str) -> bool:
        ident = self._check_uuid(event_id)
        with self._connect() as db:
            changed = db.execute(
                "UPDATE feedback SET revoked_at=? WHERE id=? AND revoked_at IS NULL",
                (int(time.time()), ident),
            )
            return changed.rowcount == 1

    def shadow_bias(self, episode_id: str, now: int | None = None,
                    half_life_days: float = 30) -> dict[str, Any]:
        """Adaptation only after >=3 active explicit signals, bounded + decayed.

        One user's repeated clicks are not independent evidence of truth;
        therefore this bias MUST NOT be used as factual trust or promotion.
        """
        ident = self._check_uuid(episode_id)
        if not 1 <= half_life_days <= 365:
            raise ValueError("Invalid half life")
        now = int(time.time()) if now is None else int(now)
        with self._connect() as db:
            rows = db.execute(
                "SELECT signal,created_at FROM feedback "
                "WHERE episode_id=? AND revoked_at IS NULL ORDER BY created_at DESC LIMIT 100",
                (ident,),
            ).fetchall()
        n = len(rows)
        weight = [math.exp(-math.log(2) * max(0, now-row["created_at"]) /
                           (half_life_days * 86400)) for row in rows]
        signed = sum(row["signal"] * w for row, w in zip(rows, weight))
        total = sum(weight)
        score = max(-MAX_SCORE_ADJUSTMENT,
                    min(MAX_SCORE_ADJUSTMENT,
                        MAX_SCORE_ADJUSTMENT * signed / max(total, 1))) if n >= MIN_EVIDENCE else 0.0
        return {"episode_id": ident, "active_support": n,
                "bias": round(score, 6), "status": "SHADOW_ONLY",
                "reversible": True, "half_life_days": half_life_days}

    def list_feedback(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("SELECT id,episode_id,signal,created_at,revoked_at "
                              "FROM feedback ORDER BY created_at DESC,id DESC LIMIT ?",
                              (max(1,min(int(limit),100)),)).fetchall()
        return [dict(x) for x in rows]
