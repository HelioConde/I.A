"""Ollama mocked. NEVER executes generated JavaScript."""
from __future__ import annotations

from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch
import luna_arcade_builder as builder

REFERENCE = """function updateGame(state,input,dt) {
  state.player.x += (Number(input.right)-Number(input.left))*dt*265;
  return state;
}"""


class ArcadeBuilderTests(unittest.TestCase):
    def test_game_completion_has_extended_token_budget(self):
        with patch.object(builder, "local_json",
                          return_value={"message": {"content": REFERENCE}}) as call:
            result = builder.arcade_chat(builder.DEFAULT_MODEL, [])
        self.assertEqual(result, REFERENCE)
        self.assertEqual(call.call_args.args[:2], ("POST", "/api/chat"))
        self.assertEqual(call.call_args.args[2]["options"]["num_predict"], 1400)

    def test_filter_accepts_pure_function(self):
        self.assertTrue(builder.validate_candidate(REFERENCE)[0])

    def test_filter_rejects_wrong_function(self):
        self.assertFalse(builder.validate_candidate("function updatePlayer() {}")[0])

    def test_filter_rejects_browser_access(self):
        self.assertFalse(builder.validate_candidate("function updateGame(){fetch('/data');}")[0])
        self.assertFalse(builder.validate_candidate("function updateGame(){window.location='x';}")[0])

    def test_filter_rejects_infinite_loop(self):
        self.assertFalse(builder.validate_candidate("function updateGame(){while(true){} }")[0])

    def test_filter_rejects_oversized_code(self):
        self.assertFalse(builder.validate_candidate(REFERENCE + " " * 17000)[0])

    def test_candidate_is_separate_and_attributed(self):
        with tempfile.TemporaryDirectory(prefix="luna_arcade_test_") as td, patch.object(
            builder, "syntax_check", return_value={"status": "pass"}
        ) as check:
            output = builder.build("Gentle 2D platformer", root=Path(td),
                                   request=lambda model, messages: REFERENCE)
            self.assertEqual(output["status"], "candidate_needs_human_review")
            folder = Path(output["folder"])
            self.assertTrue((folder / "index.html").is_file())
            self.assertTrue((folder / "engine.js").is_file())
            self.assertTrue((folder / "gameplay.js").is_file())
            manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["generated_by"], "PRETRAINED_OLLAMA_MODEL")
            self.assertEqual(manifest["behavior"], "NOT_TESTED")
            self.assertTrue(manifest["human_review_required"])
            self.assertFalse(manifest["code_executed_on_host"])
            self.assertIn("MiniCoder scratch", manifest["not_generated_by"])
            check.assert_called_once()
            self.assertTrue((builder.DEMO / "gameplay.js").read_text(encoding="utf-8").startswith('"use strict";'))

    def test_rejected_source_does_not_create_run(self):
        with tempfile.TemporaryDirectory(prefix="luna_arcade_test_") as td:
            root = Path(td) / "runs"
            result = builder.build("Movement", root=root,
                                   request=lambda model, messages: "const x = fetch('/');")
            self.assertEqual(result["status"], "rejected_no_preview")
            self.assertFalse(root.exists())

    def test_one_repair_attempt(self):
        responses = iter(["function broken(){}", REFERENCE])
        with tempfile.TemporaryDirectory(prefix="luna_arcade_test_") as td, patch.object(
            builder, "syntax_check", return_value={"status": "pass"}
        ):
            result = builder.build("Jumping", root=Path(td),
                                   request=lambda model, messages: next(responses))
        self.assertEqual(result["attempts"], 2)
        self.assertEqual(result["status"], "candidate_needs_human_review")

    def test_refuses_unknown_model(self):
        with self.assertRaises(ValueError):
            builder.build("Original game", model="any-cloud-api")


if __name__ == "__main__":
    unittest.main()
