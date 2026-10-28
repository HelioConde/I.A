"""Model-free tests of the GameDev AI coding benchmark's safety and scoring."""
from __future__ import annotations
import json
from pathlib import Path
import shutil
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))

from brain_ssd.chat.game_coding_trial import (
    FIXED_TASK, evaluate_model_answer, check_js_syntax, run_coding_trial,
)


CODE="const HERO_CLASSES={melee:{hp:150,damage:27,speed:300},ranged:{hp:100,damage:23,speed:320},magic:{hp:90,damage:33,speed:280}};"
GOOD=json.dumps({"version":1,"goal":"três classes originais","files":[{"path":"src/classes.js","content":CODE}]})


class DummyEngine:
    def __init__(self,replies,verified=True):
        self.replies=list(replies)
        self.verified=verified
        self.calls=0

    def ask(self,prompt,history,*,response_tokens):
        assert response_tokens==256
        assert not history
        assert "HERO_CLASSES" in prompt
        self.calls+=1
        text=self.replies.pop(0)
        return {"answer":text,"mode":"experimental_chat","generation_status":"unverified"}

    def status(self):
        return {"inference_verified":self.verified}


class GameCodingTests(unittest.TestCase):
    def test_benchmark_prompt_is_synthetic_and_bounded(self):
        self.assertIn("classes.js",FIXED_TASK)
        self.assertIn("JSON",FIXED_TASK)
        self.assertLess(len(FIXED_TASK.encode("utf-8")),2500)

    def test_accepts_valid_single_file_and_never_runs_it(self):
        score=evaluate_model_answer(GOOD,model_generated=True,syntax_checker=lambda code:code==CODE)
        self.assertTrue(score.accepted)
        self.assertTrue(score.schema_valid)
        self.assertTrue(score.code_syntax_valid)
        self.assertTrue(all(score.semantic_terms.values()))

    def test_rejects_local_commands_truncated_and_incomplete(self):
        result=evaluate_model_answer(GOOD,model_generated=False,syntax_checker=lambda _code:True)
        self.assertFalse(result.accepted)
        result=evaluate_model_answer(GOOD,model_generated=True,generation_status="truncated",syntax_checker=lambda _code:True)
        self.assertFalse(result.accepted)
        for raw in ('{"version":1', "<think>reasoning</think>", "{}"):
            self.assertFalse(evaluate_model_answer(raw,model_generated=True,syntax_checker=lambda _code:True).accepted)

    def test_rejects_wrong_path_and_missing_semantics(self):
        wrong=json.dumps({"version":1,"goal":"x","files":[{"path":"src/other.js","content":CODE}]})
        self.assertFalse(evaluate_model_answer(wrong,model_generated=True,syntax_checker=lambda _code:True).accepted)
        incomplete=json.dumps({"version":1,"goal":"x","files":[{"path":"src/classes.js","content":"const HERO_CLASSES = {}"}]})
        self.assertFalse(evaluate_model_answer(incomplete,model_generated=True,syntax_checker=lambda _code:True).accepted)

    def test_attempts_stop_on_first_valid_model_output(self):
        if not shutil.which("node"):
            self.skipTest("Node needed for actual syntax-only test")
        engine=DummyEngine(["not json",GOOD,"unused"])
        result=run_coding_trial(engine,trials=3)
        self.assertEqual(result["status"],"PASS")
        self.assertEqual(result["attempt_count"],2)
        self.assertTrue(result["accepted_model_proposal"])
        self.assertEqual(engine.calls,2)
        self.assertEqual(result["attempts"][0]["reason"],"malformed_proposal")

    def test_no_inference_does_not_pass_even_with_valid_code(self):
        engine=DummyEngine([GOOD],verified=False)
        result=run_coding_trial(engine,trials=1)
        self.assertEqual(result["status"],"FAIL")
        self.assertFalse(result["attempts"][0]["model_generated"])

    def test_node_check_never_executes_candidate(self):
        if not shutil.which("node"):
            self.skipTest("Node not installed")
        source="throw Error('should not run'); "+CODE
        self.assertTrue(check_js_syntax(source))
        self.assertFalse(check_js_syntax("const HERO_CLASSES = {"))


if __name__=="__main__":
    unittest.main()
