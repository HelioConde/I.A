"""Code edit regression: uses scratch fixtures and never changes user files."""
from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from brain_ssd.chat.copilot import CopilotPermissionError, LocalCopilot
from brain_ssd.chat.copilot_queries import copilot_answer


class CodeEditingTests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(self.workspace.cleanup)
        self.root = Path(self.workspace.name)
        self.backups = self.root / "private-backups"
        self.fixture = self.root / "hero.gd"
        self.fixture.write_text("extends Node\nvar speed = 10\n", encoding="utf-8")
        self.copilot = LocalCopilot([self.root], edit=True)

    def test_chat_code_review_and_proposal_are_real(self):
        response = copilot_answer("/revisar " + str(self.fixture), self.copilot)
        self.assertEqual(response["local_action"], "copilot_code_review")
        self.assertIn("Linhas: 2", response["answer"])
        question = ('/trocar "' + str(self.fixture) +
                    '" "speed = 10" => "speed = 12"')
        change = copilot_answer(question, self.copilot)
        self.assertEqual(change["local_action"], "copilot_code_edit_proposal")
        self.assertIn("+var speed = 12", change["answer"])
        self.assertEqual(self.fixture.read_text(), "extends Node\nvar speed = 10\n")
        with patch("brain_ssd.chat.code_edits._backup_dir", return_value=self.backups):
            self.copilot.apply_code_edit(change["copilot_edit_token"])
        self.assertIn("speed = 12", self.fixture.read_text())

    def test_code_review_is_grounded_without_execution(self):
        result = self.copilot.review_code(str(self.fixture))
        self.assertEqual(result["line_count"], 2)
        self.assertEqual(result["size_bytes"], len(self.fixture.read_bytes()))
        bad = self.root / "syntax.py"
        bad.write_text("def broken(:\n", encoding="utf-8")
        self.assertIn("Sintaxe Python", self.copilot.review_code(str(bad))["warnings"][0])

    def test_diff_is_not_write_and_apply_produces_backup(self):
        before = self.fixture.read_bytes()
        with patch("brain_ssd.chat.code_edits._backup_dir", return_value=self.backups):
            offer = self.copilot.propose_code_edit(str(self.fixture), "speed = 10", "speed = 20")
            self.assertIn("-var speed = 10", offer["diff"])
            self.assertIn("+var speed = 20", offer["diff"])
            self.assertEqual(self.fixture.read_bytes(), before)
            result = self.copilot.apply_code_edit(offer["token"])
            self.assertEqual(result["status"], "applied")
            self.assertEqual(self.fixture.read_text(), "extends Node\nvar speed = 20\n")
            self.assertEqual(Path(result["backup_path"]).read_bytes(), before)
            with self.assertRaises(CopilotPermissionError):
                self.copilot.apply_code_edit(offer["token"])

    def test_edits_are_denied_without_distinct_edit_permission(self):
        read_only = LocalCopilot([self.root])
        with self.assertRaises(CopilotPermissionError):
            read_only.propose_code_edit(str(self.fixture), "10", "20")
        self.assertEqual(read_only.read_file(str(self.fixture))["content"].replace("\r\n", "\n"), self.fixture.read_text())

    def test_exactly_one_match_and_same_text_required(self):
        self.fixture.write_text("test\nsame\ntest\n", encoding="utf-8")
        for old, new in [("test", "changed"), ("same", "same"), ("", "something")]:
            with self.subTest(old=old):
                with self.assertRaises(CopilotPermissionError):
                    self.copilot.propose_code_edit(str(self.fixture), old, new)

    def test_out_of_scope_and_sensitive_paths_denied(self):
        protected = self.root / ".env"
        protected.write_text("SECRET=none", encoding="utf-8")
        outside = ROOT / "DO_NOT_EDIT.md"
        with self.assertRaises(CopilotPermissionError):
            self.copilot.propose_code_edit(str(protected), "SECRET", "TOKEN")
        with self.assertRaises(CopilotPermissionError):
            self.copilot.propose_code_edit(str(outside), "a", "b")

    def test_binary_or_large_file_denied(self):
        binary = self.root / "binary.py"
        binary.write_bytes(b"hello\x00world")
        large = self.root / "large.py"
        large.write_text("a" * (81 * 1024), encoding="utf-8")
        for path in (binary, large):
            with self.assertRaises(CopilotPermissionError):
                self.copilot.propose_code_edit(str(path), "a", "b")

    def test_changed_file_rejects_stale_token(self):
        offer = self.copilot.propose_code_edit(str(self.fixture), "10", "20")
        self.fixture.write_text("extends Node\nvar speed = 15\n", encoding="utf-8")
        with patch("brain_ssd.chat.code_edits._backup_dir", return_value=self.backups):
            with self.assertRaises(CopilotPermissionError):
                self.copilot.apply_code_edit(offer["token"])
        self.assertEqual(self.fixture.read_text(), "extends Node\nvar speed = 15\n")
        self.assertFalse(self.backups.exists())

    def test_token_expiry_and_forgery(self):
        offer = self.copilot.propose_code_edit(str(self.fixture), "10", "20")
        with patch("brain_ssd.chat.code_edits.time.monotonic", return_value=time.monotonic() + 180):
            with self.assertRaises(CopilotPermissionError):
                self.copilot.apply_code_edit(offer["token"])
        with self.assertRaises(CopilotPermissionError):
            self.copilot.apply_code_edit("unknown")

    def test_edit_refuses_script_execution_types(self):
        script = self.root / "run.ps1"
        script.write_text("Write-Output 'Hello'", encoding="utf-8")
        with self.assertRaises(CopilotPermissionError):
            self.copilot.propose_code_edit(str(script), "Hello", "World")

    def test_verify_reports_actual_disk_content_and_undo_is_separate(self):
        original = self.fixture.read_bytes()
        with patch("brain_ssd.chat.code_edits._backup_dir", return_value=self.backups):
            prepared = self.copilot.propose_code_edit(
                str(self.fixture), "speed = 10", "speed = 20")
            applied = self.copilot.apply_code_edit(prepared["token"])
            self.assertIn("edit_id", applied)
            verified = self.copilot.verify_code_edit(applied["edit_id"])
            self.assertEqual(verified["status"], "matches_applied_edit")
            self.assertTrue(verified["safe_to_prepare_undo"])
            self.assertEqual(self.fixture.read_text(), "extends Node\nvar speed = 20\n")
            reverse = self.copilot.propose_code_undo(applied["edit_id"])
            self.assertIn("-var speed = 20", reverse["diff"])
            self.assertIn("+var speed = 10", reverse["diff"])
            self.assertEqual(self.fixture.read_text(), "extends Node\nvar speed = 20\n")
            report = self.copilot.confirm_code_undo(reverse["token"])
            self.assertEqual(report["status"], "reverted")
            self.assertEqual(self.fixture.read_bytes(), original)
            with self.assertRaises(CopilotPermissionError):
                self.copilot.confirm_code_undo(reverse["token"])
            with self.assertRaises(CopilotPermissionError):
                self.copilot.verify_code_edit(applied["edit_id"])

    def test_undo_blocked_if_another_editor_changed_the_file(self):
        with patch("brain_ssd.chat.code_edits._backup_dir", return_value=self.backups):
            offer = self.copilot.propose_code_edit(str(self.fixture), "10", "20")
            applied = self.copilot.apply_code_edit(offer["token"])
            self.fixture.write_text("extends Node\nvar speed = 100\n", encoding="utf-8")
            verified = self.copilot.verify_code_edit(applied["edit_id"])
            self.assertEqual(verified["status"], "changed_since_apply")
            self.assertFalse(verified["safe_to_prepare_undo"])
            with self.assertRaises(CopilotPermissionError):
                self.copilot.propose_code_undo(applied["edit_id"])
            self.assertIn("100", self.fixture.read_text())

    def test_undo_confirm_checks_current_file_again(self):
        with patch("brain_ssd.chat.code_edits._backup_dir", return_value=self.backups):
            prepared = self.copilot.propose_code_edit(str(self.fixture), "10", "20")
            applied = self.copilot.apply_code_edit(prepared["token"])
            undo = self.copilot.propose_code_undo(applied["edit_id"])
            self.fixture.write_text("extends Node\nvar speed = 30\n", encoding="utf-8")
            with self.assertRaises(CopilotPermissionError):
                self.copilot.confirm_code_undo(undo["token"])
            self.assertIn("30", self.fixture.read_text())

    def test_undo_rejects_altered_backup_and_fake_token(self):
        with patch("brain_ssd.chat.code_edits._backup_dir", return_value=self.backups):
            prepared = self.copilot.propose_code_edit(str(self.fixture), "10", "20")
            applied = self.copilot.apply_code_edit(prepared["token"])
            backup = Path(applied["backup_path"])
            backup.write_text("tampered", encoding="utf-8")
            with self.assertRaises(CopilotPermissionError):
                self.copilot.propose_code_undo(applied["edit_id"])
            with self.assertRaises(CopilotPermissionError):
                self.copilot.confirm_code_undo("forged")
            self.assertIn("20", self.fixture.read_text())

    def test_only_latest_edit_is_undoable_in_session(self):
        with patch("brain_ssd.chat.code_edits._backup_dir", return_value=self.backups):
            a = self.copilot.propose_code_edit(str(self.fixture), "10", "20")
            first = self.copilot.apply_code_edit(a["token"])
            b = self.copilot.propose_code_edit(str(self.fixture), "20", "30")
            second = self.copilot.apply_code_edit(b["token"])
            with self.assertRaises(CopilotPermissionError):
                self.copilot.propose_code_undo(first["edit_id"])
            self.assertTrue(
                self.copilot.verify_code_edit(second["edit_id"])["safe_to_prepare_undo"])

    def test_undo_requires_edit_permission_and_expires(self):
        denied = LocalCopilot([self.root])
        with self.assertRaises(CopilotPermissionError):
            denied.verify_code_edit("anything")
        with patch("brain_ssd.chat.code_edits._backup_dir", return_value=self.backups):
            a = self.copilot.propose_code_edit(str(self.fixture), "10", "20")
            edit = self.copilot.apply_code_edit(a["token"])
            from brain_ssd.chat import code_edits
            with patch.object(code_edits.time, "monotonic", return_value=1e20):
                with self.assertRaises(CopilotPermissionError):
                    self.copilot.propose_code_undo(edit["edit_id"])

    def test_bom_preserved(self):
        self.fixture.write_bytes(b"\xef\xbb\xbf" + "var nome = 1\n".encode())
        with patch("brain_ssd.chat.code_edits._backup_dir", return_value=self.backups):
            offer = self.copilot.propose_code_edit(str(self.fixture), "nome = 1", "nome = 2")
            self.copilot.apply_code_edit(offer["token"])
        self.assertTrue(self.fixture.read_bytes().startswith(b"\xef\xbb\xbf"))


if __name__ == "__main__":
    unittest.main()
