"""Jarvis-style Windows tools: explicit permissions, no hallucinated launches.

Unit tests use mock app listings and NEVER open a real Windows program.
"""
from __future__ import annotations

import json
import sys
import threading
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from brain_ssd.chat.copilot import CopilotPermissionError, LocalCopilot
from brain_ssd.chat.copilot_queries import copilot_answer
from brain_ssd.chat.server import ChatEngine, create_chat_server


APPS = {"items": [{"name": "Godot Engine", "version": "4.7.2", "publisher": "Godot"}],
        "total_matches": 1, "truncated": False,
        "source": "Windows Registry Uninstall"}
PROCESSES = {"items": [{"name": "godot.exe", "pid": 31415}],
             "total_matches": 1, "truncated": False, "source": "tasklist.exe"}


class TestJarvisTools(unittest.TestCase):
    def test_registry_results_are_from_tool_not_llm(self):
        assistant = LocalCopilot(apps=True)
        with patch("brain_ssd.chat.windows_apps.installed_apps", return_value=APPS) as lookup:
            answer = copilot_answer("Tenho o Godot instalado? Em qual pasta?", assistant)
        self.assertEqual(answer["local_action"], "copilot_installed_apps")
        self.assertIn("Godot Engine", answer["answer"])
        self.assertIn("Não foi verificado o caminho", answer["answer"])
        lookup.assert_called_once_with("godot")

    def test_process_names_and_pid_are_grounded(self):
        assistant = LocalCopilot(apps=True)
        with patch("brain_ssd.chat.windows_apps.running_apps", return_value=PROCESSES) as lookup:
            answer = copilot_answer("O Godot está aberto neste momento?", assistant)
        self.assertEqual(answer["local_action"], "copilot_running_apps")
        self.assertIn("godot.exe", answer["answer"])
        self.assertIn("31415", answer["answer"])
        lookup.assert_called_once_with("godot")

    def test_hardware_question_does_not_trigger_inventory(self):
        assistant = LocalCopilot(apps=True)
        with patch("brain_ssd.chat.windows_apps.installed_apps") as lookup:
            answer = copilot_answer("O que você sabe sobre meu computador?", assistant)
        self.assertEqual(answer["local_action"], "copilot_system")
        lookup.assert_not_called()

    def test_unapproved_inventory_does_not_touch_windows(self):
        assistant = LocalCopilot(screen=True)
        with patch("brain_ssd.chat.windows_apps.installed_apps") as lookup:
            response = copilot_answer("Quais aplicativos estão instalados?", assistant)
        self.assertEqual(response["local_action"], "copilot_apps_disabled")
        lookup.assert_not_called()

    def test_unsupported_app_does_not_generate_token(self):
        assistant = LocalCopilot(apps=True, launch=True)
        response = copilot_answer("Abra o Godot agora.", assistant)
        self.assertEqual(response["local_action"], "copilot_launch_unsupported")
        self.assertNotIn("copilot_launch_token", response)

    def test_capability_question_never_generates_launch(self):
        assistant = LocalCopilot(launch=True)
        response = copilot_answer("Você consegue abrir a Calculadora do Windows?", assistant)
        self.assertEqual(response["local_action"], "copilot_launch_info")
        self.assertNotIn("copilot_launch_token", response)

    def test_launch_requires_user_action_and_is_one_use(self):
        assistant = LocalCopilot(launch=True)
        with patch("brain_ssd.chat.windows_apps.run_approved_app",
                   return_value={"app_id": "notepad", "label": "Bloco de Notas",
                                 "started_pid": 777, "status": "requested"}) as real_launcher:
            answer = copilot_answer("Abra o Bloco de Notas agora.", assistant)
            self.assertEqual(answer["local_action"], "copilot_launch_proposal")
            real_launcher.assert_not_called()
            token = answer["copilot_launch_token"]
            self.assertGreater(len(token), 20)
            self.assertEqual(assistant.confirm_launch(token)["started_pid"], 777)
            real_launcher.assert_called_once_with("notepad")
            with self.assertRaises(CopilotPermissionError):
                assistant.confirm_launch(token)

    def test_unauthorized_and_forged_tokens_rejected(self):
        denied = LocalCopilot()
        with self.assertRaises(CopilotPermissionError):
            denied.confirm_launch("guessed")
        enabled = LocalCopilot(launch=True)
        with self.assertRaises(CopilotPermissionError):
            enabled.confirm_launch("guessed")
        with self.assertRaises(CopilotPermissionError):
            enabled.offer_launch("powershell")

    def test_launch_token_expires(self):
        assistant = LocalCopilot(launch=True)
        with patch("brain_ssd.chat.copilot.time.monotonic", return_value=100):
            token = assistant.offer_launch("calculator")["token"]
        with patch("brain_ssd.chat.copilot.time.monotonic", return_value=191):
            with patch("brain_ssd.chat.windows_apps.run_approved_app") as launcher:
                with self.assertRaises(CopilotPermissionError):
                    assistant.confirm_launch(token)
                launcher.assert_not_called()

    def test_unrelated_query_remains_regular_chat(self):
        assistant = LocalCopilot(apps=True, launch=True)
        self.assertIsNone(copilot_answer("Como funciona a CPU?", assistant))
        self.assertIsNone(copilot_answer("Você conhece o Homem de Ferro?", assistant))

    def test_server_rejects_launch_without_valid_token(self):
        assistant = LocalCopilot(launch=True)
        server = create_chat_server(ChatEngine(lambda: None, copilot=assistant),
                                    ROOT / "chat", port=0, copilot=assistant)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_address[1]}"
        try:
            def call(token: str, origin: str = base):
                return Request(base + "/api/copilot",
                    data=json.dumps({"action": "launch", "token": token}).encode(),
                    headers={"Origin": origin, "Content-Type": "application/json"},
                    method="POST")
            with self.assertRaises(HTTPError) as bad:
                urlopen(call("forged"), timeout=3)
            self.assertEqual(bad.exception.code, 400)
            with self.assertRaises(HTTPError) as origin:
                urlopen(call("forged", "https://evil.example"), timeout=3)
            self.assertEqual(origin.exception.code, 403)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
