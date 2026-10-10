"""Brain-SSD chat smoke tests, without loading any model."""
from __future__ import annotations

import json
import sys
import threading
import uuid
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brain_ssd.chat.server import ChatEngine, build_chat_prompt, bounded_chat_prompt, create_chat_server, normalize_history


class FakeCore:
    def __init__(self):
        self.prompts = []

    def generate(self, request):
        self.prompts.append(request.prompt)
        return {
            "return_code": 0,
            "stdout": "Olá! Sou o Brain-SSD, rodando localmente.\n",
            "metrics": {"latency_ms": 1250, "ttft_ms": 220, "working_set_bytes_max": 128 * 1024 ** 2},
        }


class FakeRuntime:
    def __init__(self):
        self.core_backend = FakeCore()
        self.queries = []
        self.closed = False

    def retrieve(self, query):
        self.queries.append(query)
        return {
            "status": "OK",
            "context": {"text": "SSD: dados recuperados em páginas."},
            "sources": [{"source_id": "test"}],
            "activated_pages": [1],
        }

    def close(self):
        self.closed = True


class TestChatEngine(unittest.TestCase):
    def setUp(self):
        self.runtime = FakeRuntime()
        self.engine = ChatEngine(lambda: self.runtime)
        self.engine.start()

    def tearDown(self):
        self.engine.close()

    def test_greeting_uses_real_core_response_without_fake_fallback(self):
        data = self.engine.ask("Olá!", [])
        self.assertIn("Olá!", data["answer"])
        self.assertEqual(data["mode"], "experimental_chat")
        self.assertEqual(data["active_pages"], 0)
        self.assertEqual(self.runtime.queries, [])
        self.assertEqual(len(self.runtime.core_backend.prompts), 1)
        self.assertIn("Olá!", self.runtime.core_backend.prompts[0])

    def test_technical_query_uses_ssd_context(self):
        data = self.engine.ask("Como funciona Python?", [{"role": "user", "content": "Oi"}])
        self.assertEqual(data["active_pages"], 1)
        self.assertEqual(data["sources_from_ssd"], 1)
        self.assertIn("SSD: dados recuperados", self.runtime.core_backend.prompts[0])

    def test_prompt_and_history_bounded(self):
        self.assertEqual(normalize_history({"role": "user"}), [])
        self.assertEqual(len(normalize_history([{"role": "user", "content": "x"}] * 50)), 8)
        prompt = build_chat_prompt("Olá", [{"role": "assistant", "content": "Oi"}], "")
        self.assertIn("Assistente: Oi", prompt)
        with self.assertRaises(ValueError):
            self.engine.ask("x" * 2001, [])

    def test_bounded_context_keeps_latest_question_and_recent_history(self):
        history = [
            {"role": "user", "content": "anterior" * 150},
            {"role": "assistant", "content": "resposta" * 150},
            {"role": "user", "content": "sou o usuário"},
        ]
        prompt, used, evidence = bounded_chat_prompt(
            "Quanto é 2+2?", history, "um trecho muito grande " * 300, 1750
        )
        self.assertIn("Quanto é 2+2?", prompt)
        self.assertLessEqual(len(prompt.encode("utf-8")), 1750)
        self.assertLessEqual(used, len(history))
        self.assertGreaterEqual(evidence, 0)

    def test_self_knowledge_is_specific_and_documented(self):
        memory_prompt = build_chat_prompt("Explique como você usa o SSD e a RAM.", [], "")
        self.assertIn("brain.dat", memory_prompt)
        self.assertIn("cache de arquivos", memory_prompt)
        self.assertIn("não altera pesos do Qwen", memory_prompt)
        capabilities = build_chat_prompt("O que você consegue fazer?", [], "")
        self.assertIn("Capacidades documentadas", capabilities)
        self.assertIn("Não tem internet", capabilities)
        self.assertNotIn("Fatos do Brain-SSD", capabilities)

    def test_self_knowledge_not_injected_into_unrelated_questions(self):
        for question in (
            "Como funciona um SSD?",
            "Quero programar em Python",
            "Como usar memoria RAM em um jogo?",
        ):
            with self.subTest(question=question):
                prompt = build_chat_prompt(question, [], "")
                self.assertNotIn("Capacidades documentadas", prompt)
                self.assertNotIn("Fatos do Brain-SSD", prompt)

    def test_self_explanation_respects_economy_prompt_budget(self):
        prompt, history_count, evidence_bytes = bounded_chat_prompt(
            "Explique como você usa o SSD e a RAM.", [], "Texto não relacionado", 3600
        )
        self.assertLessEqual(len(prompt.encode("utf-8")), 3600)
        self.assertEqual(history_count, 0)
        self.assertGreaterEqual(evidence_bytes, 0)

    def test_qwen_prompt_not_double_wrapped_with_manual_assistant_prefix(self):
        prompt = build_chat_prompt("Explique como o SSD é usado.", [
            {"role": "user", "content": "Olá"},
            {"role": "assistant", "content": "Bom dia"},
        ], "")
        self.assertIn("Pergunta atual do usuário:", prompt)
        self.assertIn("/no_think", prompt)
        self.assertNotIn("\n\nAssistente:\n\n/no_think", prompt)
        self.assertTrue(prompt.endswith("/no_think"))
        self.assertIn("Assistente: Bom dia", prompt)

    def test_repetitive_failed_legacy_answers_are_not_reinjected(self):
        old = [
            {"role": "user", "content": "Explique algo"},
            {"role": "assistant", "content": "Não soube."},
            {"role": "user", "content": "Como está hoje?"},
            {"role": "assistant", "content": "Não sou um assistente, estou apenas criando um modelo de IA experimental. Como uma IA..."},
            {"role": "user", "content": "O que você consegue fazer?"},
        ]
        cleaned = normalize_history(old)
        self.assertEqual(len(cleaned), 3)
        self.assertTrue(all(row["role"] == "user" for row in cleaned))

    def test_large_question_fails_instead_of_being_silently_cut(self):
        with self.assertRaisesRegex(ValueError, "Mensagem longa"):
            bounded_chat_prompt("x" * 2200, [], "", 1000)

    def test_runtime_failure_does_not_pretend_ai_is_ready(self):
        bad = ChatEngine(lambda: (_ for _ in ()).throw(FileNotFoundError("modelo ausente")))
        bad.start()
        self.assertEqual(bad.status()["status"], "error")
        with self.assertRaises(RuntimeError):
            bad.ask("Olá", [])


