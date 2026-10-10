"""Installation doctor tests; no real GGUF or llama.cpp required."""
from __future__ import annotations
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from doctor_chat import inspect_installation


class TestInstallationDoctor(unittest.TestCase):
    def test_missing_files_and_optional_ssd(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = inspect_installation(root)
            self.assertFalse(first["ready_for_test"])
            self.assertFalse(first["optional_ssd"]["available"])
            self.assertTrue(first["recommendations"])
            model = root / "models" / "Qwen3-0.6B-Q8_0.gguf"
            model.parent.mkdir(parents=True)
            model.write_bytes(b"GGUF" + b"\0" * 2048)
            exe = root / "third_party/llama.cpp/build-win/bin/llama-completion.exe"
            exe.parent.mkdir(parents=True)
            exe.write_bytes(b"MZ")
            # The resolver uses a suffix only on native Windows.
            exe.with_suffix("").write_bytes(b"ELF")
            too_small = inspect_installation(root)
            self.assertFalse(too_small["ready_for_test"])
            self.assertFalse(too_small["required"]["model_plausible_size"])
            with patch("doctor_chat.MIN_PLAUSIBLE_GGUF_BYTES", 1024):
                second = inspect_installation(root)
            self.assertTrue(second["ready_for_test"])
            self.assertFalse(second["optional_ssd"]["available"])
            self.assertEqual(second["status"], "READY_FOR_REAL_INFERENCE_TEST")


if __name__ == "__main__":
    unittest.main()
