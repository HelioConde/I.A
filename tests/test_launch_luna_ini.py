"""Persistent Luna.ini launch contracts; never starts Qwen, web or Godot."""
from __future__ import annotations

import configparser
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from launch_luna import (  # noqa: E402
    EXAMPLE, build_chat_args, enable_direct_launch, ensure_config, main, read_config, resolve_godot,
)


class LunaIniTests(unittest.TestCase):
    def setUp(self):
        sandbox = tempfile.TemporaryDirectory()
        self.addCleanup(sandbox.cleanup)
        self.temp = Path(sandbox.name)
        self.root = self.temp / "workspace with spaces"
        self.root.mkdir()
        self.other = self.temp / "other"
        self.other.mkdir()
        self.ini = self.temp / "LUNA.ini"
        template = EXAMPLE.read_text(encoding="utf-8")
        self.assertIn("[luna]", template)
        self.assertIn("[copilot]", template)
        self.ini.write_text(template.replace("root = C:/", f"root = {self.root}"),
                            encoding="utf-8")

    def test_defaults_match_prior_user_choices(self):
        conf = read_config(self.ini)
        self.assertEqual(conf.profile, "economia")
        self.assertEqual(conf.roots, (self.root.resolve(),))
        self.assertTrue(conf.screen)
        self.assertTrue(conf.apps)
        self.assertTrue(conf.launch)
        self.assertTrue(conf.launch_without_confirmation)
        self.assertTrue(conf.edit)
        self.assertTrue(conf.godot_validate)
        self.assertEqual(conf.godot_path, r"C:\godot")
        self.assertTrue(conf.web_search)
        self.assertTrue(conf.episodic_memory)

    def test_private_ini_can_enable_direct_launch_without_overwriting_other_settings(self):
        config = self.ini.read_text(encoding="utf-8")
        self.ini.write_text(config.replace("launch_without_confirmation = true",
                                           "launch_without_confirmation = false"),
                            encoding="utf-8")
        before = self.ini.read_text(encoding="utf-8")
        enable_direct_launch(self.ini)
        after = self.ini.read_text(encoding="utf-8")
        self.assertIn("launch_without_confirmation = true", after)
        self.assertIn("godot_path = ", after)
        self.assertEqual(len(after.splitlines()), len(before.splitlines()))
        parsed = read_config(self.ini)
        self.assertTrue(parsed.launch_without_confirmation)
        args, warnings = build_chat_args(parsed)
        self.assertIn("--copilot-launch-direct", args)
        self.assertIsInstance(warnings, list)

    def test_direct_launch_cannot_enable_without_apps_and_launch(self):
        original = self.ini.read_text(encoding="utf-8")
        self.ini.write_text(original.replace("apps = true", "apps = false"),
                            encoding="utf-8")
        with self.assertRaises(ValueError):
            enable_direct_launch(self.ini)

    def test_boolean_flags_can_all_be_disabled_without_extra_permissions(self):
        text = self.ini.read_text(encoding="utf-8")
        for key in ("screen", "apps", "launch", "launch_without_confirmation", "edit", "godot_validate"):
            text = text.replace(key + " = true", key + " = false")
        self.ini.write_text(text, encoding="utf-8")
        conf = read_config(self.ini)
        argv, warning = build_chat_args(conf)
        for flag in ("--copilot-screen", "--copilot-apps", "--copilot-launch",
                     "--copilot-edit", "--copilot-godot-bin"):
            self.assertNotIn(flag, argv)
        self.assertFalse(warning)
        self.assertIn("--copilot-root", argv)

    def test_accept_multiple_valid_roots_and_spaces_as_single_argument(self):
        text = self.ini.read_text(encoding="utf-8")
        text = text.replace("extra_roots =", "extra_roots = " + str(self.other))
        self.ini.write_text(text, encoding="utf-8")
        conf = read_config(self.ini)
        argv, _ = build_chat_args(conf)
        self.assertEqual(len(conf.roots), 2)
        self.assertEqual([argv[i+1] for i, v in enumerate(argv) if v == "--copilot-root"],
                         [str(self.root.resolve()), str(self.other.resolve())])

    def test_godot_directory_resolves_only_a_real_matching_exe(self):
        godot = self.temp / "godot"
        godot.mkdir()
        (godot / "other.exe").write_bytes(b"x")
        (godot / "Godot_v4.5-stable_win64.exe").write_bytes(b"file")
        resolved, message = resolve_godot(str(godot))
        self.assertEqual(resolved, (godot / "Godot_v4.5-stable_win64.exe").resolve())
        self.assertEqual(message, "")

    def test_missing_or_ambiguous_godot_disables_only_validation(self):
        config = read_config(self.ini)
        argv, warnings = build_chat_args(config)
        # The user-specific default C:\godot does not exist in a Linux test.
        # Windows CI may or may not have a C:\godot executable.
        with patch("launch_luna.resolve_godot", return_value=(None, "nao encontrado")):
            argv, warnings = build_chat_args(config)
        self.assertNotIn("--copilot-godot-bin", argv)
        self.assertIn("--copilot-screen", argv)
        self.assertIn("--copilot-edit", argv)
        self.assertTrue(warnings)

        gd = self.temp / "gd"
        gd.mkdir()
        (gd / "godot-a.exe").write_bytes(b"x")
        (gd / "godot-b.exe").write_bytes(b"x")
        found, reason = resolve_godot(str(gd))
        self.assertIsNone(found)
        self.assertIn("Multiplos", reason)

    def test_invalid_root_or_flag_is_reported_instead_of_granting_permission(self):
        body = self.ini.read_text(encoding="utf-8")
        self.ini.write_text(body.replace("root = " + str(self.root), "root = C:/missing_luna_root_987"), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Pasta autorizada nao existe"):
            read_config(self.ini)
        self.ini.write_text(body.replace("screen = true", "screen = maybe"), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "true/false"):
            read_config(self.ini)

    def test_create_once_and_never_overwrite_user_configuration(self):
        target = self.temp / "fresh.ini"
        self.assertTrue(ensure_config(target))
        saved = target.read_bytes()
        self.assertFalse(ensure_config(target))
        self.assertEqual(saved, target.read_bytes())
        target.write_text("[own settings]", encoding="utf-8")
        self.assertFalse(ensure_config(target))
        self.assertEqual(target.read_text(encoding="utf-8"), "[own settings]")

    def test_check_command_exits_without_running_model(self):
        with patch("builtins.print"), patch("launch_luna.subprocess.run") as mocked:
            code = main(["--config", str(self.ini), "--check"])
        self.assertEqual(code, 0)
        mocked.assert_not_called()

    def test_selected_model_is_checked_by_preflight_before_start(self):
        body = self.ini.read_text(encoding="utf-8")
        self.ini.write_text(
            body.replace("model_file =", "model_file = Qwen3-4B-Q8_0.gguf"),
            encoding="utf-8",
        )
        from unittest.mock import MagicMock
        success = MagicMock(returncode=0)
        with patch("launch_luna.subprocess.run", return_value=success) as doctor, \
             patch("launch_luna.subprocess.call", return_value=0) as chat, \
             patch("builtins.print"):
            self.assertEqual(main(["--config", str(self.ini), "--run"]), 0)
        doctor_args = doctor.call_args.args[0]
        chat_args = chat.call_args.args[0]
        self.assertIn("--model-file", doctor_args)
        self.assertEqual(doctor_args[doctor_args.index("--model-file") + 1],
                         "Qwen3-4B-Q8_0.gguf")
        self.assertIn("--model-file", chat_args)
        self.assertEqual(chat_args[chat_args.index("--model-file") + 1],
                         "Qwen3-4B-Q8_0.gguf")

    def test_windows_batch_no_longer_prompts_and_uses_ini_launcher(self):
        batch = (ROOT / "INICIAR-COPILOTO-WINDOWS.bat").read_text(encoding="utf-8")
        self.assertIn("tools\\launch_luna.py", batch)
        self.assertIn("--run", batch)
        self.assertNotIn("choice /c sn", batch.lower())
        self.assertNotIn("set /p", batch.lower())
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("/LUNA.ini", ignore)


if __name__ == "__main__":
    unittest.main()
