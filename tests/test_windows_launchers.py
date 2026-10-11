"""Ensure Windows shortcuts work regardless of the current shell directory.

Static lint only; the real model/DLL installation still needs physical Windows.
"""
from pathlib import Path
import re
import unittest
import json
import os
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=[
    "DIAGNOSTICAR-CHAT-WINDOWS.bat",
    "INICIAR-CHAT-WINDOWS.bat",
    "INICIAR-CHAT-MEMORIA-WINDOWS.bat",
    "INICIAR-CHAT-WEB-WINDOWS.bat",
]

class TestBatchLaunchers(unittest.TestCase):
    def test_resolve_project_directory_and_early_file_check(self):
        for name in SCRIPTS:
            with self.subTest(name=name):
                text=(ROOT/name).read_text(encoding="utf-8")
                self.assertRegex(text,r'cd /d "%~dp0"')
                self.assertIn('if not exist "tools\\doctor_chat.py"',text)
                self.assertIn('"tools\\doctor_chat.py" --profile economia --probe',text)

    def test_web_launcher_requires_explicit_search_opt_in(self):
        text=(ROOT/"INICIAR-CHAT-WEB-WINDOWS.bat").read_text(encoding="utf-8")
        self.assertIn("--web-search --web-provider auto", text)
        self.assertIn("--episodic-memory", text)

    def test_prefer_supported_python_but_allow_installed_version(self):
        for name in SCRIPTS:
            with self.subTest(name=name):
                text=(ROOT/name).read_text(encoding="utf-8")
                self.assertIn('".venv\\Scripts\\python.exe"',text)
                self.assertIn('py -3.11 --version',text)
                self.assertIn('set "PYTHON_CMD=py -3"',text)
                self.assertIn('set "PYTHON_CMD=python"',text)
                self.assertIn('%PYTHON_CMD% --version',text)
                self.assertNotIn('py -3 "tools\\doctor_chat.py"',text)

    def test_all_in_one_launcher_offers_model_selection_and_installs_missing(self):
        text=(ROOT/"INICIAR-BRAIN-SSD.bat").read_text(encoding="utf-8")
        self.assertIn('cd /d "%~dp0"',text)
        self.assertIn('"tools\\auto_setup_chat_windows.py"',text)
        self.assertIn("choice /C 123",text)
        self.assertIn("set \"MODEL=0.6b\"",text)
        self.assertIn("set \"MODEL=1.7b\"",text)
        self.assertIn("set \"MODEL=4b\"",text)
        self.assertIn("winget install --id Python.Python.3.11",text)
        self.assertIn("--profile %PROFILE%",text)
        # The main launcher now always exposes the complete feature set.
        # Only the actual external query still needs per-question consent.
        self.assertIn(' --web',text)
        self.assertNotIn("choice /C SN /N /M \"Pesquisa opcional",text)
        self.assertNotIn("%WEB%",text)

    def test_every_legacy_chat_launcher_opens_full_features(self):
        for name in (
            "INICIAR-CHAT-WINDOWS.bat",
            "INICIAR-CHAT-MEMORIA-WINDOWS.bat",
            "INICIAR-CHAT-WEB-WINDOWS.bat",
        ):
            with self.subTest(launcher=name):
                content=(ROOT/name).read_text(encoding="utf-8")
                self.assertIn("--episodic-memory",content)
                self.assertIn("--web-search --web-provider auto",content)
                self.assertIn("--cognitive-shadow",content)

    def test_chat_start_is_conditional_on_preflight(self):
        for name in SCRIPTS[1:]:
            with self.subTest(name=name):
                text=(ROOT/name).read_text(encoding="utf-8")
                self.assertIn('if errorlevel 1 goto :not_ready',text)
                self.assertIn('"tools\\run_chat.py" --profile economia',text)
                self.assertLess(text.index('"tools\\doctor_chat.py" --profile economia --probe'),
                                text.index('"tools\\run_chat.py" --profile economia'))

    def test_copilot_launcher_preserves_root_drive_path_argv(self):
        """Validate actual Windows command-line parsing, including trailing backslash."""
        launcher=(ROOT/"INICIAR-COPILOTO-WINDOWS.bat").read_text(encoding="utf-8")
        start=launcher.index('set "COPILOT_ROOT_ARG=%COPILOT_ROOT%"')
        end=launcher.index(":ask_screen",start)
        normalization=launcher[start:end]
        # This is a single literal backslash, not two.
        self.assertIn('if "%COPILOT_ROOT:~-1%"=="\\"
'.strip(),normalization)
        self.assertIn('--copilot-root "%COPILOT_ROOT_ARG%" %COPILOT_SCREEN%',launcher)
        if os.name != "nt":
            return
        with tempfile.TemporaryDirectory() as tmp:
            batch=Path(tmp)/"probe.cmd"
            batch.write_text(
                '@echo off\nsetlocal EnableExtensions\n'
                'set "COPILOT_ROOT=%TEST_COPILOT_ROOT%"\n'
                + normalization
                + '\n"%TEST_PYTHON%" -c "import sys,json;print(json.dumps(sys.argv[1:]))" '
                  '"%COPILOT_ROOT_ARG%" --copilot-screen\n',
                encoding="utf-8",
            )
            cases=[
                ("C:\\", "C:\\."),
                ("C:\\Pasta com espacos\\", "C:\\Pasta com espacos\\."),
                ("C:\\Pasta com espacos", "C:\\Pasta com espacos"),
            ]
            for root, expected in cases:
                with self.subTest(root=root):
                    env=dict(os.environ,TEST_COPILOT_ROOT=root,TEST_PYTHON=sys.executable)
                    run=subprocess.run(["cmd.exe","/d","/c",str(batch)],env=env,
                                       capture_output=True,text=True,timeout=15)
                    self.assertEqual(run.returncode,0,msg=run.stderr+run.stdout)
                    args=json.loads(run.stdout.strip().splitlines()[-1])
                    self.assertEqual(args,[expected,"--copilot-screen"])

if __name__=="__main__":
    unittest.main()
