"""Offline regression suite for Qwen3-4B installer/selector. No network or inference."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from launch_luna import read_config
from test_luna_models import CANDIDATE, CANDIDATE_SHA256
import usar_qwen4b_luna as app


class LunaModelActivationTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name)
        self.models = self.home / "models"
        self.models.mkdir()
        self.ini = self.home / "LUNA.ini"
        self.ini.write_text(
            "[luna]\n"
            "profile = economia\ncore_mode =\nmodel_file =\n"
            "port = 8766\nopen_browser = true\nepisodic_memory = true\n"
            "cognitive_shadow = true\nmemory_aliases = false\nweb_search = true\n"
            "web_provider = auto\n"
            "[copilot]\n"
            f"root = {self.home}\nextra_roots =\nscreen = true\napps = true\n"
            "launch = false\nedit = true\ngodot_validate = false\n"
            "godot_path =\n",
            encoding="utf-8",
        )

    def add_fixture_model(self):
        destination = self.models / CANDIDATE
        destination.write_bytes(b"GGUF" + b"model-test-bytes")
        return destination

    def test_missing_model_does_not_change_ini_or_download(self):
        before = self.ini.read_bytes()
        with patch.object(app, "download_candidate") as dl:
            with self.assertRaisesRegex(ValueError, "ausente"):
                app.install_activate(self.ini, download=False, models=self.models)
            dl.assert_not_called()
        self.assertEqual(self.ini.read_bytes(), before)

    def test_invalid_download_never_changes_ini(self):
        self.add_fixture_model()
        before = self.ini.read_bytes()
        with self.assertRaisesRegex(ValueError, "incompleto"):
            app.install_activate(self.ini, download=True, models=self.models)
        self.assertEqual(self.ini.read_bytes(), before)

    def test_download_optin_and_activation_preserve_permissions(self):
        calls = []
        def fake_download(models):
            calls.append("download")
            self.add_fixture_model()
            return {"downloaded": True}

        def fake_doctor(root, profile, probe, model_file):
            calls.append("preflight")
            self.assertEqual(profile, "equilibrado")
            self.assertTrue(probe)
            self.assertEqual(model_file, CANDIDATE)
            return {"ready_for_test": True}

        with patch.object(app, "download_candidate", side_effect=fake_download), \
             patch.object(app, "MIN_4B", 1), \
             patch.object(app, "sha256_file", return_value=CANDIDATE_SHA256), \
             patch.object(app, "inspect_installation", side_effect=fake_doctor):
            app.install_activate(self.ini, download=True, models=self.models)
        self.assertEqual(calls, ["download", "preflight"])
        config = read_config(self.ini)
        self.assertEqual(config.model_file, CANDIDATE)
        self.assertEqual(config.profile, "equilibrado")
        self.assertEqual(config.core_mode, "auto")
        self.assertTrue(config.screen)
        self.assertFalse(config.launch)
        self.assertEqual(config.roots, (self.home.resolve(),))

    def test_incorrect_hash_blocks_selection_without_network(self):
        self.add_fixture_model()
        before = self.ini.read_bytes()
        with patch.object(app, "MIN_4B", 1), \
             patch.object(app, "sha256_file", return_value="0" * 64):
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                app.install_activate(self.ini, download=True, models=self.models)
        self.assertEqual(self.ini.read_bytes(), before)

    def test_unavailable_runtime_blocks_selection(self):
        self.add_fixture_model()
        before = self.ini.read_bytes()
        with patch.object(app, "MIN_4B", 1), \
             patch.object(app, "sha256_file", return_value=CANDIDATE_SHA256), \
             patch.object(app, "inspect_installation", return_value={
                 "ready_for_test": False, "recommendations": ["CPU runtime missing"],
             }):
            with self.assertRaisesRegex(ValueError, "CPU runtime missing"):
                app.install_activate(self.ini, download=False, models=self.models)
        self.assertEqual(self.ini.read_bytes(), before)

    def test_rollback_preserves_paths_and_4b_gguf(self):
        candidate = self.add_fixture_model()
        app.select_ini_model(self.ini, large=True)
        self.assertEqual(read_config(self.ini).model_file, CANDIDATE)
        app.select_ini_model(self.ini, large=False)
        restored = read_config(self.ini)
        self.assertEqual(restored.model_file, "")
        self.assertEqual(restored.profile, "economia")
        self.assertEqual(restored.core_mode, "")
        self.assertTrue(restored.screen)
        self.assertTrue(candidate.is_file())

    def test_original_ini_comments_are_preserved(self):
        original = self.ini.read_text(encoding="utf-8")
        self.ini.write_text("; NOTA PESSOAL - nao apagar\n" + original, encoding="utf-8")
        app.select_ini_model(self.ini, large=True)
        self.assertTrue(self.ini.read_text(encoding="utf-8").startswith("; NOTA PESSOAL"))
        self.assertIn("root = " + str(self.home), self.ini.read_text(encoding="utf-8"))

    def test_status_never_downloads_or_executes_model(self):
        with patch.object(app, "download_candidate") as dl, \
             patch.object(app, "inspect_installation") as dr:
            self.assertEqual(app.main(["--config", str(self.ini), "--status"]), 0)
            dl.assert_not_called()
            dr.assert_not_called()

    def test_quick_use_switch_requires_existing_verified_model_and_never_downloads(self):
        candidate = self.add_fixture_model()
        calls = []
        def preflight(root, profile, probe, model_file):
            calls.append(("preflight", profile, model_file))
            return {"ready_for_test": True}
        with patch.object(app, "download_candidate") as download, \
             patch.object(app, "MIN_4B", 1), \
             patch.object(app, "sha256_file", return_value=CANDIDATE_SHA256), \
             patch.object(app, "inspect_installation", side_effect=preflight):
            app.install_activate(self.ini, download=False, models=self.models)
            download.assert_not_called()
        self.assertTrue(candidate.is_file())
        self.assertEqual(read_config(self.ini).model_file, CANDIDATE)
        self.assertEqual(calls, [("preflight", "equilibrado", CANDIDATE)])

    def test_quick_use_batch_never_downloads_without_explicit_installer(self):
        path = ROOT / "USAR-QWEN4B-LUNA.bat"
        batch = path.read_text(encoding="utf-8")
        self.assertIn('cd /d "%~dp0"', batch)
        self.assertIn('"tools\\usar_qwen4b_luna.py" --activate', batch)
        self.assertIn('INICIAR-COPILOTO-WINDOWS.bat', batch)
        self.assertNotIn('--install-activate', batch)
        self.assertNotIn('"tools\\auto_setup_chat_windows.py"', batch)
        self.assertIn('if errorlevel 1', batch)
        self.assertNotIn('choice /C 123', batch)

    def test_batch_installs_only_with_explicit_command(self):
        path = ROOT / "INSTALAR-QWEN4B-LUNA.bat"
        batch = path.read_text(encoding="utf-8")
        self.assertIn("usar_qwen4b_luna.py", batch)
        self.assertIn("--install-activate", batch)
        self.assertIn("INICIAR-COPILOTO-WINDOWS.bat", batch)
        self.assertFalse("--restore-06b" in batch.split("--install-activate")[0])


if __name__ == "__main__":
    unittest.main()
