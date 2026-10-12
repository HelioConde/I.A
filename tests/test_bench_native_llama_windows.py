from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from bench_native_llama_windows import build_report, native_command


class NativeLlamaBenchTests(unittest.TestCase):
    def test_command_is_deterministic_and_never_selects_a_smaller_model(self):
        command = native_command(Path("llama-cli.exe"), Path("Qwen3-0.6B-Q8_0.gguf"), "fixed", load_mode="mmap",
                                 threads=4, predict=16, seed=1234, context_size=512)
        self.assertIn("--load-mode", command)
        self.assertIn("mmap", command)
        self.assertIn("--temp", command)
        self.assertIn("0", command)
        self.assertIn("Qwen3-0.6B-Q8_0.gguf", command)

    def test_report_does_not_call_upstream_mmap_brain_ssd_loader(self):
        root = Path(__file__).resolve()
        conventional = {"status": "measured", "stdout_sha256": "a"}
        report = build_report(conventional, None, cli=root, model=root, prompt="fixed", seed=1, threads=1,
                              predict=1, context_size=512)
        self.assertEqual(report["brain_ssd_experimental"]["status"], "not_implemented")
        self.assertIsNone(report["integrity"]["upstream_token_output_equal"])


if __name__ == "__main__":
    unittest.main()
