"""Model-free regression: GameDev v2 requires real evidence and safe proposals."""
from __future__ import annotations
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from brain_ssd.chat.game_agent_v2 import (
    FileTask,STAGE_TASKS,draft_prompt,inspect_generated,run_generation_session,stage_plan
)


HTML='<!doctype html><html lang="pt-BR"><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>Luna</title></head><body><main><canvas id="game"></canvas></main></body></html>'
CSS='body{background:#112}button{color:white}button:focus-visible{outline:2px solid gold}@media(max-width:600px){body{padding:2px}}'
JS='const canvas=document.getElementById("game");const player={x:0};function step(){if (window.ArrowRight && window.ArrowLeft && window.Space){player.x++}requestAnimationFrame(step)}requestAnimationFrame(step);'


def proposal(path:str,content:str):
    return json.dumps({"version":1,"goal":"protótipo original","files":[{"path":path,"content":content}]},ensure_ascii=False)


class GameAgentV2Tests(unittest.TestCase):
    def test_stages_and_prompt_budgets(self):
        self.assertEqual(tuple(STAGE_TASKS),("s0-plan","s1-movement"))
        self.assertEqual(len(stage_plan("s0-plan")),2)
        self.assertEqual(len(stage_plan("s1-movement")),1)
        with self.assertRaises(ValueError):
            stage_plan("s9-fake")
        prompt=draft_prompt(stage_plan("s0-plan")[0])
        self.assertIn("/no_think",prompt)
        self.assertIn("index.html",prompt)
        self.assertIn('"files"',prompt)
        self.assertIn("JSON",prompt)
        with self.assertRaises(ValueError):
            draft_prompt(stage_plan("s0-plan")[0],context="x"*2000)

    def test_accepts_syntax_only_html_css_and_js(self):
        cases=[("s0-plan",0,HTML),("s0-plan",1,CSS),("s1-movement",0,JS)]
        for stage,idx,code in cases:
            task=stage_plan(stage)[idx]
            with self.subTest(path=task.path):
                if task.path.endswith(".js") and not shutil.which("node"):
                    continue
                ok,reason,source=inspect_generated(task,proposal(task.path,code))
                self.assertTrue(ok,reason)
                self.assertEqual(source,code)

    def test_rejects_unsafe_code_or_false_file_path(self):
        task=stage_plan("s0-plan")[0]
        self.assertFalse(inspect_generated(task,"hello")[0])
        self.assertFalse(inspect_generated(task,proposal("other.html",HTML))[0])
        self.assertFalse(inspect_generated(task,proposal("index.html","<main/>"))[0])
        js=stage_plan("s1-movement")[0]
        bad=JS+"fetch('https://example.org')"
        with patch("brain_ssd.chat.game_agent_v2.check_js_syntax",return_value=True):
            self.assertEqual(inspect_generated(js,proposal(js.path,bad))[1],"disallowed_dynamic_code_or_network")

    def test_multi_file_session_stages_not_applied_or_executed(self):
        replies=[proposal("index.html",HTML),proposal("styles.css",CSS)]
        calls=[]
        def mock_infer(prompt,max_tokens):
            calls.append((prompt,max_tokens))
            return {"answer":replies.pop(0),"model_generated":True}
        with tempfile.TemporaryDirectory() as dirname:
            before=list(Path(dirname).iterdir())
            result=run_generation_session(mock_infer,"s0-plan",include_code=False)
            self.assertEqual(result["status"],"CANDIDATE_FOR_HUMAN_REVIEW")
            self.assertEqual(result["accepted_paths"],["index.html","styles.css"])
            self.assertEqual(result["model_inference_attempts"],2)
            self.assertNotIn("proposal",result)
            self.assertFalse(result["code_executed"])
            self.assertFalse(result["gameplay_verified"])
            self.assertFalse(result["workspace_modified"])
            self.assertEqual(before,list(Path(dirname).iterdir()))
            self.assertEqual(len(calls),2)

    def test_retry_explicitly_uses_feedback_and_persists_only_in_result(self):
        responses=["not_json",proposal("index.html",HTML),proposal("styles.css",CSS)]
        seen=[]
        def model(prompt,max_tokens):
            seen.append(prompt)
            return {"answer":responses.pop(0),"model_generated":True}
        result=run_generation_session(model,"s0-plan",attempts_per_file=2,include_code=True)
        self.assertEqual(result["status"],"CANDIDATE_FOR_HUMAN_REVIEW")
        self.assertEqual(result["model_inference_attempts"],3)
        self.assertIn("Diagnóstico anterior",seen[1])
        self.assertEqual(len(result["proposal"]["files"]),2)

    def test_no_canned_fallback_and_strict_end_detection(self):
        def fake_model(_prompt,_tokens):
            return {"answer":proposal("index.html",HTML),"model_generated":False}
        r=run_generation_session(fake_model,"s0-plan",attempts_per_file=1)
        self.assertEqual(r["status"],"INCOMPLETE")
        self.assertEqual(r["model_inference_attempts"],0)
        self.assertEqual(r["accepted_paths"],[])
        def native_limit(_prompt,_tokens):
            return {"answer":proposal("index.html",HTML),"model_generated":True,"finish_reason":"length"}
        r=run_generation_session(native_limit,"s0-plan",attempts_per_file=1)
        self.assertEqual(r["status"],"INCOMPLETE")
        self.assertEqual(r["checks"][0]["attempts"][0]["status"],"native_token_limit")

    def test_invalid_attempt_budget(self):
        for amount in (0,4):
            with self.assertRaises(ValueError):
                run_generation_session(lambda *_: {}, "s0-plan",attempts_per_file=amount)


if __name__=="__main__":
    unittest.main()
