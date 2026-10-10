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
        # Forgotten episodic sources must not keep influencing any ranking,
        # even if their old feedback events remain in this separate sidecar.
        with self.episodes._connect() as source_db:
            source_exists = source_db.execute(
                "SELECT 1 FROM episodes WHERE id=? AND confirmed=1", (ident,)
            ).fetchone() is not None
        if not source_exists:
            return {"episode_id": ident, "active_support": 0,
                    "bias": 0.0, "status": "SOURCE_DELETED",
                    "reversible": True, "half_life_days": half_life_days}
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


class PredictionJournal:
    """Versioned, reversible Beta-Bernoulli predictions for verified outcomes.

    Learns a scalar probability for a limited task ID, NOT Qwen facts/weights.
    Unverified guesses have no effect; rollback restores the previous estimate.
    """

    def __init__(self, path: Path) -> None:
        import re
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS prediction_feedback (
                    id TEXT PRIMARY KEY,
                    task_key TEXT NOT NULL,
                    predicted REAL NOT NULL,
                    observed INTEGER NOT NULL CHECK(observed IN (0,1)),
                    timestamp INTEGER NOT NULL,
                    revoked_at INTEGER
                );
                CREATE INDEX IF NOT EXISTS prediction_task_idx
                    ON prediction_feedback(task_key, revoked_at);
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
    def _task_key(key: str) -> str:
        import re
        if not isinstance(key, str) or re.fullmatch(r"[a-z][a-z0-9_.-]{0,63}", key) is None:
            raise ValueError("Use um identificador de tarefa sem dados pessoais.")
        return key

    def predict(self, task_key: str) -> dict[str, Any]:
        key = self._task_key(task_key)
        with self._connect() as db:
            row = db.execute(
                "SELECT SUM(observed) AS successes, COUNT(*) AS n FROM prediction_feedback "
                "WHERE task_key=? AND revoked_at IS NULL",
                (key,),
            ).fetchone()
        count = int(row["n"])
        success = int(row["successes"] or 0)
        # Beta(1,1) conjugate mean; smoothed and bounded away from certainty.
        p = (success + 1) / (count + 2)
        return {"task": key, "probability": round(p, 6), "observations": count,
                "status": "SYNTHETIC_METADATA_ONLY", "model_weights_changed": False}

    def observe(self, task_key: str, verified_outcome: bool) -> dict[str, Any]:
        key = self._task_key(task_key)
        if type(verified_outcome) is not bool:
            raise ValueError("O resultado precisa ser um booleano verificado.")
        before = self.predict(key)
        with self._connect() as db:
            total = int(db.execute("SELECT COUNT(*) FROM prediction_feedback").fetchone()[0])
            if total >= MAX_EVENTS:
                raise ValueError("Limite de observações atingido.")
            identifier = str(uuid.uuid4())
            db.execute(
                "INSERT INTO prediction_feedback VALUES (?,?,?,?,?,NULL)",
                (identifier,key,before["probability"],int(verified_outcome),int(time.time())),
            )
        error = float(verified_outcome) - before["probability"]
        return {"id": identifier, "task": key, "predicted": before["probability"],
                "observed": verified_outcome, "prediction_error": round(error,6),
                "brier": round(error*error,6), "updated": self.predict(key)}

    def revoke(self, observation_id: str) -> bool:
        event = PlasticityLedger._check_uuid(observation_id)
        with self._connect() as db:
            cursor=db.execute(
                "UPDATE prediction_feedback SET revoked_at=? WHERE id=? AND revoked_at IS NULL",
                (int(time.time()),event),
            )
            return cursor.rowcount == 1
