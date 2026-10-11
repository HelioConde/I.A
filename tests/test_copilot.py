"""Regressão dos recursos locais e da pesquisa Google (sem rede ou GGUF)."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brain_ssd.chat.copilot import LocalCopilot, CopilotPermissionError
from brain_ssd.chat.server import ChatEngine, create_chat_server
from brain_ssd.chat.web_search import WebSearchService


class TestCopilot(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "Drive root is Windows-specific")
    def test_drive_root_is_valid_when_explicitly_authorized(self):
        drive = Path(os.environ.get("SystemDrive", "C:") + "\\\\.")
        copilot = LocalCopilot([drive], screen=True)
        self.assertTrue(copilot.status()["files_enabled"])
        self.assertTrue(copilot.status()["screen_enabled"])

    def test_no_access_by_default(self):
        copilot = LocalCopilot()
        self.assertFalse(copilot.status()["enabled"])
        with self.assertRaises(CopilotPermissionError):
            copilot.list_directory(".")
        with self.assertRaises(CopilotPermissionError):
            copilot.capture_screen()

    def test_read_only_allowed_root_and_size_limit(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as base:
            root = Path(base)
            (root / "codigo.py").write_text("print('ok')", encoding="utf-8")
            (root / "grande.txt").write_text("x" * 131073, encoding="utf-8")
            (root / ".env").write_text("SECRET=none", encoding="utf-8")
            (root / "private.key").write_text("secret", encoding="utf-8")
            copilot = LocalCopilot([root])
            contents = copilot.read_file(str(root / "codigo.py"))
            self.assertEqual(contents["content"], "print('ok')")
            listing = copilot.list_directory(str(root))["entries"]
            self.assertIn("codigo.py", [item["name"] for item in listing])
            self.assertNotIn(".env", [item["name"] for item in listing])
            with self.assertRaises(CopilotPermissionError):
                copilot.read_file(str(root / ".env"))
            with self.assertRaises(CopilotPermissionError):
                copilot.read_file(str(root / "private.key"))
            with self.assertRaises(CopilotPermissionError):
                copilot.read_file(str(root / "grande.txt"))
            with self.assertRaises(CopilotPermissionError):
                copilot.read_file(str(root.parent))
            self.assertTrue(copilot.system_info()["cpu_threads"] is None or
                            copilot.system_info()["cpu_threads"] > 0)

    def test_symlink_outside_root_is_denied(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as base:
            base = Path(base)
            root = base / "allowed"
            root.mkdir()
            outside = base / "outside.txt"
            outside.write_text("no", encoding="utf-8")
            try:
                (root / "link.txt").symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest("Sistema bloqueia a criação de symlink")
            copilot = LocalCopilot([root])
            with self.assertRaises(CopilotPermissionError):
                copilot.read_file(str(root / "link.txt"))
            self.assertFalse(any(e["name"] == "link.txt"
                                 for e in copilot.list_directory(str(root))["entries"]))

    def test_screen_requires_permission_and_rejects_bad_monitor(self):
        copilot = LocalCopilot(screen=True)
        self.assertTrue(copilot.status()["screen_enabled"])
        self.assertFalse(copilot.status()["vision_enabled"])
        for monitor in (-1, "1", 17, True):
            with self.assertRaises(CopilotPermissionError):
                copilot.capture_screen(monitor)


class TestCopilotHttp(unittest.TestCase):
    def test_origin_guard_and_file_access(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            (root / "help.md").write_text("conteúdo local", encoding="utf-8")
            engine = ChatEngine(lambda: None)
            server = create_chat_server(engine, ROOT / "chat", port=0,
                                        copilot=LocalCopilot([root]))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            port = server.server_address[1]
            base = f"http://127.0.0.1:{port}"
            try:
                def call(origin: str):
                    return Request(base + "/api/copilot", method="POST",
                                   headers={"Origin": origin,
                                            "Content-Type": "application/json"},
                                   data=json.dumps({"action": "read",
                                                    "path": str(root / "help.md")}).encode())
                with self.assertRaises(HTTPError) as error:
                    urlopen(call("https://attacker.example"), timeout=4)
                self.assertEqual(error.exception.code, 403)
                with urlopen(call(base), timeout=4) as response:
                    result = json.loads(response.read())
                self.assertEqual(result["content"], "conteúdo local")
                with urlopen(base + "/api/copilot/status", timeout=4) as response:
                    state = json.loads(response.read())
                self.assertTrue(state["files_enabled"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=4)


class TestGoogleProvider(unittest.TestCase):
    def test_google_needs_key(self):
        with patch.dict(os.environ, {"SERPER_API_KEY": ""}):
            with self.assertRaises(ValueError):
                WebSearchService("google")

    def test_google_results_normalized(self):
        service = WebSearchService("google", serper_key="example")
        with patch.object(service, "_request_google", return_value={
            "organic": [{"title": "Fonte", "link": "https://example.com/a",
                         "snippet": "Detalhes públicos"},
                        {"title": "Local", "link": "http://127.0.0.1/private",
                         "snippet": "Não incluir"}]
        }):
            results = service.search("meteorologia")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["url"], "https://example.com/a")

    def test_auto_uses_google_when_key_present(self):
        service = WebSearchService("auto", serper_key="example")
        self.assertTrue(service.supports_general_web())
        with patch.object(service, "_request_google", return_value={
            "organic": [{"title": "Fonte web", "link": "https://example.org",
                         "snippet": "Conteúdo"}]
        }) as lookup:
            result = service.search("computação")
        lookup.assert_called_once()
        self.assertEqual(len(result), 1)


if __name__ == "__main__":
    unittest.main()
