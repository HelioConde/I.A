"""Godot executable checks remain opt-in, one-shot and shell-free.

These tests MOCK subprocess.run and never execute a real Godot binary.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from brain_ssd.chat.copilot import CopilotPermissionError, LocalCopilot
from brain_ssd.chat.copilot_queries import copilot_answer
from brain_ssd.chat.server import ChatEngine, create_chat_server


class TestGodotValidation(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.project = base / "My Godot Game"
        (self.project / "scripts").mkdir(parents=True)
        (self.project / "project.godot").write_text("config_version=5\n", encoding="utf-8")
        self.script = self.project / "scripts" / "player.gd"
        self.script.write_text("extends Node\nvar x = 1\n", encoding="utf-8")
        self.binary = base / "Godot_v4.exe"
        self.binary.write_bytes(b"fake-binary-test-only")
        self.copilot = LocalCopilot([self.project], godot_binary=self.binary)

    def test_chat_proposes_but_does_not_launch(self):
        question = '/validar-godot "' + str(self.project) + '" :: res://scripts/player.gd'
        with patch("brain_ssd.chat.godot_validation.subprocess.run") as runner:
            answer = copilot_answer(question, self.copilot)
            self.assertEqual(answer["local_action"], "copilot_godot_validation_proposal")
            self.assertIn("--check-only", answer["answer"])
            self.assertGreater(len(answer["copilot_godot_validation_token"]), 20)
            runner.assert_not_called()
            denied = copilot_answer(question, LocalCopilot([self.project]))
            self.assertEqual(denied["local_action"], "copilot_godot_validation_disabled")
            runner.assert_not_called()

    def test_permission_absent_cannot_propose_or_run(self):
        denied = LocalCopilot([self.project])
        self.assertFalse(denied.status()["godot_validate_enabled"])
        with self.assertRaises(CopilotPermissionError):
            denied.propose_godot_validation(str(self.project), "res://scripts/player.gd")
        with self.assertRaises(CopilotPermissionError):
            denied.confirm_godot_validation("forged")

    def test_explicit_proposal_no_execution_and_arguments_fixed(self):
        with patch("brain_ssd.chat.godot_validation.subprocess.run") as runner:
            proposal = self.copilot.propose_godot_validation(
                str(self.project), "res://scripts/player.gd"
            )
            self.assertEqual(proposal["script"], "res://scripts/player.gd")
            self.assertEqual(proposal["timeout_seconds"], 30)
            self.assertIn("--check-only", proposal["command_flags"])
            self.assertIn("--recovery-mode", proposal["command_flags"])
            self.assertIn("não", proposal["warning"].casefold())
            runner.assert_not_called()

    def test_single_use_approved_check_produces_real_exit_status(self):
        proposal = self.copilot.propose_godot_validation(
            str(self.project), "res://scripts/player.gd"
        )
        returned = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"Parse OK\n")
        with patch("brain_ssd.chat.godot_validation.subprocess.run", return_value=returned) as runner:
            result = self.copilot.confirm_godot_validation(proposal["token"])
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["exit_code"], 0)
            self.assertIn("Parse OK", result["output"])
            args, kwargs = runner.call_args
            self.assertEqual(args[0][0], str(self.binary))
            self.assertEqual(args[0][-1], "--check-only")
            self.assertEqual(args[0][-2], "res://scripts/player.gd")
            self.assertEqual(kwargs["cwd"], str(self.project))
            self.assertFalse(kwargs["shell"])
            self.assertEqual(kwargs["timeout"], 30)
            with self.assertRaises(CopilotPermissionError):
                self.copilot.confirm_godot_validation(proposal["token"])
            runner.assert_called_once()

    def test_error_exit_and_timeout_are_not_false_pass(self):
        failure = self.copilot.propose_godot_validation(
            str(self.project), "scripts/player.gd")
        with patch("brain_ssd.chat.godot_validation.subprocess.run",
                   return_value=subprocess.CompletedProcess([], 3, b"Parse ERROR")):
            result = self.copilot.confirm_godot_validation(failure["token"])
            self.assertEqual(result["status"], "FAIL")
            self.assertEqual(result["exit_code"], 3)
        timeout = self.copilot.propose_godot_validation(
            str(self.project), "scripts/player.gd")
        with patch("brain_ssd.chat.godot_validation.subprocess.run",
                   side_effect=subprocess.TimeoutExpired(["godot"], timeout=30)):
            result = self.copilot.confirm_godot_validation(timeout["token"])
            self.assertEqual(result["status"], "TIMEOUT")

    def test_changed_script_or_manifest_blocks_execution(self):
        proposal = self.copilot.propose_godot_validation(
            str(self.project), "res://scripts/player.gd")
        self.script.write_text("extends Node\nvar x = 100\n", encoding="utf-8")
        with patch("brain_ssd.chat.godot_validation.subprocess.run") as runner:
            with self.assertRaises(CopilotPermissionError):
                self.copilot.confirm_godot_validation(proposal["token"])
            runner.assert_not_called()

    def test_traversal_and_non_script_paths_are_rejected(self):
        with patch("brain_ssd.chat.godot_validation.subprocess.run") as runner:
            for resource in ("res://../secret.gd", "/etc/passwd",
                             "res://.godot/internal.gd",
                             "res://scripts/player.gd;rm -rf",
                             "res://project.godot", "res://scripts/../project.godot"):
                with self.subTest(resource=resource):
                    with self.assertRaises(CopilotPermissionError):
                        self.copilot.propose_godot_validation(str(self.project), resource)
            runner.assert_not_called()

    def test_cannot_confirm_forged_or_reused_token(self):
        with patch("brain_ssd.chat.godot_validation.subprocess.run") as runner:
            with self.assertRaises(CopilotPermissionError):
                self.copilot.confirm_godot_validation("unrecognized")
            runner.assert_not_called()

    def test_no_project_roots_rejected_at_startup(self):
        with self.assertRaises(ValueError):
            LocalCopilot([], godot_binary=self.binary)

    def test_origin_guard_on_local_endpoint(self):
        server = create_chat_server(
            ChatEngine(lambda: None, copilot=self.copilot),
            ROOT / "chat", port=0, copilot=self.copilot
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_address[1]}"
        try:
            def post(action, origin):
                req = Request(
                    base + "/api/copilot", method="POST",
                    headers={"Content-Type": "application/json", "Origin": origin},
                    data=json.dumps(action).encode("utf-8")
                )
                with urlopen(req, timeout=4) as response:
                    return json.loads(response.read())
            payload = {"action": "propose_godot_validation",
                       "path": str(self.project), "script": "res://scripts/player.gd"}
            with self.assertRaises(HTTPError) as blocked:
                post(payload, "https://attacker.example")
            self.assertEqual(blocked.exception.code, 403)
            accepted = post(payload, base)
            self.assertGreater(len(accepted["token"]), 20)
            with patch("brain_ssd.chat.godot_validation.subprocess.run",
                       return_value=subprocess.CompletedProcess([], 0, b"Parse OK")) as runner:
                done = post({"action": "confirm_godot_validation",
                             "token": accepted["token"]}, base)
                self.assertEqual(done["status"], "PASS")
                runner.assert_called_once()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
