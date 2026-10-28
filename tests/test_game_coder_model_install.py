"""No-download checks for the pinned optional Qwen3-4B GGUF installer."""
from __future__ import annotations
import hashlib
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
TOOLS=ROOT/"tools"
sys.path.insert(0,str(TOOLS))
from install_game_coder_model import MODEL_BYTES,MODEL_SHA256,MODEL_FILENAME,MODEL_REVISION,MODEL_URL
from install_windows_chat import verified_file


class QwenCoderInstallerTests(unittest.TestCase):
    def test_pinned_official_model_metadata(self):
        self.assertEqual(MODEL_FILENAME,"Qwen3-4B-Q4_K_M.gguf")
        self.assertEqual(MODEL_BYTES,2497280256)
        self.assertEqual(len(MODEL_SHA256),64)
        int(MODEL_SHA256,16)
        self.assertEqual(len(MODEL_REVISION),40)
        int(MODEL_REVISION,16)
        self.assertTrue(MODEL_URL.startswith("https://huggingface.co/Qwen/Qwen3-4B-GGUF/resolve/"))
        self.assertIn(MODEL_REVISION,MODEL_URL)
        self.assertTrue(MODEL_URL.endswith(MODEL_FILENAME))

    def test_verified_file_rejects_wrong_bytes_and_hash(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"fake.gguf"
            path.write_bytes(b"GGUFinvalid")
            self.assertFalse(verified_file(path,sha256=MODEL_SHA256,exact_size=MODEL_BYTES))
            self.assertFalse(verified_file(path,sha256=MODEL_SHA256,exact_size=11))
            self.assertTrue(verified_file(path,sha256=hashlib.sha256(b"GGUFinvalid").hexdigest(),exact_size=11))

    def test_missing_file_never_counts_as_model(self):
        self.assertFalse(verified_file(ROOT/"models"/"nonexistent-4b-benchmark.gguf",sha256=MODEL_SHA256,exact_size=MODEL_BYTES))


if __name__=="__main__":
    unittest.main()
