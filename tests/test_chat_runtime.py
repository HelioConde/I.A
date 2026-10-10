"""Mock-free initialization tests for Windows chat without the SSD corpus."""
from __future__ import annotations
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from brain_ssd.chat.runtime import LocalChatRuntime, PROFILES
from brain_ssd.local_runtime.pipeline import MODEL_RELATIVE


class TestOptionalSSD(unittest.TestCase):
    def setUp(self):
        minimum=patch("brain_ssd.chat.runtime.MIN_PLAUSIBLE_GGUF_BYTES", 32)
        minimum.start()
        self.addCleanup(minimum.stop)
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

    def test_official_runtime_fallback_is_isolated_from_frozen_backend(self):
        from brain_ssd.chat.runtime import resolve_chat_completion
        from brain_ssd.local_runtime.backend import resolve_llama_executable
        community=self.root/"third_party/llama.cpp/runtime-win-cpu-x64/bin/llama-completion.exe"
        community.parent.mkdir(parents=True)
        community.write_bytes(b"MZ community binary")
        self.assertEqual(resolve_chat_completion(self.root),community.resolve())
        frozen=resolve_llama_executable(self.root)
        self.assertNotEqual(frozen,community)
        runtime=LocalChatRuntime(self.root,profile="economia")
        try:
            self.assertEqual(runtime.core_backend.runtime_path,community.resolve())
            self.assertEqual(runtime._completion_path,frozen)
        finally:
            runtime.close()

    def test_community_runtime_works_without_frozen_checkout(self):
        from brain_ssd.chat.runtime import resolve_chat_completion
        frozen=self.root/"third_party/llama.cpp/build-win/bin/llama-completion.exe"
        frozen.unlink()
        community=self.root/"third_party/llama.cpp/runtime-win-cpu-x64/bin/llama-completion.exe"
        community.parent.mkdir(parents=True)
        community.write_bytes(b"MZ community binary")
        self.assertEqual(resolve_chat_completion(self.root),community)
        runtime=LocalChatRuntime(self.root,profile="economia")
        try:
            self.assertEqual(runtime._completion_path,community.resolve())
            self.assertFalse(runtime.status()["knowledge_available"])  # No corpus in this fixture
            self.assertEqual(runtime.status()["retrieval_runtime"], "official_cpu_distribution")
            self.assertEqual(runtime.core_backend.runtime_path,community)
        finally:
            runtime.close()

    def test_official_cpu_runtime_enables_optional_ssd_retrieval(self):
        frozen = self.root / "third_party/llama.cpp/build-win/bin/llama-completion.exe"
        frozen.unlink()
        community = self.root / "third_party/llama.cpp/runtime-win-cpu-x64/bin/llama-completion.exe"
        community.parent.mkdir(parents=True)
        community.write_bytes(b"MZ community binary")
        # Only path presence is tested here; no real corpus or model is loaded.
        for relative in (
            "brain_data/real_knowledge/semantic/manifest.json",
            "brain_data/real_knowledge/semantic/brain.dat",
            "brain_data/real_knowledge/index/record-index.json.gz",
        ):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"fixture")

        runtime = LocalChatRuntime(self.root, profile="economia")
        try:
            self.assertTrue(runtime.status()["knowledge_available"])
            self.assertEqual(runtime.status()["retrieval_runtime"], "official_cpu_distribution")
            with patch("brain_ssd.chat.runtime.LocalBrainSSD") as factory:
                instance = factory.return_value.__enter__.return_value
                instance.retrieve.return_value = {"status": "OK", "activated_pages": [0]}
                result = runtime.retrieve("O que e SQLite?")
                self.assertEqual(result["status"], "OK")
                self.assertEqual(factory.call_args.args[0], self.root)
                self.assertEqual(factory.call_args.kwargs["executable"], community.resolve())
        finally:
            runtime.close()

    def test_all_profiles_have_complete_budgets(self):
        for name, values in PROFILES.items():
            with self.subTest(profile=name):
                self.assertIn("threads", values)
                self.assertIn("context_size", values)
                self.assertIn("knowledge_budget", values)
                self.assertIn("prompt_budget_bytes", values)
                self.assertGreater(values["prompt_budget_bytes"], 1000)

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
        with self.assertRaisesRegex(RuntimeError, "Modelo GGUF ausente"):
            LocalChatRuntime(self.root)

    def test_short_gguf_fails_preflight_before_native_model_load(self):
        with patch("brain_ssd.chat.runtime.MIN_PLAUSIBLE_GGUF_BYTES", 64):
            with self.assertRaisesRegex(RuntimeError, "GGUF"):
                LocalChatRuntime(self.root)

    def test_missing_binary_is_classified_without_local_path_in_status(self):
        (self.root / "third_party/llama.cpp/build-win/bin/llama-completion.exe").unlink()
        # Linux resolver also checks without .exe.
        bare = self.root / "third_party/llama.cpp/build-win/bin/llama-completion"
        if bare.is_file():
            bare.unlink()
        from brain_ssd.chat.server import ChatEngine
        messages=[]
        engine=ChatEngine(lambda: LocalChatRuntime(self.root,profile="economia"),
                          startup_reporter=messages.append)
        engine.start()
        try:
            info=engine.status()
            self.assertEqual(info["startup_error_code"], "CORE_MISSING")
            self.assertEqual(len(messages),1)
            self.assertNotIn(str(self.root), str(info))
        finally:
            engine.close()

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
        with self.assertRaisesRegex(RuntimeError, "GGUF"):
            LocalChatRuntime(self.root)


if __name__ == "__main__":
    unittest.main()
