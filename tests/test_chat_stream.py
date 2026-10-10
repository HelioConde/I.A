"""SSE, native chat streaming and cancellation tests, without downloading GGUF."""
from __future__ import annotations

import json
import sys
import tempfile
from types import SimpleNamespace
import threading
import time
import unittest
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from brain_ssd.chat.history import ChatHistory
from brain_ssd.chat.server import ChatEngine, create_chat_server
from brain_ssd.chat.streaming import GenerationCancelled, generate_streamed
from brain_ssd.local_runtime.core_backend import SubprocessPerQueryCore, PersistentCoreBackend


class DummyCore:
    def generate(self, request):
        return {"return_code": 0, "stdout": "Olá, eu sou o Brain-SSD.", "metrics": {"latency_ms": 42}}


class DummyRuntime:
    core_backend = DummyCore()
    profile = "economia"
    core_mode = "subprocess"

    def retrieve(self, question):
        return {"status": "UNAVAILABLE", "context": {"text": ""}, "sources": [], "activated_pages": []}

    def close(self):
        pass


class TestNativeStreaming(unittest.TestCase):
    def test_fake_core_fallback_is_explicitly_not_native(self):
        output = []
        measured = generate_streamed(DummyCore(), self._request("Olá"), output.append, threading.Event())
        self.assertEqual(measured["stdout"], "".join(output))

    @staticmethod
    def _request(message):
        from brain_ssd.backend import GenerationRequest
        return GenerationRequest(message)

    def test_pre_cancelled_never_calls_model(self):
        event = threading.Event()
        event.set()
        with self.assertRaises(GenerationCancelled):
            generate_streamed(DummyCore(), self._request("Olá"), lambda _: None, event)


class TestPipeCancellation(unittest.TestCase):
    """Uses an actual Python child to verify process I/O and cancellation.

    This is NOT a Qwen quality test. It covers real OS process termination.
    """
    def core_with_child(self, script):
        core = SubprocessPerQueryCore(Path(sys.executable), Path(sys.executable))
        core.backend = SimpleNamespace(command=lambda _: [sys.executable, "-u", "-c", script])
        return core

    def test_real_pipe_delivers_chunks(self):
        core = self.core_with_child("import sys,time;print('Primeiro',flush=True);time.sleep(.15);print('Segundo',flush=True)")
        chunks = []
        measured = generate_streamed(core, self._request(), chunks.append, threading.Event())
        self.assertEqual(measured["return_code"], 0)
        self.assertIn("Primeiro", "".join(chunks))
        self.assertIn("Segundo", "".join(chunks))
        self.assertEqual(core.query_count, 1)

    def test_cancel_kills_real_child(self):
        # Child never exits on its own within the test. Cancellation MUST end it.
        core = self.core_with_child("import sys,time;print('Começou',flush=True);time.sleep(25)")
        cancelled = threading.Event()
        chunks = []

        def receive(part):
            chunks.append(part)
            cancelled.set()

        start = time.monotonic()
        with self.assertRaises(GenerationCancelled):
            generate_streamed(core, self._request(), receive, cancelled)
        self.assertLess(time.monotonic() - start, 5)
        self.assertIn("Começou", "".join(chunks))
        self.assertEqual(core.query_count, 0)

    @staticmethod
    def _request():
        from brain_ssd.backend import GenerationRequest
        return GenerationRequest("olá")


class TestPersistentModelLoadCancellation(unittest.TestCase):
    def test_stop_during_model_loading_exits_before_timeout(self):
        class Child:
            def __init__(self):
                self.stopped = threading.Event()
            def poll(self):
                return 1 if self.stopped.is_set() else None
            def terminate(self):
                self.stopped.set()
            def wait(self, timeout=None):
                return 1
            def kill(self):
                self.stopped.set()

        child = Child()
        core = object.__new__(PersistentCoreBackend)
        core.process = child
        core.host = "127.0.0.1"
        core.port = 9000
        started = threading.Event()
        closed = threading.Event()

        def slow_start():
            started.set()
            if not child.stopped.wait(timeout=4):
                raise RuntimeError("A model stayed loading without cancellation")
            raise RuntimeError("persistent Core exited during loading")
        core.start = slow_start
        core.close = closed.set
        signal = threading.Event()
        from brain_ssd.backend import GenerationRequest

        def interrupt():
            self.assertTrue(started.wait(timeout=2))
            signal.set()
        stopper = threading.Thread(target=interrupt)
        stopper.start()
        before = time.monotonic()
        with self.assertRaises(GenerationCancelled):
            generate_streamed(core, GenerationRequest("Olá"), lambda _: None, signal)
        stopper.join(timeout=3)
        self.assertLess(time.monotonic() - before, 3)
        self.assertTrue(child.stopped.is_set())
        self.assertTrue(closed.is_set())


class TestHttpStreaming(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = ChatHistory(Path(self.directory.name) / "history.sqlite3")
        self.engine = ChatEngine(DummyRuntime)
        self.engine.start()
        self.server = create_chat_server(self.engine, ROOT / "chat", port=0, history_store=self.store)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.engine.close()
        self.directory.cleanup()

    def post(self, path, payload, origin=None):
        request = urllib.request.Request(
            self.base + path, data=json.dumps(payload).encode("utf-8"),
            method="POST", headers={"Content-Type": "application/json",
                                    "Origin": origin or self.base})
        return urllib.request.urlopen(request, timeout=5)

    def test_live_events_and_history(self):
        conversation = self.store.create()
        token = str(uuid.uuid4())
        with self.post("/api/chat/stream", {"message": "Olá!", "conversation_id": conversation["id"],
                                           "request_id": token}) as response:
            self.assertIn("text/event-stream", response.headers.get("Content-Type", ""))
            body = response.read().decode("utf-8")
        self.assertIn("event: started", body)
        self.assertIn("event: delta", body)
        self.assertIn("event: done", body)
        self.assertEqual(len(self.store.messages(conversation["id"])), 2)
        self.assertTrue(self.engine.status()["inference_verified"])

    def test_cancel_interrupts_and_does_not_persist_incomplete_answer(self):
        convo = self.store.create()
        token = str(uuid.uuid4())
        started = threading.Event()
        response_chunks = []

        def slow_generator(core, request, on_chunk, cancel):
            on_chunk("Um texto parcial")
            started.set()
            if not cancel.wait(4):
                raise AssertionError("cancel was not signaled")
            raise GenerationCancelled()

        def read_stream():
            with self.post("/api/chat/stream", {"message": "Olá!", "conversation_id": convo["id"],
                                               "request_id": token}) as response:
                response_chunks.append(response.read().decode("utf-8"))

        with patch("brain_ssd.chat.server.generate_streamed", side_effect=slow_generator):
            worker = threading.Thread(target=read_stream, daemon=True)
            worker.start()
            self.assertTrue(started.wait(timeout=4))
            with self.post("/api/chat/cancel", {"request_id": token}) as response:
                self.assertTrue(json.loads(response.read())["cancelled"])
            worker.join(timeout=5)
            self.assertFalse(worker.is_alive())
        self.assertIn("event: cancelled", "".join(response_chunks))
        self.assertNotIn("event: done", "".join(response_chunks))
        self.assertEqual(self.store.messages(convo["id"]), [])

    def test_cross_origin_cannot_cancel(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.post("/api/chat/cancel", {"request_id": str(uuid.uuid4())},
                      origin="https://malicious.invalid")
        self.assertEqual(ctx.exception.code, 403)

    def test_invalid_stream_id_is_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.post("/api/chat/stream", {"request_id": "../hack", "message": "Olá"})
        self.assertEqual(ctx.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
