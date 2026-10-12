"""Offline checks: no Git clone, network, compiler or model is started."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from prepare_native_llama_windows import (  # noqa: E402
    DEFAULT_REVISION, commands, inspect, main, valid_revision,
)


class PinnedNativeBuildTests(unittest.TestCase):
    def test_full_git_revision_is_required(self):
        self.assertEqual(valid_revision(DEFAULT_REVISION), DEFAULT_REVISION)
        for value in ("main", "972b5fc", "g" * 40):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    valid_revision(value)

    def test_commands_use_cpu_only_config_and_no_shell(self):
        ops = commands(Path("C:/Temp/native-llama"), DEFAULT_REVISION)
        self.assertEqual(ops["clone"][:3], ["git", "clone", "--filter=blob:none"])
        self.assertEqual(ops["checkout"][-1], DEFAULT_REVISION)
        self.assertIn("-DGGML_CUDA=OFF", ops["configure"])
        self.assertIn("-DGGML_VULKAN=OFF", ops["configure"])

    def test_default_is_read_only_and_creates_no_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "not-yet-present"
            with patch("builtins.print"):
                self.assertEqual(main(["--source-dir", str(target)]), 0)
            self.assertFalse(target.exists())

    def test_existing_unrelated_directory_must_not_be_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "existing"
            target.mkdir()
            with self.assertRaisesRegex(RuntimeError, "not a Git checkout"):
                inspect(target, DEFAULT_REVISION)

    def test_incorrect_pinned_checkout_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "source"
            (target / ".git").mkdir(parents=True)
            (target / "CMakeLists.txt").write_text("project(test)", encoding="utf-8")
            class GitResult:
                stdout = "0" * 40 + "\n"
            with patch("prepare_native_llama_windows.invoke", return_value=GitResult()):
                with self.assertRaisesRegex(RuntimeError, "differs"):
                    inspect(target, DEFAULT_REVISION)

    def test_no_windows_native_build_outside_windows(self):
        if sys.platform == "win32":
            self.skipTest("Windows deliberately permits native build with explicit flags.")
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "source"
            with patch("builtins.print"):
                self.assertEqual(main(["--fetch", "--build",
                                       "--source-dir", str(target)]), 2)
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
