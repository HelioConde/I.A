"""Local model patch drafts: model output is never trusted or applied directly.

All tests mock the model, use temporary fixture files and do not run project
code, launch executables or communicate with external services.
"""
from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brain_ssd.chat.copilot import CopilotPermissionError, LocalCopilot
from brain_ssd.chat.server import ChatEngine, create_chat_server


class TestModelPatchDraft(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.source = self.root / "math.py"
        self.source.write_text(
            "def total(a):\n    return a + 0\n", encoding="utf-8")
        self.copilot = LocalCopilot([self.root], edit=True)
        self.backups = self.root / "backups"
        self.answer = json.dumps({
            "before": "return a + 0",
            "after": "return a",
            "reason": "Reduz operação redundante.",
        })

    def test_valid_candidate_only_stages_diff(self):
        original = self.source.read_bytes()
        model = Mock(return_value=self.answer)
        proposal = self.copilot.propose_model_patch(
            str(self.source), "Remova a adição redundante", model)
        self.assertEqual(proposal["status"], "proposal")
        self.assertIn("-    return a + 0", proposal["diff"])
        self.assertIn("+    return a", proposal["diff"])
        self.assertEqual(self.source.read_bytes(), original)
        self.assertIn("ast.parse", proposal["validation"])
        prompt = model.call_args.args[0]
        self.assertIn("return a + 0", prompt)
        self.assertIn("JSON", prompt)
        with patch("brain_ssd.chat.code_edits._backup_dir", return_value=self.backups):
            applied = self.copilot.apply_code_edit(proposal["token"])
        self.assertEqual(applied["status"], "applied")
        self.assertIn("return a\n", self.source.read_text())

    def test_denied_scope_never_calls_model(self):
        no_edit = LocalCopilot([self.root])
        generate = Mock()
        with self.assertRaises(CopilotPermissionError):
            no_edit.propose_model_patch(str(self.source), "Corrigir", generate)
        generate.assert_not_called()
        with self.assertRaises(CopilotPermissionError):
            self.copilot.propose_model_patch(
                str(self.root / "missing.py"), "Corrigir", generate)
        generate.assert_not_called()

    def test_invalid_model_json_and_wrong_schema_do_not_stage(self):
        old = self.source.read_bytes()
        for response in (
            "Vou corrigir automaticamente", "{}", '{"before":"x"}',
            '{"before":"x","after":"y","reason":"z","command":"rm -rf /"}',
            '{"before":7,"after":"x","reason":"teste"}',
        ):
            with self.subTest(response=response):
                with self.assertRaises(CopilotPermissionError):
                    self.copilot.propose_model_patch(
                        str(self.source), "Corrigir", lambda _: response)
                self.assertEqual(self.source.read_bytes(), old)

    def test_file_must_still_match_after_inference(self):
        def changed(_):
            self.source.write_text(
                "def total(a):\n    return a + 3\n", encoding="utf-8")
            return self.answer
        with self.assertRaises(CopilotPermissionError):
            self.copilot.propose_model_patch(
                str(self.source), "Corrigir", changed)
        self.assertIn("a + 3", self.source.read_text())

    def test_reject_bad_python_syntax(self):
        output = json.dumps({
            "before": "return a + 0",
            "after": "return (",
            "reason": "Proposta ruim",
        })
        with self.assertRaises(CopilotPermissionError):
            self.copilot.propose_model_patch(
                str(self.source), "Corrigir", lambda _: output)
        self.assertIn("return a + 0", self.source.read_text())

    def test_reject_nonexistent_or_ambiguous_source(self):
        model = Mock(return_value=json.dumps({
            "before": "does_not_exist", "after": "hello", "reason": "Teste",
        }))
        with self.assertRaises(CopilotPermissionError):
            self.copilot.propose_model_patch(
                str(self.source), "Corrigir", model)
        self.source.write_text(
            "value = 123\nvalue = 123\n", encoding="utf-8")
        repeat = json.dumps({
            "before": "value = 123",
            "after": "value = 456",
            "reason": "Mudança",
        })
        with self.assertRaises(CopilotPermissionError):
            self.copilot.propose_model_patch(
                str(self.source), "Corrigir", lambda _: repeat)

    def test_json_static_guard(self):
        file = self.root / "info.json"
        file.write_text('{"active":true}\n', encoding="utf-8")
        valid = json.dumps({
            "before": "true", "after": "false", "reason": "Solicitado",
        })
        proposal = self.copilot.propose_model_patch(
            str(file), "Desative a opção", lambda _: valid)
        self.assertIn("JSON", proposal["validation"])
        invalid = json.dumps({
            "before": "true", "after": "NaN}", "reason": "Ruim",
        })
        with self.assertRaises(CopilotPermissionError):
            self.copilot.propose_model_patch(
                str(file), "Desative a opção", lambda _: invalid)

    def test_focus_line_must_exist_and_short_input(self):
        model = Mock(return_value=self.answer)
        with self.assertRaises(CopilotPermissionError):
            self.copilot.propose_model_patch(
                str(self.source), "Corrigir", model, focus_line=999)
        model.assert_not_called()
        with self.assertRaises(CopilotPermissionError):
            self.copilot.propose_model_patch(
                str(self.source), "X" * 381, model)
        model.assert_not_called()
        self.copilot.propose_model_patch(
            str(self.source), "Corrigir", model, focus_line=2)
        self.assertIn("return a + 0", model.call_args.args[0])

    def test_local_api_does_not_apply_until_explicit_confirmation(self):
        engine = ChatEngine(lambda: None, copilot=self.copilot)
        server = create_chat_server(
            engine, ROOT / "chat", port=0, copilot=self.copilot)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_address[1]}"
        try:
            def post(body, origin=base):
                request = Request(
                    base + "/api/copilot", method="POST",
                    data=json.dumps(body).encode("utf-8"),
                    headers={"Origin": origin, "Content-Type": "application/json"},
                )
                with urlopen(request, timeout=8) as response:
                    return json.loads(response.read())
            with patch.object(engine, "ask", return_value={"answer": self.answer}) as model:
                with self.assertRaises(HTTPError) as wrong_origin:
                    post({"action": "draft_model_patch", "path": str(self.source),
                          "instruction": "Reduza operação redundante"},
                         origin="https://other.example")
                self.assertEqual(wrong_origin.exception.code, 403)
                proposal = post({
                    "action": "draft_model_patch", "path": str(self.source),
                    "instruction": "Reduza operação redundante",
                    "focus_line": 2,
                })
                self.assertIn("return a + 0", self.source.read_text())
                self.assertEqual(proposal["status"], "proposal")
                self.assertEqual(model.call_args.kwargs["web_search"], False)
                self.assertEqual(model.call_args.kwargs["remember_web"], False)
                self.assertEqual(model.call_args.kwargs["response_tokens"], 256)
                with patch("brain_ssd.chat.code_edits._backup_dir",
                           return_value=self.backups):
                    result = post({"action": "apply_code_edit",
                                   "token": proposal["token"]})
                self.assertEqual(result["status"], "applied")
                self.assertIn("return a\n", self.source.read_text())
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
