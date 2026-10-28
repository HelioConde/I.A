"""Code Studio regression: malformed output, opt-in writes, no code execution."""
from __future__ import annotations
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from brain_ssd.chat.code_studio import (
    ProposalError, apply_new_files, parse_proposal, review_proposal, validate_path,
)


def example(files=None):
    return {"version": 1, "goal": "Projeto exemplo com Python", "files": files or [
        {"path": "src/main.py", "content": "print('Olá mundo')\n"},
        {"path": "README.md", "content": "# Exemplo\n"},
    ]}


class CodeStudioTests(unittest.TestCase):
    def test_complete_proposal_validates_and_reviews(self):
        data = parse_proposal(json.dumps(example(), ensure_ascii=False))
        report = review_proposal(data)
        self.assertEqual(report["file_count"], 2)
        self.assertEqual(report["syntax_errors"], 0)
        self.assertEqual(report["status"], "READY_FOR_HUMAN_REVIEW")

    def test_json_fenced_output(self):
        fence = chr(96) * 3
        data = parse_proposal(fence + "json\n" + json.dumps(example()) + "\n" + fence)
        self.assertEqual(data["version"], 1)

    def test_invalid_output_and_internal_reasoning_rejected(self):
        for raw in ('{"version":1,"files":[]}', '{"version":1,"goal":"x","files":[}',
                    '<think>private</think>\n{"version":1}',
                    json.dumps({"version": 2, "goal": "x", "files": []})):
            with self.subTest(raw=raw[:25]):
                with self.assertRaises(ProposalError):
                    parse_proposal(raw)

    def test_reject_escape_hidden_system_and_windows_reserved_names(self):
        bad_paths = [
            "../app.py", "folder/../app.py", "./app.py", "/tmp/a.py",
            "C:/temp/a.py", "folder\\app.py", ".env", ".github/workflows/evil.yml",
            "node_modules/h.js", "results/secret.json", "foo//bar.js",
            "CON.txt", "src/com1.ts", "folder/.secrets.py",
            "src/evil.exe", "folder/name. ", "src/sneaky.py/",
        ]
        for path in bad_paths:
            with self.subTest(path=path):
                with self.assertRaises(ProposalError):
                    validate_path(path)

    def test_prevent_duplicate_name_case_insensitive_and_oversized(self):
        duplicate = example([
            {"path": "App.js", "content": "let n=1;"},
            {"path": "app.js", "content": "let n=2;"},
        ])
        with self.assertRaises(ProposalError):
            parse_proposal(json.dumps(duplicate))
        large = example([{"path": "a.js", "content": "a" * 48001}])
        with self.assertRaises(ProposalError):
            parse_proposal(json.dumps(large))

    def test_static_errors_are_blocking_no_execution(self):
        source = "raise RuntimeError('code should NEVER run in review')\n"
        safe = example([{"path": "main.py", "content": source}])
        self.assertEqual(review_proposal(safe)["status"], "READY_FOR_HUMAN_REVIEW")
        unsafe = example([{"path": "main.py", "content": "def fn(:\n"}])
        self.assertEqual(review_proposal(unsafe)["status"], "BLOCKED")

    def test_html_and_css_design_checks_are_hints_not_fake_audits(self):
        data = example([
            {"path": "index.html", "content": "<html><body><p>Oi</p></body></html>"},
            {"path": "style.css", "content": "body{color:#333}"},
        ])
        report = review_proposal(data)
        self.assertEqual(report["status"], "READY_FOR_HUMAN_REVIEW")
        self.assertGreater(len(report["files"][0]["suggestions"]), 0)
        self.assertGreater(len(report["files"][1]["suggestions"]), 0)
        self.assertIn("não executou código", report["warning"])

    def test_apply_requires_approval_creates_new_only(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data = example()
            with self.assertRaises(PermissionError):
                apply_new_files(data, root)
            self.assertFalse((root / "src").exists())
            paths = apply_new_files(data, root, approved=True)
            self.assertEqual(paths, ["src/main.py", "README.md"])
            self.assertEqual((root / "src/main.py").read_text(encoding="utf-8"), "print('Olá mundo')\n")
            with self.assertRaises(ProposalError):
                apply_new_files(data, root, approved=True)

    def test_no_partial_apply_when_target_exists(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "README.md").write_text("original", encoding="utf-8")
            with self.assertRaises(ProposalError):
                apply_new_files(example(), root, approved=True)
            self.assertEqual((root / "README.md").read_text(encoding="utf-8"), "original")
            self.assertFalse((root / "src").exists())

    def test_block_symlinks_in_workspace(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "real").mkdir()
            try:
                (root / "src").symlink_to(root / "real", target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("Symlinks unavailable for this Windows runner")
            with self.assertRaises(ProposalError):
                apply_new_files(example(), root, approved=True)
            self.assertEqual(list((root / "real").iterdir()), [])

    def test_stages_and_weights_are_valid(self):
        brief = json.loads((ROOT / "benchmarks/arcade_s1/brief.json").read_text(encoding="utf-8"))
        self.assertEqual(brief["benchmark_version"], 1)
        self.assertEqual(sum(brief["scoring"].values()), 100)
        ids = [stage["id"] for stage in brief["stages"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("s7-capstone", ids)
        self.assertGreaterEqual(len(brief["graduation"]["hard_gates"]), 5)

    def test_milestone_prompt_has_contract_and_does_not_claim_work_done(self):
        from tools.code_studio import make_prompt
        brief = json.loads((ROOT / "benchmarks/arcade_s1/brief.json").read_text(encoding="utf-8"))
        prompt = make_prompt(brief, "s1-movement")
        self.assertIn('"files"', prompt)
        self.assertIn("saltar", prompt)
        self.assertIn("ORIGINAL", prompt)
        with self.assertRaises(ProposalError):
            make_prompt(brief, "not-a-stage")


if __name__ == "__main__":
    unittest.main()
