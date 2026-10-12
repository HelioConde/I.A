"""Regression tests for deterministic, read-only multi-step Agent Core.

No Godot executable, shell, UI automation or user project is used.
"""
from __future__ import annotations

import json
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


class AgentCoreTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.project = self.base / "SampleGodot"
        scripts = self.project / "scripts"
        scripts.mkdir(parents=True)
        (self.project / "project.godot").write_text("config_version=5\n", encoding="utf-8")
        self.script = scripts / "player.gd"
        self.script.write_text(
            "extends Node\n"
            "# TODO fix\n"
            "func _ready():\n"
            "    print(player.name)\n",
            encoding="utf-8",
        )
        self.copilot = LocalCopilot([self.project])
        self.before = self.script.read_bytes()

    def test_chat_plans_but_never_executes_automatically(self):
        question = ('/investigar-godot "' + str(self.project) +
                    '" :: Invalid access at res://scripts/player.gd:4')
        with patch.object(self.copilot, "inspect_godot_project") as inspector:
            proposal = copilot_answer(question, self.copilot)
            inspector.assert_not_called()
        self.assertEqual(proposal["local_action"], "copilot_agent_plan")
        self.assertNotIn("completada", proposal["answer"].lower())
        self.assertGreater(len(proposal["copilot_agent_token"]), 20)
        result = self.copilot.run_investigation(proposal["copilot_agent_token"])
        self.assertEqual(result["status"], "completed")
        self.assertEqual(self.script.read_bytes(), self.before)

    def test_explicit_pc_command_remains_read_only(self):
        with patch.object(self.copilot, "system_info") as inspector:
            proposal = copilot_answer("/investigar-pc", self.copilot)
            self.assertEqual(proposal["local_action"], "copilot_agent_plan")
            inspector.assert_not_called()

    def test_plan_does_not_read_project_or_run_tools(self):
        with patch.object(self.copilot, "inspect_godot_project") as inspector:
            proposal = self.copilot.plan_investigation(
                "godot_overview", project=str(self.project)
            )
            inspector.assert_not_called()
        self.assertEqual(proposal["task"], "godot_overview")
        self.assertEqual(len(proposal["steps"]), 3)
        self.assertIn("Leitura", proposal["risk"])
        self.assertEqual(self.script.read_bytes(), self.before)

    def test_diagnosis_executes_fixed_local_steps_with_evidence(self):
        plan = self.copilot.plan_investigation(
            "godot_diagnosis", project=str(self.project),
            error="Invalid access at res://scripts/player.gd:4",
        )
        self.assertNotIn("error", plan["scope"])
        with patch.object(self.copilot, "propose_code_edit") as edit:
            with patch.object(self.copilot, "confirm_launch") as launch:
                result = self.copilot.run_investigation(plan["token"])
                edit.assert_not_called()
                launch.assert_not_called()
        self.assertEqual(result["task"], "godot_diagnosis")
        self.assertEqual(result["status"], "completed")
        self.assertEqual([e["step"] for e in result["evidence"]],
                         ["godot_project_inspector", "godot_error_inspector"])
        matches = result["evidence"][1]["facts"]["matches"]
        self.assertEqual(matches[0]["file"], "scripts/player.gd")
        self.assertEqual(matches[0]["reported_line"], 4)
        self.assertIn("print(player.name)", matches[0]["snippet"][-1]["text"])
        self.assertEqual(self.script.read_bytes(), self.before)
        with self.assertRaises(CopilotPermissionError):
            self.copilot.run_investigation(plan["token"])

    def test_unknown_error_is_partial_not_successful_fix(self):
        plan = self.copilot.plan_investigation(
            "godot_diagnosis", project=str(self.project),
            error="Unexpected failure at res://missing.gd:100",
        )
        result = self.copilot.run_investigation(plan["token"])
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["evidence"][1]["facts"]["matched_count"], 0)
        self.assertNotIn("applied", result)
        self.assertEqual(self.script.read_bytes(), self.before)

    def test_static_code_review_and_todos(self):
        plan = self.copilot.plan_investigation(
            "code_review", path=str(self.script))
        result = self.copilot.run_investigation(plan["token"])
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["evidence"][0]["facts"]["todos"][0]["line"], 2)
        self.assertEqual(self.script.read_bytes(), self.before)

    def test_pc_report_uses_actual_tool_not_fabricated_specs(self):
        assistant = LocalCopilot(screen=True)
        specs = {
            "os": "Windows TEST", "architecture": "AMD64", "cpu_name": "test-CPU",
            "cpu_threads": 4, "ram_total_gib": 4.0, "disks": [], "python": "3.14",
        }
        with patch.object(assistant, "system_info", return_value=specs) as tool:
            proposal = assistant.plan_investigation("pc_report")
            tool.assert_not_called()
            result = assistant.run_investigation(proposal["token"])
            tool.assert_called_once()
        self.assertEqual(result["evidence"][0]["facts"]["ram_gib"], 4.0)
        self.assertTrue(any("8 GiB" in x for x in result["suggestions"]))

    def test_denied_scopes_and_unknown_tasks(self):
        with self.assertRaises(CopilotPermissionError):
            LocalCopilot().plan_investigation(
                "godot_overview", project=str(self.project)
            )
        with self.assertRaises(CopilotPermissionError):
            LocalCopilot().plan_investigation("pc_report")
        with self.assertRaises(CopilotPermissionError):
            self.copilot.plan_investigation("run_shell", path=str(self.script))
        with self.assertRaises(CopilotPermissionError):
            self.copilot.plan_investigation(
                "godot_diagnosis", project=str(self.project), error="x" * 4001
            )
        with self.assertRaises(CopilotPermissionError):
            self.copilot.plan_investigation(
                "code_review", path=str(self.base / "outside.py")
            )

    def test_unknown_expired_and_replaced_tokens(self):
        first = self.copilot.plan_investigation(
            "godot_overview", project=str(self.project))
        second = self.copilot.plan_investigation(
            "code_review", path=str(self.script))
        with self.assertRaises(CopilotPermissionError):
            self.copilot.run_investigation(first["token"])
        with self.assertRaises(CopilotPermissionError):
            self.copilot.run_investigation("fake")
        from brain_ssd.chat import agent_core
        with patch.object(agent_core.time, "monotonic", return_value=1e20):
            with self.assertRaises(CopilotPermissionError):
                self.copilot.run_investigation(second["token"])

    def test_http_origin_and_authorized_execution(self):
        server = create_chat_server(
            ChatEngine(lambda: None, copilot=self.copilot),
            ROOT / "chat", port=0, copilot=self.copilot
        )
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        base = f"http://127.0.0.1:{server.server_address[1]}"
        try:
            def post(body, origin=base):
                request = Request(
                    base + "/api/copilot", method="POST",
                    data=json.dumps(body).encode("utf-8"),
                    headers={"Origin": origin, "Content-Type": "application/json"},
                )
                with urlopen(request, timeout=6) as response:
                    return json.loads(response.read())
            with self.assertRaises(HTTPError) as wrong_origin:
                post({"action": "agent_plan", "task": "pc_report"},
                     origin="https://external.example")
            self.assertEqual(wrong_origin.exception.code, 403)
            plan = post({
                "action": "agent_plan", "task": "godot_overview",
                "project": str(self.project),
            })
            self.assertEqual(len(plan["steps"]), 3)
            result = post({"action": "agent_execute", "token": plan["token"]})
            self.assertEqual(result["status"], "completed")
            with self.assertRaises(HTTPError) as second:
                post({"action": "agent_execute", "token": plan["token"]})
            self.assertEqual(second.exception.code, 400)
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
