"""Memory-safe CPU inference policy for 4B models (no model downloads)."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from brain_ssd.chat.performance import (
    GiB, MemoryInfo, choose_mode, recommended_threads, answer_token_limit,
    compact_profile,
)
from brain_ssd.chat.runtime import LocalChatRuntime
from brain_ssd.chat.server import ChatEngine


class TestPerformancePolicy(unittest.TestCase):
    def test_persistent_only_with_large_ram_headroom_and_server(self):
        size = int(2.5 * GiB)
        self.assertEqual(choose_mode("equilibrado", size, True, MemoryInfo(16*GiB, 10*GiB))[0], "persistent")
        for profile, available, server in (
            ("equilibrado", 5*GiB, True),
            ("equilibrado", 10*GiB, False),
            ("economia", 10*GiB, True),
        ):
            with self.subTest(profile=profile, available=available, server=server):
                self.assertEqual(choose_mode(profile, size, server, MemoryInfo(16*GiB, available))[0], "subprocess")
        self.assertEqual(choose_mode("equilibrado", size, True, MemoryInfo(8*GiB, 7*GiB))[0], "subprocess")
        self.assertEqual(choose_mode("equilibrado", size, True, None)[0], "subprocess")

    def test_threads_leave_desktop_headroom_and_limit_output(self):
        self.assertEqual(recommended_threads("equilibrado", 16), 6)
        self.assertEqual(recommended_threads("equilibrado", 8), 4)
        self.assertEqual(recommended_threads("economia", 16), 2)
        self.assertEqual(answer_token_limit(int(2.5*GiB)), 112)
        self.assertEqual(answer_token_limit(1*GiB), 160)
        self.assertEqual(answer_token_limit(int(2.5*GiB), 256), 256)
        self.assertEqual(compact_profile("equilibrado", int(2.5*GiB), 4096, 7600),
                         (3072, 5600, 112))
        self.assertEqual(compact_profile("economia", int(2.5*GiB), 2048, 3600),
                         (2048, 3600, 112))
        for illegal in (0, 512, "100", True, 22.5):
            with self.subTest(illegal=illegal), self.assertRaises(ValueError):
                answer_token_limit(int(2.5*GiB), illegal)

    def test_auto_without_llama_server_uses_tuned_subprocess_and_no_extra_ram(self):
        with TemporaryDirectory() as folder:
            root=Path(folder)
            model=root/"models"/"Qwen3-4B-Q4_K_M.gguf"
            model.parent.mkdir(parents=True)
            model.write_bytes(b"GGUF" + b"0" * 128)
            exe=root/"third_party"/"llama.cpp"/"runtime-win-cpu-x64"/"bin"/"llama-completion.exe"
            exe.parent.mkdir(parents=True)
            exe.write_bytes(b"MZ")
            with patch("brain_ssd.chat.runtime.windows_memory", return_value=MemoryInfo(16*GiB,10*GiB)), patch("brain_ssd.chat.runtime.os.cpu_count", return_value=12):
                runtime=LocalChatRuntime(root, profile="equilibrado", core_mode="auto", model_file=model.name)
            try:
                status=runtime.status()
                self.assertEqual(status["core_mode"], "subprocess")
                self.assertEqual(status["auto_mode_reason"], "server_not_installed")
                self.assertEqual(status["threads"], 6)
                self.assertEqual(status["context_size"], 4096)
                self.assertEqual(status["prompt_budget_bytes"], 7600)
                self.assertEqual(status["max_output_tokens"], 160)
                self.assertEqual(runtime.core_backend.backend.threads, 6)
            finally:
                runtime.close()

    def test_auto_reuses_model_if_server_present_and_ram_is_available(self):
        with TemporaryDirectory() as folder:
            root=Path(folder)
            model=root/"models"/"Qwen3-4B-Q4_K_M.gguf"
            model.parent.mkdir(parents=True)
            model.write_bytes(b"GGUF" + b"0" * 128)
            exe=root/"third_party"/"llama.cpp"/"runtime-win-cpu-x64"/"bin"/"llama-server.exe"
            exe.parent.mkdir(parents=True)
            exe.write_bytes(b"MZ")
            with patch("brain_ssd.chat.runtime.windows_memory", return_value=MemoryInfo(16*GiB,10*GiB)), patch("brain_ssd.chat.runtime.os.cpu_count", return_value=12):
                runtime=LocalChatRuntime(root, profile="equilibrado", core_mode="auto", model_file=model.name)
            try:
                self.assertEqual(runtime.core_mode, "persistent")
                self.assertEqual(runtime.status()["auto_mode_reason"], "ram_headroom_sufficient")
                self.assertEqual(runtime.core_backend.context_size, 4096)
                self.assertEqual(runtime.max_output_tokens, 160)
            finally:
                runtime.close()

    def test_chat_engine_passes_runtime_output_budget_to_generation(self):
        class Backend:
            def __init__(self):
                self.last=None
            def generate(self, request):
                self.last=request
                return {"return_code":0,"stdout":"Uma resposta curta.","metrics":{}}
            def close(self):
                pass
        class Runtime:
            def __init__(self):
                self.core_backend=Backend()
                self.max_output_tokens=112
                self.prompt_budget_bytes=5600
            def retrieve(self, query):
                return {"status":"UNAVAILABLE","context":{"text":""},"sources":[],"activated_pages":[]}
            def close(self):
                pass
        runtime=Runtime()
        engine=ChatEngine(lambda:runtime)
        engine.start()
        try:
            reply=engine.ask("Explique o funcionamento dos modelos de linguagem.",[])
            self.assertEqual(reply["answer"],"Uma resposta curta.")
            self.assertEqual(runtime.core_backend.last.max_tokens,112)
        finally:
            engine.close()


if __name__ == "__main__":
    unittest.main()
