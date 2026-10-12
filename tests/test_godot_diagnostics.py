"""Godot diagnosis regression tests: bounded, authorized, read-only.

No project binaries are run, and no files in a real user project are touched.
"""
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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brain_ssd.chat.copilot import CopilotPermissionError, LocalCopilot
from brain_ssd.chat.copilot_queries import copilot_answer
from brain_ssd.chat.server import ChatEngine, create_chat_server


class TestGodotProjectInspector(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.project = base / "Godot Projeto"
        self.project.mkdir()
        (self.project / "project.godot").write_text("config_version=5\n", encoding="utf-8")
        self.scripts = self.project / "scripts"
        self.scripts.mkdir()
        self.script = self.scripts / "player.gd"
        self.script.write_text(
            "extends Node2D\n"
            "@onready var player = $Player\n"
            "# TODO: ensure player exists\n"
            "func _ready():\n"
            "    print(player.health)\n",
            encoding="utf-8",
        )
        (self.project / "world.tscn").write_text("[gd_scene]\n", encoding="utf-8")
        (self.project / ".godot").mkdir()
        (self.project / ".godot" / "sensitive.gd").write_text(
            "private_string", encoding="utf-8"
        )
        (self.project / ".env").write_text("TOKEN=not-a-real-secret", encoding="utf-8")
        self.copilot = LocalCopilot([self.project])
        self.before = self.script.read_bytes()

    def test_project_structure_and_source_are_grounded(self) -> None:
        report = self.copilot.inspect_godot_project(str(self.project))
        self.assertEqual(report["project_manifest"], "project.godot")
        self.assertEqual(report["script_count"], 1)
        self.assertEqual(report["scene_count"], 1)
        self.assertIn("scripts/player.gd", report["files"])
        self.assertFalse(any(".godot" in entry or ".env" in entry
                             for entry in report["files"]))
        self.assertEqual(report["todo"][0]["line"], 3)
        self.assertEqual(self.script.read_bytes(), self.before)

    def test_error_trace_points_to_real_file_and_line(self) -> None:
        result = self.copilot.diagnose_godot_error(
            str(self.project),
            "SCRIPT ERROR: Invalid access to property\n"
            "at: res://scripts/player.gd:5"
        )
        self.assertEqual(result["matched_count"], 1)
        match = result["matches"][0]
        self.assertEqual(match["file"], "scripts/player.gd")
        self.assertEqual(match["reported_line"], 5)
        self.assertIn("print(player.health)", match["snippet"][-1]["text"])
        self.assertTrue(any("objeto" in text for text in result["recommendations"]))
        self.assertEqual(self.script.read_bytes(), self.before)

    def test_unique_basename_is_accepted_but_ambiguous_one_is_not(self) -> None:
        unique = self.copilot.diagnose_godot_error(str(self.project),
                                                   "Parser error in player.gd:4")
        self.assertEqual(unique["matched_count"], 1)
        second = self.project / "other"
        second.mkdir()
        (second / "player.gd").write_text("extends Node\n", encoding="utf-8")
        ambiguous = self.copilot.diagnose_godot_error(str(self.project),
                                                      "Parser error in player.gd:4")
        self.assertEqual(ambiguous["matched_count"], 0)

    def test_unknown_file_cannot_be_conjured_from_stack_trace(self) -> None:
        result = self.copilot.diagnose_godot_error(
            str(self.project), "Invalid access res://scripts/not_here.gd:42"
        )
        self.assertEqual(result["matched_count"], 0)
        self.assertTrue(any("Não foi possível" in x for x in result["recommendations"]))

    def test_traversal_and_protected_paths_not_indexed(self) -> None:
        result = self.copilot.diagnose_godot_error(
            str(self.project), "at res://../.env:1 and res://.godot/sensitive.gd:1"
        )
        self.assertEqual(result["matched_count"], 0)

    def test_symlink_to_outside_is_not_indexed(self) -> None:
        outside = Path(self.tmp.name) / "outside.gd"
        outside.write_text("extends Node\n", encoding="utf-8")
        symlink = self.scripts / "escape.gd"
        try:
            symlink.symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("Windows requires Developer Mode or privileges for symlinks.")
        report = self.copilot.inspect_godot_project(str(self.project))
        self.assertNotIn("scripts/escape.gd", report["files"])

    def test_no_copilot_permission_or_project_manifest(self) -> None:
        denied = LocalCopilot()
        with self.assertRaises(CopilotPermissionError):
            denied.inspect_godot_project(str(self.project))
        with self.assertRaises(CopilotPermissionError):
            denied.diagnose_godot_error(str(self.project), "res://scripts/player.gd:1")
        with self.assertRaises(CopilotPermissionError):
            self.copilot.inspect_godot_project(str(self.scripts))

    def test_oversized_error_denied(self) -> None:
        with self.assertRaises(CopilotPermissionError):
            self.copilot.diagnose_godot_error(str(self.project), "x" * 4001)

    def test_chat_commands_use_real_inspector(self) -> None:
        first = copilot_answer("/projeto " + str(self.project), self.copilot)
        self.assertEqual(first["local_action"], "copilot_godot_project")
        self.assertIn("scripts/player.gd", first["answer"])
        second = copilot_answer(
            '/erro-godot "' + str(self.project) +
            '" :: at res://scripts/player.gd:5', self.copilot
        )
        self.assertEqual(second["local_action"], "copilot_godot_diagnosis")
        self.assertIn("player.gd:5", second["answer"])
        self.assertEqual(self.script.read_bytes(), self.before)

    def test_http_scan_and_diagnosis(self) -> None:
        engine = ChatEngine(lambda: None, copilot=self.copilot)
        server = create_chat_server(engine, ROOT / "chat", port=0, copilot=self.copilot)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        url = f"http://127.0.0.1:{server.server_address[1]}"
        try:
            def post(payload: dict, origin: str = url) -> dict:
                request = Request(
                    url + "/api/copilot", method="POST",
                    headers={"Origin": origin, "Content-Type": "application/json"},
                    data=json.dumps(payload).encode("utf-8")
                )
                with urlopen(request, timeout=5) as response:
                    return json.loads(response.read())
            scanned = post({"action": "project_scan", "path": str(self.project)})
            self.assertEqual(scanned["script_count"], 1)
            diagnosed = post({
                "action": "godot_error", "path": str(self.project),
                "error": "at res://scripts/player.gd:5",
            })
            self.assertEqual(diagnosed["matched_count"], 1)
            with self.assertRaises(HTTPError) as invalid_origin:
                post({"action": "project_scan", "path": str(self.project)},
                     origin="http://attacker.example")
            self.assertEqual(invalid_origin.exception.code, 403)
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
