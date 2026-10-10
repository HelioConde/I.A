"""Local SQLite conversation persistence and HTTP contract tests (no GGUF)."""
from __future__ import annotations
import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from brain_ssd.chat.history import ChatHistory
from brain_ssd.chat.server import ChatEngine, create_chat_server


class FakeCore:
    def generate(self, request):
        return {"return_code": 0, "stdout": "Olá, tudo bem?", "metrics": {}}


class FakeRuntime:
    core_backend = FakeCore()
    def retrieve(self, query):
        return {"status": "UNAVAILABLE", "context": {"text": ""}, "sources": [], "activated_pages": []}
    def close(self):
        pass


class TestHistory(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "history.sqlite3"
        self.history = ChatHistory(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_survives_restart_and_preserves_turn_order(self):
        item = self.history.create()
        self.history.append_exchange(item["id"], "Olá!", "Olá, tudo bem?")
        reopened = ChatHistory(self.path)
        self.assertEqual([m["role"] for m in reopened.messages(item["id"])], ["user", "assistant"])
        self.assertEqual(reopened.recent_context(item["id"])[-1]["content"], "Olá, tudo bem?")
        self.assertEqual(reopened.list()[0]["title"], "Olá!")
        self.assertTrue(reopened.delete(item["id"]))
        self.assertEqual(reopened.list(), [])

    def test_unknown_and_invalid_ids_are_not_accepted(self):
        with self.assertRaises(ValueError):
            self.history.messages("../../etc/passwd")
        with self.assertRaises(ValueError):
            self.history.append_exchange("00000000-0000-4000-8000-000000000000", "x", "y")
        self.assertFalse(self.history.delete("00000000-0000-4000-8000-000000000000"))

    def test_http_flow_and_same_origin_delete(self):
        engine = ChatEngine(FakeRuntime)
        engine.start()
        server = create_chat_server(engine, ROOT / "chat", 0, self.history)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_address[1]}"

        def post(path, payload):
            request = urllib.request.Request(url + path, method="POST",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Origin": url, "Content-Type": "application/json"})
            with urllib.request.urlopen(request, timeout=5) as response:
                return json.loads(response.read())

        try:
            identifier = post("/api/conversations", {})["conversation"]["id"]
            chat = post("/api/chat", {"message": "Olá", "conversation_id": identifier})
            self.assertEqual(chat["conversation_id"], identifier)
            self.assertIn("Olá", chat["answer"])
            with urllib.request.urlopen(url + "/api/conversations/" + identifier) as response:
                data = json.loads(response.read())
            self.assertEqual(len(data["messages"]), 2)
            with urllib.request.urlopen(url + "/api/conversations") as response:
                self.assertEqual(len(json.loads(response.read())["conversations"]), 1)
            bad = urllib.request.Request(url + "/api/conversations/" + identifier,
                method="DELETE", headers={"Origin": "https://elsewhere.invalid"})
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(bad, timeout=3)
            self.assertEqual(ctx.exception.code, 403)
            good = urllib.request.Request(url + "/api/conversations/" + identifier,
                method="DELETE", headers={"Origin": url})
            with urllib.request.urlopen(good, timeout=3) as response:
                self.assertTrue(json.loads(response.read())["deleted"])
            self.assertEqual(self.history.list(), [])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
            engine.close()


if __name__ == "__main__":
    unittest.main()
