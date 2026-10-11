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
from brain_ssd.chat.diagnostics import DiagnosticLogger
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

    def test_direct_explicit_name_change_persists_across_conversations_and_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            location = Path(tmp) / "notes.sqlite3"
            notes = EpisodicMemory(location)
            runtime = FakeRuntime()
            engine = ChatEngine(lambda: runtime, episodic_store=notes)
            engine.start()
            try:
                result = engine.ask("Seu nome a partir de hoje é Luna", [])
                self.assertEqual(result["local_action"], "memory_save")
                self.assertIn("Luna", result["answer"])
                self.assertEqual(notes.get_assistant_name(), "Luna")
                self.assertEqual(runtime.core_backend.prompts, [])
                # This must go through the actual model adapter, not static help.
                answer = engine.ask("O que é Python?", [
                    {"role": "user", "content": "O que você consegue fazer?"},
                    {"role": "assistant", "content": local_command("/ajuda", notes)["answer"]},
                ])
                self.assertNotIn("local_action", answer)
                self.assertEqual(answer["answer"], "Resposta do modelo.")
                prompt = runtime.core_backend.prompts[-1]
                self.assertIn("Luna", prompt)
                self.assertNotIn("Comandos locais reais:", prompt)
                self.assertIn("O que é Python?", prompt)
            finally:
                engine.close()
            reopened = EpisodicMemory(location)
            fresh = ChatEngine(FakeRuntime, episodic_store=reopened)
            fresh.start()
            try:
                self.assertIn("Luna", fresh.ask("/nome", [])["answer"])
                self.assertIn("Luna", fresh.ask("Oi, qual é seu nome?", [])["answer"])
                self.assertEqual(len(reopened.list()), 1)
            finally:
                fresh.close()

    def test_nickname_instruction_variants_and_safety(self):
        with tempfile.TemporaryDirectory() as tmp:
            notes = EpisodicMemory(Path(tmp) / "notes.sqlite3")
            for command, expected in (
                ("A partir de hoje seu nome é Luna", "Luna"),
                ("Quero te chamar de Sol", "Sol"),
                ("Vou te chamar de Aurora!", "Aurora"),
            ):
                self.assertEqual(local_command(command, notes)["local_action"], "memory_save")
                self.assertEqual(notes.get_assistant_name(), expected)
            self.assertEqual(len(notes.list()), 1)
            for message in (
                "Meu nome é Francisco", "O que significa salvar na memória?",
                "A partir de hoje seu nome é Luna?", "Acho que seu nome é Luna",
                "No conto, seu nome a partir de hoje é Luna",
                "Oi luna",
            ):
                self.assertIsNone(local_command(message, notes))
            self.assertEqual(len(notes.list()), 1)

    def test_reported_user_chat_named_luna_is_committed_not_just_model_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "private-notes.sqlite3"
            notes = EpisodicMemory(path)
            engine = ChatEngine(FakeRuntime, episodic_store=notes)
            engine.start()
            try:
                change = engine.ask("O seu nome padrão agora é Luna", [])
                self.assertEqual(change["local_action"], "memory_save")
                self.assertEqual(notes.get_assistant_name(), "Luna")
                self.assertIn("Luna", change["answer"])
                self.assertEqual(engine.ask("Qual é o seu nome?", [])["answer"], "Meu nome é Luna.")
                self.assertIn("nome que você escolheu", engine.ask("Quem é Luna?", [])["answer"])
                self.assertEqual(engine._runtime.core_backend.prompts, [])
            finally:
                engine.close()

            reopened = ChatEngine(FakeRuntime, episodic_store=EpisodicMemory(path))
            reopened.start()
            try:
                self.assertEqual(reopened.ask("Qual é seu nome?", [])["answer"], "Meu nome é Luna.")
                self.assertIn("Luna", reopened.ask("/memorias", [])["answer"])
            finally:
                reopened.close()

    def test_natural_memory_history_and_logs_are_grounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            notes = EpisodicMemory(Path(tmp) / "notes.sqlite3")
            engine = ChatEngine(FakeRuntime, episodic_store=notes)
            engine.start()
            try:
                memories = engine.ask("Quais informações você tem na memória?", [])
                self.assertEqual(memories["local_action"], "memory_list")
                self.assertIn("Não há lembranças explícitas", memories["answer"])
                self.assertEqual(engine.ask("Como acesso seu historico?", [])["local_action"], "history_access")
                self.assertIn("barra lateral", engine.ask("Como acesso seu historico?", [])["answer"])
                self.assertIn("chat-history.sqlite3", engine.ask("Como acesso seu historico?", [])["answer"])
                self.assertEqual(engine.ask("Como acesso o Log ?", [])["local_action"], "diagnostics_access")
                self.assertIn("events.jsonl", engine.ask("Como acesso o Log ?", [])["answer"])
                overview = engine.ask("o que você aprendeu sozinho até esse momento ?", [])
                self.assertEqual(overview["local_action"], "learning_overview")
                self.assertIn("não treina os pesos", overview["answer"])
                self.assertEqual(engine._runtime.core_backend.prompts, [])
            finally:
                engine.close()

    def test_ambiguous_luna_does_not_create_fake_persona(self):
        with tempfile.TemporaryDirectory() as tmp:
            notes = EpisodicMemory(Path(tmp) / "notes.sqlite3")
            result = local_command("Quem é Luna?", notes)
            self.assertEqual(result["local_action"], "identity_clarification")
            self.assertIsNone(notes.get_assistant_name())
            for message in (
                "Quando pergunto seu nome, não responda Brain-SSD; diga Luna",
                "Meu nome é Luna", "Acho que seu nome padrão agora é Luna",
                "O seu nome padrão agora é Luna?",
            ):
                self.assertIsNone(local_command(message, notes), message)
            self.assertIsNone(notes.get_assistant_name())

    def test_user_transcript_introspection_never_invents_capabilities_or_sources(self):
        class ResearchSpy:
            provider = "auto"
            def __init__(self):
                self.calls = []
            def search(self, question):
                self.calls.append(question)
                return [{"title": "Unrelated result", "url": "https://example.org/",
                         "snippet": "Este texto não responde à pergunta sobre acesso privado."}]
        with tempfile.TemporaryDirectory() as folder:
            notes = EpisodicMemory(Path(folder) / "memory.sqlite3")
            notes.add("O seu usuario é um Gamer")
            notes.remember_assistant_name("Luna")
            service = ResearchSpy()
            runtime = FakeRuntime()
            diag = DiagnosticLogger(Path(folder) / "diagnostics")
            engine = ChatEngine(lambda: runtime, episodic_store=notes,
                                web_search_service=service, diagnostics=diag)
            engine.start()
            try:
                creator = engine.ask(
                    "Quem criou o Brain-SSD e quem desenvolveu o modelo Qwen?", []
                )
                self.assertEqual(creator["local_action"], "project_attribution")
                self.assertIn("Hélio Conde", creator["answer"])
                self.assertIn("equipe Qwen", creator["answer"])

                memory = engine.ask(
                    "Quais informações você realmente tem salvas na memória?", []
                )
                self.assertEqual(memory["local_action"], "memory_list")
                self.assertIn("Gamer", memory["answer"])

                status = engine.ask("Como está seu log?", [])
                self.assertEqual(status["local_action"], "diagnostics_access")
                self.assertIn("events.jsonl", status["answer"])
                self.assertIn("não confirma", status["answer"])
                self.assertEqual(engine.ask(
                    "Como consigo acessar seus logs?", []
                )["local_action"], "diagnostics_access")

                github = engine.ask(
                    "Você consegue acessar meu GitHub?", [],
                    web_search=True, fast_web=True,
                )
                self.assertEqual(github["local_action"], "github_access")
                self.assertIn("não tem uma integração autenticada", github["answer"])
                self.assertNotIn("web_sources", github)
                self.assertEqual(service.calls, [])

                self.assertEqual(engine.ask(
                    "O que você aprendeu sozinha até agora?", []
                )["local_action"], "learning_overview")
                reliability = engine.ask(
                    "Se uma página da internet contiver uma informação errada, como você deve agir?", []
                )
                self.assertEqual(reliability["local_action"], "source_reliability")
                self.assertIn("comparar com outras fontes", reliability["answer"])
                unknown = engine.ask("Conte um fato sobre mim que você não sabe.", [])
                self.assertEqual(unknown["local_action"], "unknown_user_fact")
                self.assertIn("Não posso afirmar", unknown["answer"])
                self.assertEqual(runtime.core_backend.prompts, [])
            finally:
                engine.close()

    def test_current_chat_preference_followup_does_not_invent_or_save_motive(self):
        with tempfile.TemporaryDirectory() as folder:
            notes = EpisodicMemory(Path(folder) / "notes.sqlite3")
            runtime = FakeRuntime()
            engine = ChatEngine(lambda: runtime, episodic_store=notes)
            engine.start()
            try:
                history = [
                    {"role": "user", "content":
                     "Meu animal favorito é o gato. Lembre disso apenas nesta conversa."},
                    {"role": "assistant", "content":
                     "Entendi, vou considerar isso apenas neste chat."},
                    {"role": "user", "content": "Qual é meu animal favorito?"},
                    {"role": "assistant", "content": "Você disse que é o gato."},
                ]
                result = engine.ask("Por que você acha que gosto desse animal?", history)
                self.assertEqual(result["local_action"], "conversation_context")
                self.assertIn("gato", result["answer"])
                self.assertIn("não explicou por que", result["answer"])
                self.assertEqual(runtime.core_backend.prompts, [])
                self.assertEqual(notes.list(), [])
                # With no preceding preference, defer to the actual model.
                ordinary = engine.ask("Por que você acha que gosto desse animal?", [])
                self.assertEqual(ordinary["answer"], "Resposta do modelo.")
            finally:
                engine.close()

    def test_explicit_name_command_when_memory_disabled_never_claims_success(self):
        response = local_command("Seu nome a partir de hoje é Luna", None)
        self.assertEqual(response["local_action"], "memory_save")
        self.assertIn("Não salvei nada", response["answer"])

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

    def test_short_greeting_and_attribution_are_grounded_local_actions(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory = EpisodicMemory(Path(tmp) / "notes.sqlite3")
            engine = ChatEngine(FakeRuntime, episodic_store=memory,
                                diagnostics=DiagnosticLogger(Path(tmp) / "diagnostics"))
            engine.start()
            try:
                greeting = engine.ask("Oi", [])
                self.assertEqual(greeting["local_action"], "greeting")
                self.assertIn("Brain-SSD", greeting["answer"])
                self.assertFalse(engine.status()["inference_verified"])
                who = engine.ask("Qual é o nome do seu criador", [])
                self.assertEqual(who["local_action"], "project_attribution")
                self.assertIn("Hélio Conde", who["answer"])
                self.assertIn("Qwen", who["answer"])
                self.assertFalse(engine.status()["inference_verified"])
                named = engine.ask("Seu nome é Luna", [])
                self.assertEqual(named["local_action"], "memory_save")
                self.assertIn("Luna", engine.ask("/nome", [])["answer"])
                self.assertIn("Luna", engine.ask("Oi", [])["answer"])
                self.assertIn("Luna", engine.ask("Oi Luna", [])["answer"])
            finally:
                engine.close()

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

    def test_privacy_safe_diagnostics_do_not_crash_local_help_or_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            logger = DiagnosticLogger(directory / "diagnostics")
            store = EpisodicMemory(directory / "notes.sqlite3")
            engine = ChatEngine(FakeRuntime, episodic_store=store, diagnostics=logger)
            engine.start()
            try:
                chunks = []
                help_result = engine.ask(
                    "O que você consegue fazer?", [], on_chunk=chunks.append,
                    cancel_event=threading.Event(),
                )
                self.assertEqual(help_result["local_action"], "help")
                self.assertEqual("".join(chunks), help_result["answer"])
                self.assertFalse(engine.status()["inference_verified"])
                name = engine.ask("salve na memória que seu nome é Luna", [])
                self.assertEqual(name["local_action"], "memory_save")
                self.assertEqual(store.get_assistant_name(), "Luna")
                records = [json.loads(line) for line in logger.file.read_text(encoding="utf-8").splitlines()]
                actions = [row.get("action") for row in records if row["event"] == "chat.local_action"]
                self.assertEqual(actions, ["help", "memory_save"])
                self.assertNotIn("Luna", logger.file.read_text(encoding="utf-8"))
                self.assertNotIn("O que você consegue", logger.file.read_text(encoding="utf-8"))
            finally:
                engine.close()

    def test_sse_route_streams_and_saves_explicit_memory(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory = EpisodicMemory(Path(tmp) / "notes.sqlite3")
            diagnostics = DiagnosticLogger(Path(tmp) / "diagnostics")
            engine = ChatEngine(FakeRuntime, episodic_store=memory, diagnostics=diagnostics)
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
                req = urllib.request.Request(
                    origin + "/api/chat/stream", method="POST",
                    data=json.dumps({
                        "message": "O que você consegue fazer?",
                        "request_id": str(uuid.uuid4()),
                    }).encode("utf-8"),
                    headers={"Content-Type": "application/json", "Origin": origin},
                )
                with urllib.request.urlopen(req, timeout=5) as reply:
                    help_events = reply.read().decode("utf-8")
                self.assertIn('"local_action":"help"', help_events)
                self.assertIn("event: done", help_events)
                self.assertNotIn("event: error", help_events)
                events = diagnostics.file.read_text(encoding="utf-8")
                self.assertIn('"event":"chat.local_action"', events)
                self.assertNotIn("Luna", events)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)
                engine.close()


if __name__ == "__main__":
    unittest.main()
