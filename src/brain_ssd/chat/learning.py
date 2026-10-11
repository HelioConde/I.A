"""Opt-in correction-based learning for Brain-SSD.

A user can *explicitly* teach a short reply, and the application stores that
example locally in a separate SQLite database. This is retrieval of a saved
example, NOT fine-tuning, self-training, or an update to the Qwen weights.
Normal chat messages never create learning records.
"""
from __future__ import annotations

import re
import sqlite3
import unicodedata
from pathlib import Path
import os
from typing import Any

MAX_RULES = 120
MAX_TRIGGER = 160
MAX_REPLY = 400


def default_learning_path() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    base = Path(local) if local else Path.home() / ".local" / "share"
    return base / "BrainSSD" / "learned-responses.sqlite3"


def normalize_trigger(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.casefold())
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", text.strip()).strip(" \t\r\n.!?,")


def parse_lesson(message: str) -> tuple[str, str] | None:
    """Recognize deliberately authored examples, not incidental dialogue."""
    if not isinstance(message, str):
        return None
    # Teach exactly one short stimulus and reply; both sides are bounded.
    formats = (
        r"^\s*/ensinar\s+(.+?)\s*=>\s*(.+?)\s*$",
        r"^\s*ensine\s*:\s*(.+?)\s*=>\s*(.+?)\s*$",
        r'^\s*quando\s+eu\s+disser\s+["“\'](.+?)["”\']\s*,?\s*'
        r'responda\s+["“\'](.+?)["”\']\s*[.!]?\s*$',
    )
    for pattern in formats:
        match = re.fullmatch(pattern, message, flags=re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip(), match.group(2).strip()
    return None


def parse_forget(message: str) -> str | None:
    match = re.fullmatch(r"\s*/desaprender\s+(.+?)\s*", message, re.I | re.S)
    return match.group(1).strip() if match else None


def _validated(trigger: str, reply: str) -> tuple[str, str, str]:
    if not isinstance(trigger, str) or not isinstance(reply, str):
        raise ValueError("Ensine com texto: /ensinar pergunta => resposta")
    trigger, reply = trigger.strip(), reply.strip()
    if not (1 <= len(trigger) <= MAX_TRIGGER and 1 <= len(reply) <= MAX_REPLY):
        raise ValueError("Exemplo muito longo: até 160 caracteres na pergunta e 400 na resposta.")
    if any(x in trigger + reply for x in ("\x00", "\r", "\n")):
        raise ValueError("Use somente uma linha para cada lado do exemplo.")
    normalized = normalize_trigger(trigger)
    if not normalized:
        raise ValueError("Exemplo sem pergunta válida.")
    if trigger.startswith("/") or reply.startswith("/") or "<|" in reply or "[INST]" in reply:
        raise ValueError("Não ensine comandos ou delimitadores de sistema como resposta.")
    return trigger, normalized, reply


class LearnedResponses:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS learned_responses (
                    normalized TEXT PRIMARY KEY,
                    trigger TEXT NOT NULL,
                    reply TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
            """)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(str(self.path), timeout=8)
        db.row_factory = sqlite3.Row
        return db

    def teach(self, trigger: str, reply: str) -> dict[str, str]:
        trigger, normalized, reply = _validated(trigger, reply)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            count = db.execute("SELECT COUNT(*) FROM learned_responses").fetchone()[0]
            old = db.execute(
                "SELECT normalized FROM learned_responses WHERE normalized=?", (normalized,)
            ).fetchone()
            if count >= MAX_RULES and old is None:
                raise ValueError("Limite de aprendizados atingido; use /desaprender para liberar espaço.")
            db.execute("""
                INSERT INTO learned_responses (normalized, trigger, reply)
                VALUES (?, ?, ?)
                ON CONFLICT(normalized) DO UPDATE SET
                    trigger=excluded.trigger, reply=excluded.reply,
                    updated_at=datetime('now')
            """, (normalized, trigger, reply))
        return {"trigger": trigger, "reply": reply}

    def match(self, question: str) -> str | None:
        normalized = normalize_trigger(question)
        if not normalized or len(normalized) > MAX_TRIGGER:
            return None
        with self._connect() as db:
            row = db.execute(
                "SELECT reply FROM learned_responses WHERE normalized=?", (normalized,)
            ).fetchone()
        return row["reply"] if row is not None else None

    def list(self, limit: int = 10) -> list[dict[str, str]]:
        limit = min(max(int(limit), 1), 20)
        with self._connect() as db:
            rows = db.execute(
                "SELECT trigger, reply FROM learned_responses "
                "ORDER BY updated_at DESC, rowid DESC LIMIT ?", (limit,)
            ).fetchall()
        return [{"trigger": row["trigger"], "reply": row["reply"]} for row in rows]

    def forget(self, trigger: str) -> bool:
        normalized = normalize_trigger(trigger)
        if not normalized:
            raise ValueError("Informe a frase ensinada.")
        with self._connect() as db:
            changed = db.execute(
                "DELETE FROM learned_responses WHERE normalized=?", (normalized,)
            ).rowcount
        return changed > 0


def learned_action(question: str, store: LearnedResponses | None,
                   *, bypass_match: bool = False) -> dict[str, Any] | None:
    lesson = parse_lesson(question)
    forgetting = parse_forget(question)
    norm = normalize_trigger(question)
    if lesson is None and forgetting is None and norm not in ("/aprendizados", "/aprendizado"):
        if store is None or bypass_match:
            return None
        # The reply is a saved user correction, not text generated by the LLM.
        reply = store.match(question)
        return _result(reply, "learned_reply") if reply is not None else None

    if store is None:
        return _result(
            "Aprendizado local está desativado nesta sessão. Nenhum exemplo foi salvo.",
            "learning_off",
        )
    if lesson is not None:
        saved = store.teach(*lesson)
        return _result(
            f"Aprendi este exemplo no SQLite local: quando você disser "
            f"“{saved['trigger']}”, responderei “{saved['reply']}”. "
            "Isso não alterou os pesos do modelo.",
            "learning_save",
        )
    if forgetting is not None:
        removed = store.forget(forgetting)
        return _result(
            "Exemplo apagado do aprendizado local." if removed else "Não encontrei esse exemplo.",
            "learning_delete",
        )
    rows = store.list()
    if not rows:
        return _result("Nenhum exemplo ensinado ainda. Use /ensinar Olá => Olá!", "learning_list")
    rendered = "\n".join(
        f"{i}. {row['trigger']} → {row['reply']}"
        for i, row in enumerate(rows, 1)
    )
    return _result("Exemplos ensinados (até 10):\n" + rendered, "learning_list")


def _result(answer: str, action: str) -> dict[str, Any]:
    return {
        "answer": answer, "mode": "local_command",
        "local_action": action, "source": "local_learning_sqlite",
        "metrics": {}, "active_pages": 0, "sources_from_ssd": 0,
        "episodic_memories_used": 0,
        "episodic_ambiguities_detected": 0,
        "episodic_ambiguities_withheld": False,
        "cognitive_shadow": None,
        "note": "Exemplo explícito recuperado ou alterado no SQLite; nenhuma inferência Qwen.",
    }
