from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brain_ssd.backend import GenerationRequest, LlamaCppBackend
from brain_ssd.telemetry import run_measured


class BackendTests(unittest.TestCase):
    def test_llama_backend_is_explicitly_cpu_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "llama-cli"
            model = Path(directory) / "model.gguf"
            executable.touch()
            model.touch()
            command = LlamaCppBackend(executable, model).command(GenerationRequest("test"))
            self.assertIn("--device", command)
            self.assertEqual(command[command.index("--device") + 1], "none")
            self.assertIn("--perf", command)

    def test_measures_streaming_process(self) -> None:
        result = run_measured((sys.executable, str(ROOT / "tests" / "fake_stream_backend.py")), 0.01)
        self.assertEqual(result["return_code"], 0)
        self.assertIn("AZUL", result["stdout"])
        self.assertIsNotNone(result["metrics"]["ttft_ms"])
        self.assertEqual(result["metrics"]["generated_tokens"], 2)
        self.assertEqual(result["metrics"]["tokens_per_second"], 20.0)
        self.assertIsNone(result["metrics"]["active_brain_size_bytes"])


if __name__ == "__main__":
    unittest.main()
