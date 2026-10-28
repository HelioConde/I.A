"""Offline regression tests for Luna's first model-authored reference-game patch."""
from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))

from brain_ssd.chat.game_outperform_v1 import (
    BUGGY_LINE,TASK,validate_candidate,run_first_fix,node_syntax
)

GOOD="const end=e=>{e.preventDefault();keys.delete(code)};"
SOURCE="(()=>{'use strict';const code='ArrowRight';"+BUGGY_LINE+"})();"


class OutperformTests(unittest.TestCase):
    def test_real_reference_has_known_bug_initially(self):
        reference=(ROOT/"site"/"arcade"/"game.js").read_text(encoding="utf-8")
        self.assertEqual(reference.count(BUGGY_LINE),1)
        self.assertIn("touchDown=false",reference)

    def test_bounded_task_contains_real_input_and_requires_unchanged_input_cleanup(self):
        self.assertIn(BUGGY_LINE,TASK)
        self.assertIn("keys.delete(code)",TASK)
        self.assertIn("ReferenceError",TASK)

    def test_valid_model_authored_candidate_can_be_reviewed(self):
        self.assertEqual(validate_candidate(GOOD,SOURCE,lambda code:True),(True,"candidate_requires_browser_review"))
        if shutil.which("node"):
            self.assertTrue(validate_candidate(GOOD,SOURCE,node_syntax)[0])

    def test_rejects_unsafe_or_changed_patches(self):
        for value in (
            BUGGY_LINE,
            "const end=e=>{};",
            "const end=e=>{e.preventDefault();keys.delete(code);touchDown=false};",
            "const end=e=>{eval('1');keys.delete(code);};",
            "const end=e=>{e.preventDefault();keys.delete(code)};\nconsole.log('evil')",
            "const end=e=>{e.preventDefault();keys.delete(code);window.x=1};",
        ):
            with self.subTest(value=value[:35]):
                self.assertFalse(validate_candidate(value,SOURCE,lambda _:True)[0])
        self.assertEqual(validate_candidate(GOOD,SOURCE.replace(BUGGY_LINE,"unrelated"),
                                            lambda _:True)[1],"reference_source_changed")
        self.assertEqual(validate_candidate(GOOD,SOURCE,lambda _:False)[1],"javascript_syntax_error")

    def test_two_real_outputs_retry_then_pass_only_if_actual_model(self):
        replies=[{"answer":"Let me think","model_generated":True},
                 {"answer":GOOD,"model_generated":True}]
        prompts=[]
        def infer(prompt,tokens):
            prompts.append((prompt,tokens))
            return replies.pop(0)
        result=run_first_fix(SOURCE,infer,attempts=2,checker=lambda _:True)
        self.assertEqual(result["status"],"CANDIDATE_FOR_REVIEW")
        self.assertEqual(result["model_authored_line"],GOOD)
        self.assertEqual(result["attempts"][0]["accepted"],False)
        self.assertEqual(len(prompts),2)
        self.assertIn("Tentativa anterior recusada",prompts[1][0])
        self.assertEqual(prompts[0][1],210)
        self.assertFalse(result["gameplay_improvement_verified"])
        self.assertFalse(result["baseline_modified"])
        self.assertFalse(result["code_executed"])

    def test_fake_output_cannot_be_credited(self):
        result=run_first_fix(SOURCE,lambda *_:{"answer":GOOD,"model_generated":False},
                             attempts=1,checker=lambda _:True)
        self.assertEqual(result["status"],"INCOMPLETE")
        self.assertIsNone(result["model_authored_line"])
        self.assertEqual(result["attempts"][0]["reason"],"not_real_model")

    def test_truncation_disqualifies_candidate(self):
        result=run_first_fix(SOURCE,lambda *_:{"answer":GOOD,"model_generated":True,
                                                  "finish_reason":"length"},
                             attempts=1,checker=lambda _:True)
        self.assertEqual(result["status"],"INCOMPLETE")
        self.assertEqual(result["attempts"][0]["reason"],"token_limit")


if __name__=="__main__":
    unittest.main()
