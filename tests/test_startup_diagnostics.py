"""No secrets may escape through startup status or terminal-safe hints."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))

from brain_ssd.chat.startup_diagnostics import ChatStartupError, classify_startup_error, RECOVERY
from brain_ssd.chat.server import ChatEngine


class TestSafeStartup(unittest.TestCase):
    def test_code_mapping(self):
        for code in RECOVERY:
            with self.subTest(code=code):
                diagnosis=classify_startup_error(ChatStartupError(code))
                self.assertEqual(diagnosis.code,code)
                self.assertNotIn("C:\\Users",diagnosis.guidance)

    def test_legacy_missing_binary_and_model(self):
        cases=[
            (FileNotFoundError("llama-completion was not found at C:\\Users\\secret"),"CORE_MISSING"),
            (FileNotFoundError("GGUF ausente C:\\Users\\secret"),"MODEL_MISSING"),
            (ValueError("Invalid GGUF C:\\Users\\secret"),"MODEL_INVALID"),
            (PermissionError("C:\\Users\\secret\\runtime.exe"),"RUNTIME_UNREADABLE"),
            (RuntimeError("API_KEY_PRIVATE xyz"),"STARTUP_UNEXPECTED"),
        ]
        for exc,expected in cases:
            with self.subTest(expected=expected):
                got=classify_startup_error(exc)
                self.assertEqual(got.code,expected)
                self.assertNotIn("C:\\Users",got.guidance)
                self.assertNotIn("API_KEY_PRIVATE",got.guidance)

    def test_engine_reports_code_and_not_exception_details(self):
        private="C:\\Users\\private\\SUPER_SECRET_PASS"
        def fail():
            raise FileNotFoundError("llama-completion missing: "+private)
        engine=ChatEngine(fail)
        engine.start()
        try:
            state=engine.status()
            self.assertEqual(state["status"],"error")
            self.assertEqual(state["startup_error_code"],"CORE_MISSING")
            self.assertNotIn(private,str(state))
            self.assertIn("DIAGNOSTICAR",state["error"])
        finally:
            engine.close()

    def test_generic_runtime_does_not_leak(self):
        engine=ChatEngine(lambda: (_ for _ in ()).throw(RuntimeError("secret-TOKEN")))
        engine.start()
        try:
            state=engine.status()
            self.assertEqual(state["startup_error_code"],"STARTUP_UNEXPECTED")
            self.assertNotIn("secret-TOKEN",str(state))
        finally:
            engine.close()

if __name__=="__main__":
    unittest.main()
