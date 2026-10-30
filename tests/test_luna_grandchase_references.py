"""Regression checks for a safe, clean-room action-game learning curriculum."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]/"experiments"/"luna-forge-zero"
spec=importlib.util.spec_from_file_location("gc_gate",ROOT/"grandchase_reference_gate.py")
gate=importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

class GrandChaseReferenceGateTests(unittest.TestCase):
    def test_nine_repositories_licensed_or_quarantined(self):
        result=gate.verify()
        self.assertEqual(result["audited_repositories"],9)
        self.assertEqual(result["raw_grandchase_sources_in_training"],0)
        self.assertEqual(result["original_training_tasks"],8)
        self.assertEqual(result["unseen_evaluation_tasks"],4)

    def test_no_proprietary_answers_ever_exported(self):
        with tempfile.TemporaryDirectory() as temp:
            dest=Path(temp)/"approved.jsonl"
            report=gate.export_training(dest)
            self.assertEqual(report["holdout_exported"],0)
            examples=[json.loads(line) for line in dest.read_text().splitlines()]
            self.assertEqual(len(examples),8)
            self.assertTrue(all(r["provenance"]=="Luna original authored example" for r in examples))
            self.assertTrue(all(r["split"]=="train" for r in examples))
            self.assertFalse(any("GrandChase" in r["code"] for r in examples))
            with self.assertRaises(FileExistsError):
                gate.export_training(dest)

    def test_fail_closed_on_repository_admission(self):
        with tempfile.TemporaryDirectory() as temp:
            sources=json.loads(gate.CATALOG.read_text(encoding="utf-8"))
            sources["repositories"][1]["include_raw_code_in_training"]=True
            temp_path=Path(temp)/"catalog.json"
            temp_path.write_text(json.dumps(sources),encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"cannot enter training"):
                gate.verify(catalog=temp_path)

    def test_fail_closed_if_holdout_answer_is_added(self):
        with tempfile.TemporaryDirectory() as temp:
            curriculum=json.loads(gate.CURRICULUM.read_text(encoding="utf-8"))
            next(t for t in curriculum["tasks"] if t["split"]=="holdout")["reference_solution"]="function leaked() { return true; }"
            path=Path(temp)/"curriculum.json"
            path.write_text(json.dumps(curriculum),encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"Holdout tasks"):
                gate.verify(curriculum=path)

    def test_original_javascript_train_syntax(self):
        if not shutil.which("node"):
            self.skipTest("node is not installed")
        tasks=json.loads(gate.CURRICULUM.read_text(encoding="utf-8"))["tasks"]
        for task in tasks:
            if task["split"]!="train" or task["language"]!="javascript":
                continue
            with self.subTest(task=task["id"]), tempfile.TemporaryDirectory() as temp:
                path=Path(temp)/"code.js"
                path.write_text(task["reference_solution"],encoding="utf-8")
                proc=subprocess.run(["node","--check",str(path)],capture_output=True,text=True,timeout=5)
                self.assertEqual(proc.returncode,0,proc.stderr)

if __name__=="__main__":
    unittest.main()
