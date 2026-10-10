"""Small, private, local SQLite conversation store for the Brain-SSD Windows chat.

No cloud account, service or additional Python dependency is required.
Each operation opens its own connection to support ThreadingHTTPServer safely.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Iterator


def default_history_path() -> Path:
    """Keep private chats OUTSIDE the Git repository, including on Windows."""
    local = os.environ.get("LOCALAPPDATA")
    base = Path(local) if local else Path.home() / ".local" / "share"
    return base / "BrainSSD" / "chat-history.sqlite3"


class ChatHistory:
    def __init__(self, filename: Path) -> None:
        self.path = Path(filename).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                    role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_messages_conversation
                  ON messages(conversation_id, id);
                CREATE INDEX IF NOT EXISTS idx_conversations_updated
                  ON conversations(updated_at DESC);
            """)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        # sqlite3's native context manager commits but DOES NOT close the
        # connection. Windows locks the database file until close(), so use
        # an explicit finally block (also required by TemporaryDirectory tests).
        db = sqlite3.connect(self.path, timeout=10.0)
        try:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys = ON")
            db.execute("PRAGMA busy_timeout = 10000")
            try:
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise
        finally:
            db.close()

    @staticmethod
    def _valid_id(conversation_id: Any) -> str:
        if not isinstance(conversation_id, str):
            raise ValueError("ID da conversa inválido.")
        try:
            parsed = uuid.UUID(conversation_id)
        except (ValueError, AttributeError) as exc:
            raise ValueError("ID da conversa inválido.") from exc
        if str(parsed) != conversation_id:
            raise ValueError("ID da conversa inválido.")
        return conversation_id

    def create(self) -> dict[str, Any]:
        identifier = str(uuid.uuid4())
        now = int(time.time())
        with self._connect() as db:
            db.execute(
                "INSERT INTO conversations (id,title,created_at,updated_at) VALUES (?,?,?,?)",
                (identifier, "Nova conversa", now, now),
            )
            db.commit()
        return {"id": identifier, "title": "Nova conversa", "created_at": now, "updated_at": now}

    def list(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT id, title, created_at, updated_at FROM conversations "
                "ORDER BY updated_at DESC, rowid DESC LIMIT ?",
                (max(1, min(int(limit), 100)),),
            ).fetchall()
        return [dict(row) for row in rows]

    def get(self, conversation_id: Any) -> dict[str, Any] | None:
        identifier = self._valid_id(conversation_id)
        with self._connect() as db:
            row = db.execute(
                "SELECT id, title, created_at, updated_at FROM conversations WHERE id=?",
                (identifier,),
            ).fetchone()
        return dict(row) if row is not None else None

    def messages(self, conversation_id: Any, limit: int = 200) -> list[dict[str, str]]:
        identifier = self._valid_id(conversation_id)
        if self.get(identifier) is None:
            raise ValueError("Conversa não encontrada.")
        with self._connect() as db:
            rows = db.execute(
                "SELECT role, content FROM (SELECT id, role, content FROM messages "
                "WHERE conversation_id=? ORDER BY id DESC LIMIT ?) ORDER BY id",
                (identifier, max(1, min(int(limit), 500))),
            ).fetchall()
        return [{"role": row["role"], "content": row["content"]} for row in rows]

    def recent_context(self, conversation_id: Any, limit: int = 8) -> list[dict[str, str]]:
        return [
            {"role": item["role"], "content": item["content"][:700]}
            for item in self.messages(conversation_id, min(limit, 8))[-8:]
        ]

    def append_exchange(self, conversation_id: Any, question: str, answer: str) -> None:
        identifier = self._valid_id(conversation_id)
        if not question.strip() or not answer.strip():
            raise ValueError("Não é possível salvar uma troca vazia.")
        now = int(time.time())
        with self._connect() as db:
            row = db.execute("SELECT title FROM conversations WHERE id=?", (identifier,)).fetchone()
            if row is None:
                raise ValueError("Conversa não encontrada.")
            db.executemany(
                "INSERT INTO messages(conversation_id,role,content,created_at) VALUES (?,?,?,?)",
                ((identifier, "user", question, now), (identifier, "assistant", answer, now)),
            )
            # Use only the first question for a concise, harmless local title.
            title = question.strip().replace("\n", " ")[:55] or "Nova conversa"
            db.execute(
                "UPDATE conversations SET updated_at=?, title=? WHERE id=?",
                (now, title if row["title"] == "Nova conversa" else row["title"], identifier),
            )
            db.commit()

    def delete(self, conversation_id: Any) -> bool:
        identifier = self._valid_id(conversation_id)
        with self._connect() as db:
            cursor = db.execute("DELETE FROM conversations WHERE id=?", (identifier,))
            db.commit()
        return cursor.rowcount > 0
