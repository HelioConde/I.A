"""Offline tests for the Windows model chooser and pinned auto-installation."""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))
import auto_setup_chat_windows as setup
import doctor_chat


class TestModelCatalog(unittest.TestCase):
    def test_allowlist_contains_three_sha256_verified_ggufs(self):
        self.assertEqual(set(setup.MODELS), {"0.6b", "1.7b", "4b"})
        names = set()
        for model in setup.MODELS.values():
            self.assertTrue(model.url.startswith("https://huggingface.co/"))
            self.assertRegex(model.sha256, r"^[a-f0-9]{64}$")
            self.assertNotIn("..", model.filename)
            self.assertRegex(model.filename, r"^[A-Za-z0-9_.+-]+\.gguf$")
            self.assertGreater(model.estimated_bytes, 0)
            self.assertGreater(model.max_bytes, model.min_bytes)
            self.assertNotIn(model.filename, names)
            names.add(model.filename)

    def test_existing_verified_model_is_reused_without_downloading(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            filedata = b"GGUF" + b"a" * 200
            spec = setup.ModelSpec(
                "test", "Synthetic", "model.gguf", "https://huggingface.co/",
                hashlib.sha256(filedata).hexdigest(), 2000, 8, len(filedata), 1,
            )
            target = setup.model_destination(root, spec)
            target.parent.mkdir()
            target.write_bytes(filedata)
            with patch.object(setup, "download_verified") as download:
                path, created = setup.ensure_model(root, spec)
            self.assertFalse(created)
            self.assertEqual(path, target)
            download.assert_not_called()

    def test_corrupt_download_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bad = root / "models" / "model.gguf"
            bad.parent.mkdir()
            bad.write_bytes(b"GGUF" + b"q" * 150)
            spec = setup.ModelSpec(
                "test", "Synthetic", bad.name, "https://huggingface.co/",
                "0" * 64, 500, 8, 200, 1,
            )
            with patch.object(setup, "download_verified") as download:
                with self.assertRaises(FileExistsError):
                    setup.ensure_model(root, spec)
            download.assert_not_called()
            self.assertEqual(bad.read_bytes(), b"GGUF" + b"q" * 150)

    def test_missing_model_is_downloaded_and_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = b"GGUF" + b"x" * 200
            spec = setup.ModelSpec(
                "test", "Synthetic", "model.gguf", "https://huggingface.co/",
                hashlib.sha256(data).hexdigest(), 1000, 8, len(data), 1,
            )
            def fake_download(url, dest, *, sha256, max_size, exact_size):
                self.assertEqual(sha256, spec.sha256)
                self.assertEqual(max_size, spec.max_bytes)
                self.assertIsNone(exact_size)
                dest.write_bytes(data)
            with patch.object(setup, "download_verified", side_effect=fake_download) as download:
                path, created = setup.ensure_model(root, spec)
            self.assertTrue(created)
            self.assertEqual(path.read_bytes(), data)
            download.assert_called_once()
            with patch.object(setup, "download_verified") as again:
                path2, created2 = setup.ensure_model(root, spec)
            self.assertFalse(created2)
            self.assertEqual(path, path2)
            again.assert_not_called()

    def test_existing_private_notes_and_old_model_are_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = root / "models" / "Qwen3-0.6B-Q8_0.gguf"
            old.parent.mkdir(parents=True)
            old.write_bytes(b"PRIVATE-OLD-MODEL")
            memory = root / "private-notes.sqlite3"
            memory.write_bytes(b"PRIVATE-MEMORY")
            spec = setup.ModelSpec(
                "test", "Synthetic", "next.gguf", "https://huggingface.co/",
                hashlib.sha256(b"GGUF"+b"b"*50).hexdigest(), 1000, 8, 54, 1,
            )
            with patch.object(setup, "download_verified",
                              side_effect=lambda _url, dest, **_kw: dest.write_bytes(b"GGUF"+b"b"*50)):
                setup.ensure_model(root, spec)
            self.assertEqual(old.read_bytes(), b"PRIVATE-OLD-MODEL")
            self.assertEqual(memory.read_bytes(), b"PRIVATE-MEMORY")

    def test_start_chat_selects_requested_model_and_web_only_with_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = setup.MODELS["4b"]
            with patch.object(setup.subprocess, "call", return_value=0) as invoke:
                self.assertEqual(setup.start_chat(root, spec, web=False, profile="equilibrado"), 0)
                cmd = invoke.call_args.args[0]
                self.assertIn("--model-file", cmd)
                self.assertEqual(cmd[cmd.index("--model-file")+1], spec.filename)
                self.assertNotIn("--web-search", cmd)
                self.assertIn("--episodic-memory", cmd)
                setup.start_chat(root, spec, web=True, profile="equilibrado")
                cmd = invoke.call_args.args[0]
                self.assertIn("--web-search", cmd)
                self.assertIn("wikipedia", cmd)

    def test_selected_model_doctor_accepts_gguf_inside_models_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            local = root / "models" / "Qwen3-4B-Q4_K_M.gguf"
            local.parent.mkdir()
            with local.open("wb") as fh:
                fh.write(b"GGUF")
                fh.truncate(64 * 1024 * 1024 + 1)
            report = doctor_chat.inspect_installation(root, "economia", False, model_file=local.name)
            self.assertTrue(report["required"]["model_gguf_valid_header"])
            self.assertTrue(report["required"]["model_plausible_size"])
            self.assertEqual(report["model"]["path"], str(local))
            for name in ("../other.gguf", r"C:\private.gguf", "folder/model.gguf"):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    doctor_chat.inspect_installation(root, model_file=name)


if __name__ == "__main__":
    unittest.main()
