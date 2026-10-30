"""Regression tests for Luna's first ORIGINAL Lua game-code training set."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE=Path(__file__).resolve().parents[1]/"experiments"/"luna-forge-zero"
spec=importlib.util.spec_from_file_location("original_lua_lessons",HERE/"original_lua_lessons.py")
curriculum=importlib.util.module_from_spec(spec)
spec.loader.exec_module(curriculum)

class OriginalLuaLessonsTest(unittest.TestCase):
    def test_six_approved_original_mechanics_and_separate_holdouts(self):
        report=curriculum.verify()
        self.assertEqual(report["lua_training_lessons"],6)
        self.assertEqual(report["heldout_questions_without_answers"],3)
        self.assertEqual(report["commercial_lua_training_files"],0)
        self.assertEqual(report["commercial_lua_files_opened"],0)
        examples=curriculum.lessons()
        self.assertEqual({t["id"] for t in examples},set(curriculum.LESSONS))
        self.assertEqual(set(x["id"] for x in curriculum.HOLDOUT)&set(x["id"] for x in examples),set())
        self.assertTrue(all(x["split"]=="train" and x["language"]=="lua" for x in examples))

    def test_export_contains_original_code_only_and_is_immutable(self):
        with tempfile.TemporaryDirectory(dir=HERE) as temp:
            dest=Path(temp)/"lessons.jsonl"
            result=curriculum.export(dest)
            self.assertEqual(result["exported_holdout_answers"],0)
            rows=[json.loads(l) for l in dest.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(rows),6)
            self.assertTrue(all("function Game." in x["code"] for x in rows))
            self.assertTrue(all("luna-authored" in x["provenance"].lower() for x in rows))
            with self.assertRaises(FileExistsError):
                curriculum.export(dest)

    def test_cannot_export_outside_experiment(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError,"inside"):
                curriculum.export(Path(temp)/"leaked.jsonl")

    def test_no_unreviewed_lua_files_scan(self):
        self.assertEqual(curriculum.SOURCE.name,"original_lua_gameplay.lua")
        self.assertEqual(curriculum.SOURCE.parent.resolve(),HERE.resolve())
        self.assertFalse(any("grand chase files" in str(x).lower() for x in (curriculum.SOURCE,)))

if __name__=="__main__": unittest.main()
