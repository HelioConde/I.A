"""Offline safety tests for optional official Qwen3-4B Q8_0 model trial."""
from __future__ import annotations

import hashlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import test_luna_models as model_trial
from brain_ssd.chat.performance import MemoryInfo


class QwenModelTrialTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.models = self.root / "models"
        self.models.mkdir()

    def test_default_status_does_not_download_or_execute_model(self):
        with patch.object(model_trial, "download_candidate") as download, \
             patch.object(model_trial, "run_comparison") as compare:
            self.assertEqual(model_trial.main([]), 0)
        download.assert_not_called()
        compare.assert_not_called()

    def test_local_status_never_overwrites_user_gguf(self):
        baseline = self.models / model_trial.BASELINE
        candidate = self.models / model_trial.CANDIDATE
        baseline.write_bytes(b"GGUF")
        candidate.write_bytes(b"GGUFqwen")
        before = candidate.read_bytes()
        status = model_trial.local_model_status(self.models)
        self.assertTrue(status[model_trial.CANDIDATE]["present"])
        self.assertTrue(status[model_trial.CANDIDATE]["header_gguf"])
        self.assertFalse(status[model_trial.CANDIDATE]["plausible_size"])
        self.assertEqual(candidate.read_bytes(), before)

    def test_opt_in_download_checks_sha_and_uses_atomic_promotion(self):
        fake = b"GGUF" + b"fake Qwen3-4B content for unit test"
        class Response(io.BytesIO):
            pass
        def fake_open(url: str, timeout: int):
            self.assertTrue(url.startswith("https://huggingface.co/Qwen/"))
            self.assertEqual(timeout, 120)
            return Response(fake)
        with patch.object(model_trial, "MIN_4B", 8), \
             patch.object(model_trial, "CANDIDATE_SHA256", hashlib.sha256(fake).hexdigest()), \
             patch.object(model_trial, "MIN_FREE_DISK", 0):
            report = model_trial.download_candidate(self.models, opener=fake_open)
        self.assertTrue(report["downloaded"])
        self.assertEqual((self.models / model_trial.CANDIDATE).read_bytes(), fake)
        self.assertFalse((self.models / (model_trial.CANDIDATE + ".download-incomplete")).exists())

    def test_failed_hash_discards_partial_and_preserves_baseline(self):
        baseline = self.models / model_trial.BASELINE
        baseline.write_bytes(b"GGUF keep me")
        with patch.object(model_trial, "MIN_4B", 8), \
             patch.object(model_trial, "MIN_FREE_DISK", 0):
            with self.assertRaisesRegex(ValueError, "SHA256"):
                model_trial.download_candidate(
                    self.models, opener=lambda url, timeout: io.BytesIO(b"GGUF bogus bytes"))
        self.assertFalse((self.models / model_trial.CANDIDATE).exists())
        self.assertFalse((self.models / (model_trial.CANDIDATE + ".download-incomplete")).exists())
        self.assertEqual(baseline.read_bytes(), b"GGUF keep me")

    def test_download_refuses_existing_model(self):
        path = self.models / model_trial.CANDIDATE
        path.write_bytes(b"existing model")
        with self.assertRaises(FileExistsError):
            model_trial.download_candidate(self.models, opener=lambda *a, **kw: None)
        self.assertEqual(path.read_bytes(), b"existing model")

    def test_4b_must_match_official_sha_and_available_memory(self):
        checks = {name: {"present": True, "header_gguf": True, "plausible_size": True}
                  for name in (model_trial.BASELINE, model_trial.CANDIDATE)}
        with patch.object(model_trial, "local_model_status", return_value=checks), \
             patch.object(model_trial, "sha256_file", return_value=model_trial.CANDIDATE_SHA256):
            with self.assertRaisesRegex(ValueError, "RAM disponível"):
                model_trial.check_comparison_prerequisites(
                    self.models, memory_probe=lambda: MemoryInfo(16*2**30, 3*2**30))
            result = model_trial.check_comparison_prerequisites(
                self.models, memory_probe=lambda: MemoryInfo(16*2**30, 3*2**30),
                unsafe_low_ram=True)
            self.assertTrue(result["ram_safety_override"])
        with patch.object(model_trial, "local_model_status", return_value=checks), \
             patch.object(model_trial, "sha256_file", return_value="0"*64):
            with self.assertRaisesRegex(ValueError, "SHA256"):
                model_trial.check_comparison_prerequisites(
                    self.models, memory_probe=lambda: MemoryInfo(16*2**30, 12*2**30))

    def test_default_prompt_suite_is_safe_and_explicitly_reviewed(self):
        self.assertEqual(len(model_trial.TEST_CASES), 4)
        self.assertEqual(len({c[0] for c in model_trial.TEST_CASES}), 4)
        self.assertTrue(all(len(q) < 400 for _, q in model_trial.TEST_CASES))
        self.assertNotIn("Q4", model_trial.CANDIDATE)
        self.assertEqual(len(model_trial.CANDIDATE_SHA256), 64)


if __name__ == "__main__":
    unittest.main()
