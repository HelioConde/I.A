"""Ensure Windows shortcuts work regardless of the current shell directory.

Static lint only; the real model/DLL installation still needs physical Windows.
"""
from pathlib import Path
import re
import unittest

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
        self.assertIn("--web-search --web-provider wikipedia", text)
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

    def test_chat_start_is_conditional_on_preflight(self):
        for name in SCRIPTS[1:]:
            with self.subTest(name=name):
                text=(ROOT/name).read_text(encoding="utf-8")
                self.assertIn('if errorlevel 1 goto :not_ready',text)
                self.assertIn('"tools\\run_chat.py" --profile economia',text)
                self.assertLess(text.index('"tools\\doctor_chat.py" --profile economia --probe'),
                                text.index('"tools\\run_chat.py" --profile economia'))

if __name__=="__main__":
    unittest.main()
