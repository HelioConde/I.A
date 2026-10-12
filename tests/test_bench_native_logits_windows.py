"""Offline contract checks for the pinned llama C API logits probe."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from bench_native_logits_windows import build_commands, compare, probe_command


def fake(mode="mmap", *, tokens=None, first=2.5, checksum="deadbeef") -> dict:
    return {
        "type": "native_llama_logits_probe", "status": "measured",
        "load_mode": mode, "context": 512, "threads": 4,
        "lazy_mode": "off",
        "predict_limit": 16, "sampling": "greedy", "vocab_count": 300,
        "prompt_top8_logits": [
            {"token": 3, "value": first}, {"token": 12, "value": 1.0}
        ],
        "tokens": [3, 12, 7] if tokens is None else tokens,
        "prompt_logits_fnv64": checksum,
    }


class NativeLogitsBenchTests(unittest.TestCase):
    def test_identical_modes_pass(self):
        result = compare(fake(), fake("none"))
        self.assertEqual(result["status"], "consistent")
        self.assertTrue(result["greedy_token_ids_equal"])
        self.assertTrue(result["first_prompt_logits_bitwise_checksum_equal"])

    def test_small_numeric_drift_does_not_claim_bitwise_identity(self):
        result = compare(fake(), fake("none", first=2.500001, checksum="different"))
        self.assertEqual(result["status"], "consistent")
        self.assertFalse(result["first_prompt_logits_bitwise_checksum_equal"])
        self.assertTrue(result["top8_logits_within_absolute_tolerance"])

    def test_token_divergence_is_detected(self):
        result = compare(fake(), fake("none", tokens=[3, 12, 8]))
        self.assertEqual(result["status"], "diverged")
        self.assertFalse(result["greedy_token_ids_equal"])

    def test_top_logits_drift_is_detected(self):
        result = compare(fake(), fake("none", first=2.6))
        self.assertEqual(result["status"], "diverged")
        self.assertFalse(result["top8_logits_within_absolute_tolerance"])

    def test_invalid_or_mismatched_configs_are_rejected(self):
        altered = fake()
        altered["context"] = 1024
        with self.assertRaises(ValueError):
            compare(fake(), altered)
        altered = fake()
        altered["lazy_mode"] = "on"
        with self.assertRaises(ValueError):
            compare(fake(), altered)
        altered = fake()
        altered["status"] = "not_implemented"
        with self.assertRaises(ValueError):
            compare(fake(), altered)
        altered = fake()
        altered["prompt_top8_logits"] = []
        with self.assertRaises(ValueError):
            compare(fake(), altered)

    def test_probe_command_is_explicit_cpu_runtime(self):
        cmd = probe_command(Path("probe.exe"), Path("Qwen3-0.6B-Q8_0.gguf"),
                            mode="mmap", prompt="Uma pergunta", context=512,
                            threads=4, predict=16)
        self.assertIn("Qwen3-0.6B-Q8_0.gguf", cmd)
        self.assertIn("mmap", cmd)
        self.assertIn("--lazy-mode", cmd)
        self.assertIn("off", cmd)
        self.assertEqual(cmd[0], "probe.exe")
        with self.assertRaises(ValueError):
            probe_command(Path("probe.exe"), Path("weights.gguf"),
                          mode="mlock", prompt="teste", context=512, threads=4, predict=16)
        with self.assertRaises(ValueError):
            probe_command(Path("probe.exe"), Path("weights.gguf"),
                          mode="mmap", prompt="teste", context=512, threads=4, predict=16,
                          lazy_mode="unsupported")

    def test_isolated_build_does_not_touch_existing_runtime(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "upstream"
            build = Path(temp) / "probe"
            config, make = build_commands(source, build)
            self.assertIn("-DLLAMA_SOURCE_DIR=" + str(source), config)
            self.assertIn("brainssd-native-logits", make)
            self.assertNotIn("INICIAR-CHAT-WINDOWS.bat", " ".join(config + make))


if __name__ == "__main__":
    unittest.main()