class TestLifecycle(unittest.TestCase):
    def test_close_during_async_start_never_leaves_runtime_alive(self):
        opened = threading.Event()
        continue_start = threading.Event()
        sessions = []

        class SlowRuntime(FakeRuntime):
            pass

        def factory():
            opened.set()
            self.assertTrue(continue_start.wait(timeout=3))
            obj = SlowRuntime()
            sessions.append(obj)
            return obj

        engine = ChatEngine(factory)
        initializer = threading.Thread(target=engine.start)
        initializer.start()
        self.assertTrue(opened.wait(timeout=2))
        closer = threading.Thread(target=engine.close)
        closer.start()
        continue_start.set()
        initializer.join(timeout=3)
        closer.join(timeout=3)
        self.assertFalse(initializer.is_alive())
        self.assertFalse(closer.is_alive())
        self.assertEqual(len(sessions), 1)
        self.assertTrue(sessions[0].closed)
        self.assertEqual(engine.status()["status"], "stopped")
        engine.start()  # Must not reopen after close.
        self.assertEqual(len(sessions), 1)

    def test_duplicate_start_is_idempotent(self):
        calls = []
        def factory():
            runtime = FakeRuntime()
            calls.append(runtime)
            return runtime
        engine = ChatEngine(factory)
        engine.start()
        engine.start()
        self.assertEqual(len(calls), 1)
        engine.close()
        engine.close()
        self.assertTrue(calls[0].closed)


class TestHttpUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = FakeRuntime()
        cls.engine = ChatEngine(lambda: cls.runtime)
        cls.engine.start()
        cls.server = create_chat_server(cls.engine, ROOT / "chat", port=0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.engine.close()
        cls.thread.join(timeout=3)

    def test_serves_visual_chat_and_status(self):
        with urllib.request.urlopen(self.url + "/", timeout=3) as response:
            html = response.read().decode("utf-8")
        self.assertIn("Como posso ajudar?", html)
        with urllib.request.urlopen(self.url + "/api/status", timeout=3) as response:
            data = json.loads(response.read())
        self.assertTrue(data["local"])
        self.assertEqual(data["status"], "ready")

    def test_chat_post_uses_core_adapter(self):
        data = json.dumps({"message": "Olá", "history": []}).encode("utf-8")
        req = urllib.request.Request(
            self.url + "/api/chat", data=data, method="POST",
            headers={"Origin": self.url, "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=3) as response:
            result = json.loads(response.read())
        self.assertIn("Brain-SSD", result["answer"])
        self.assertEqual(result["metrics"]["working_set_bytes_max"], 128 * 1024 ** 2)
        self.assertEqual(result["metrics"]["ttft_ms"], 220)

    def test_rejects_cross_origin_requests(self):
        req = urllib.request.Request(
            self.url + "/api/chat", data=b'{"message":"Ola"}', method="POST",
            headers={"Origin": "https://example.com", "Content-Type": "application/json"},
        )
        with self.assertRaises(urllib.error.HTTPError) as context:
            urllib.request.urlopen(req, timeout=3)
        self.assertEqual(context.exception.code, 403)

    def test_private_backend_error_is_redacted_in_http_and_sse(self):
        private = "SK_PROJECT_NEVER_LOG_THIS_INTERNAL_SECRET"
        class UnsafeCore(FakeCore):
            def generate(self, request):
                raise RuntimeError("internal failure at C:\\Users\\secret\\" + private)
        class UnsafeRuntime(FakeRuntime):
            def __init__(self):
                super().__init__()
                self.core_backend = UnsafeCore()
        engine = ChatEngine(UnsafeRuntime)
        engine.start()
        server = create_chat_server(engine, ROOT / "chat", port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        origin = f"http://127.0.0.1:{server.server_address[1]}"
        try:
            request = urllib.request.Request(
                origin + "/api/chat", method="POST",
                data=json.dumps({"message": "Olá", "history": []}).encode(),
                headers={"Origin": origin, "Content-Type": "application/json"},
            )
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(request, timeout=5)
            self.assertEqual(ctx.exception.code, 503)
            error_data = ctx.exception.read().decode()
            self.assertNotIn(private, error_data)
            self.assertNotIn("C:\\Users", error_data)

            sse = urllib.request.Request(
                origin + "/api/chat/stream", method="POST",
                data=json.dumps({"message": "Olá", "history": [],
                                 "request_id": str(uuid.uuid4())}).encode(),
                headers={"Origin": origin, "Content-Type": "application/json"},
            )
            with urllib.request.urlopen(sse, timeout=5) as reply:
                events = reply.read().decode()
            self.assertIn("event: error", events)
            self.assertNotIn(private, events)
            self.assertNotIn("C:\\Users", events)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
            engine.close()

    def test_startup_failure_does_not_expose_local_paths(self):
        engine = ChatEngine(lambda: (_ for _ in ()).throw(
            FileNotFoundError("C:\\Users\\Sensitive\\models\\private-model.gguf")))
        engine.start()
        error = engine.status()["error"]
        self.assertNotIn("C:\\Users", error)
        self.assertNotIn("private-model", error)
        engine.close()

    def test_unknown_file_is_not_exposed(self):
        with self.assertRaises(urllib.error.HTTPError) as context:
            urllib.request.urlopen(self.url + "/bad/path", timeout=3)
        self.assertEqual(context.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
