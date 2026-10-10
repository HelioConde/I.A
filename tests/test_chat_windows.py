"""Brain-SSD chat smoke tests, without loading any model."""
from __future__ import annotations

import json
import sys
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brain_ssd.chat.server import ChatEngine, build_chat_prompt, create_chat_server, normalize_history


class FakeCore:
    def __init__(self):
        self.prompts = []

    def generate(self, request):
        self.prompts.append(request.prompt)
        return {
            "return_code": 0,
            "stdout": "Olá! Sou o Brain-SSD, rodando localmente.\n",
            "metrics": {"latency_ms": 1250, "working_set_bytes_max": 128 * 1024 ** 2},
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

    def test_runtime_failure_does_not_pretend_ai_is_ready(self):
        bad = ChatEngine(lambda: (_ for _ in ()).throw(FileNotFoundError("modelo ausente")))
        bad.start()
        self.assertEqual(bad.status()["status"], "error")
        with self.assertRaises(RuntimeError):
            bad.ask("Olá", [])


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

    def test_rejects_cross_origin_requests(self):
        req = urllib.request.Request(
            self.url + "/api/chat", data=b'{"message":"Ola"}', method="POST",
            headers={"Origin": "https://example.com", "Content-Type": "application/json"},
        )
        with self.assertRaises(urllib.error.HTTPError) as context:
            urllib.request.urlopen(req, timeout=3)
        self.assertEqual(context.exception.code, 403)

    def test_unknown_file_is_not_exposed(self):
        with self.assertRaises(urllib.error.HTTPError) as context:
            urllib.request.urlopen(self.url + "/bad/path", timeout=3)
        self.assertEqual(context.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
