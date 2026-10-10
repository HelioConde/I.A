"""Mock-free initialization tests for Windows chat without the SSD corpus."""
from __future__ import annotations
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from brain_ssd.chat.runtime import LocalChatRuntime
from brain_ssd.local_runtime.pipeline import MODEL_RELATIVE


class TestOptionalSSD(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        model = self.root / MODEL_RELATIVE
        model.parent.mkdir(parents=True)
        model.write_bytes(b"GGUF" + b"\0" * 32)
        executable = self.root / "third_party/llama.cpp/build-win/bin/llama-completion.exe"
        executable.parent.mkdir(parents=True)
        executable.write_bytes(b"MZ")

    def tearDown(self):
        self.directory.cleanup()

    def test_chat_without_corpus(self):
        runtime = LocalChatRuntime(self.root, profile="economia")
        try:
            self.assertFalse(runtime.status()["knowledge_available"])
            self.assertEqual(runtime.retrieve("Como vai?")["status"], "UNAVAILABLE")
            self.assertEqual(runtime.core_backend.backend.threads, 2)
            self.assertEqual(runtime.core_backend.backend.context_size, 2048)
        finally:
            runtime.close()

    def test_balanced_profile(self):
        runtime = LocalChatRuntime(self.root, profile="equilibrado")
        try:
            self.assertEqual(runtime.core_backend.backend.threads, 4)
            self.assertEqual(runtime.core_backend.backend.context_size, 4096)
        finally:
            runtime.close()

    def test_missing_model(self):
        (self.root / MODEL_RELATIVE).unlink()
        with self.assertRaisesRegex(FileNotFoundError, "GGUF"):
            LocalChatRuntime(self.root)

    def test_economy_releases_knowledge_brain_after_each_query(self):
        runtime = LocalChatRuntime(self.root, profile="economia")
        runtime.has_knowledge_files = True  # mock only the heavy native index
        try:
            with patch("brain_ssd.chat.runtime.LocalBrainSSD") as factory:
                factory.return_value.__enter__.return_value.retrieve.return_value = {"status": "OK"}
                self.assertEqual(runtime.retrieve("Python")["status"], "OK")
                self.assertEqual(runtime.retrieve("SQLite")["status"], "OK")
                self.assertEqual(factory.call_count, 2)
                self.assertIsNone(runtime._brain)
                self.assertEqual(runtime.status()["knowledge_cache"], "per_query")
        finally:
            runtime.close()

    def test_balanced_retains_index_for_session(self):
        runtime = LocalChatRuntime(self.root, profile="equilibrado")
        runtime.has_knowledge_files = True
        try:
            with patch("brain_ssd.chat.runtime.LocalBrainSSD") as factory:
                factory.return_value.retrieve.return_value = {"status": "OK"}
                runtime.retrieve("Python")
                runtime.retrieve("SQLite")
                self.assertEqual(factory.call_count, 1)
                self.assertEqual(runtime.status()["knowledge_cache"], "session")
        finally:
            runtime.close()

    def test_bad_gguf(self):
        (self.root / MODEL_RELATIVE).write_bytes(b"invalid")
        with self.assertRaisesRegex(ValueError, "GGUF"):
            LocalChatRuntime(self.root)


if __name__ == "__main__":
    unittest.main()
