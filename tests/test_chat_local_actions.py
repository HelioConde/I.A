"""Explicit local-chat actions and persistence across conversations/restarts.

No GGUF, internet or user records are used; a synthetic temporary SQLite
store is the only source of memory.
"""
from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brain_ssd.chat.episodic import EpisodicMemory
from brain_ssd.chat.local_actions import local_command
from brain_ssd.chat.server import ChatEngine, create_chat_server


class FakeCore:
    def __init__(self):
        self.prompts = []

    def generate(self, request):
        self.prompts.append(request.prompt)
        return {"return_code": 0, "stdout": "Resposta do modelo.", "metrics": {}}


class FakeRuntime:
    def __init__(self):
        self.core_backend = FakeCore()
        self.prompt_budget_bytes = 3600

    def retrieve(self, question):
        return {"status": "UNAVAILABLE", "context": {"text": ""}, "sources": [], "activated_pages": []}

    def close(self):
        pass


class TestExplicitLocalCommands(unittest.TestCase):
    def test_explicit_nickname_survives_restart_without_model_inference(self):
        with tempfile.TemporaryDirectory() as tmp:
            location = Path(tmp) / "notes.sqlite3"
            store = EpisodicMemory(location)
            runtime = FakeRuntime()
            engine = ChatEngine(lambda: runtime, episodic_store=store)
            engine.start()
            try:
                saved = engine.ask("salve na memoria que seu nome é luna", [])
                self.assertEqual(saved["local_action"], "memory_save")
                self.assertIn("Luna", saved["answer"])
                self.assertEqual(store.get_assistant_name(), "Luna")
                self.assertEqual(runtime.core_backend.prompts, [])
                self.assertFalse(engine.status()["inference_verified"])
            finally:
                engine.close()

            fresh_store = EpisodicMemory(location)
            engine2 = ChatEngine(FakeRuntime, episodic_store=fresh_store)
            engine2.start()
            try:
                name = engine2.ask("Oi, qual é seu nome?", [])
                self.assertEqual(name["local_action"], "assistant_name")
                self.assertIn("Luna", name["answer"])
                direct = engine2.ask("qual é seu nome?", [])
                self.assertEqual(direct["local_action"], "assistant_name")
                self.assertIn("Luna", direct["answer"])
                self.assertIn("Luna", engine2.ask("/nome", [])["answer"])
            finally:
                engine2.close()

    def test_nickname_correction_edits_one_note_and_retains_revision(self):
        with tempfile.TemporaryDirectory() as tmp:
            notes = EpisodicMemory(Path(tmp) / "notes.sqlite3")
            first = local_command("salve na memória que seu nome é Luna", notes)
            self.assertIn("Luna", first["answer"])
            second = local_command("salve na memória que seu nome é Sol", notes)
            self.assertIn("Sol", second["answer"])
            self.assertEqual(notes.get_assistant_name(), "Sol")
            self.assertEqual(len(notes.list()), 1)
            self.assertEqual(len(notes.revisions(notes.list()[0]["id"])), 1)

    def test_casual_statement_does_not_store_automatically(self):
        with tempfile.TemporaryDirectory() as tmp:
            notes = EpisodicMemory(Path(tmp) / "notes.sqlite3")
            for message in ("A partir de hoje seu nome é Luna", "Meu nome é Francisco",
                            "O que significa salvar na memória?"):
                self.assertIsNone(local_command(message, notes))
            self.assertEqual(notes.list(), [])

    def test_regular_note_and_list_are_real_db_operations(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = EpisodicMemory(Path(tmp) / "notes.sqlite3")
            saved = local_command("guarde na memória que meu jogo favorito é xadrez", store)
            self.assertEqual(saved["local_action"], "memory_save")
            self.assertEqual(len(store.list()), 1)
            listed = local_command("/memorias", store)
            self.assertIn("xadrez", listed["answer"])
            self.assertNotIn("Luna", listed["answer"])
            self.assertEqual(local_command("qual seu nome?", store)["local_action"], "assistant_name")

    def test_memories_are_off_by_default_and_no_write_is_claimed(self):
        response = local_command("salve na memória que seu nome é Luna", None)
        self.assertIn("Não salvei", response["answer"])
        self.assertIn("desativada", response["answer"])
        self.assertEqual(response["local_action"], "memory_save")

    def test_commands_are_real_and_separate_from_llm_inference(self):
        engine = ChatEngine(FakeRuntime)
        engine.start()
        try:
            info = engine.ask("quais comandos você tem?", [])
            self.assertIn("/memorias", info["answer"])
            self.assertIn("salve na memória que", info["answer"])
            self.assertFalse(engine.status()["inference_verified"])
            ordinary = engine.ask("Qual é a capital do Brasil?", [])
            self.assertEqual(ordinary["answer"], "Resposta do modelo.")
            self.assertTrue(engine.status()["inference_verified"])
        finally:
            engine.close()

    def test_sse_route_streams_and_saves_explicit_memory(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory = EpisodicMemory(Path(tmp) / "notes.sqlite3")
            engine = ChatEngine(FakeRuntime, episodic_store=memory)
            engine.start()
            server = create_chat_server(engine, ROOT / "chat", port=0, episodic_store=memory)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            origin = f"http://127.0.0.1:{server.server_address[1]}"
            try:
                req = urllib.request.Request(
                    origin + "/api/chat/stream", method="POST",
                    data=json.dumps({
                        "message": "salve na memoria que seu nome é Luna",
                        "request_id": str(uuid.uuid4()),
                    }).encode("utf-8"),
                    headers={"Content-Type": "application/json", "Origin": origin},
                )
                with urllib.request.urlopen(req, timeout=5) as reply:
                    events = reply.read().decode("utf-8")
                self.assertIn("event: delta", events)
                self.assertIn("event: done", events)
                self.assertIn('"local_action":"memory_save"', events)
                self.assertEqual(memory.get_assistant_name(), "Luna")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)
                engine.close()


if __name__ == "__main__":
    unittest.main()
