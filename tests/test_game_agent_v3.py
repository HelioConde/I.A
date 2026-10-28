"""Game Agent v3 regression and safety tests without any GGUF."""
from __future__ import annotations
import shutil
from unittest import mock
import sys
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from brain_ssd.chat.game_agent_v3 import (
    CHECKS, GOAL, strip_code_wrapper, inspect_code, coding_prompt, run_native_game_js_trial
)

GOOD = '''
const canvas = document.getElementById("game");
const ctx = canvas.getContext("2d");
const player = {x:20,y:380,vy:0};
const keys = new Set();
window.addEventListener("keydown",e=>keys.add(e.code));
window.addEventListener("keyup",e=>keys.delete(e.code));
function draw(){
  if(keys.has("ArrowRight")) player.x+=2;
  if(keys.has("ArrowLeft")) player.x-=2;
  if(keys.has("Space")) player.vy=-8;
  player.y+=player.vy; player.vy+=.5;
  ctx.clearRect(0,0,800,480);ctx.fillRect(player.x,player.y,30,40);
  requestAnimationFrame(draw);
}
requestAnimationFrame(draw);
'''.strip()


class V3Tests(unittest.TestCase):
    def test_prompt_mentions_genuine_canvas_gameplay_without_json(self):
        prompt=coding_prompt()
        self.assertIn("SOMENTE código-fonte",prompt)
        self.assertIn("/no_think",prompt)
        self.assertNotIn('{"version":',prompt)
        self.assertIn("requestAnimationFrame",prompt)
        self.assertIn("javascript_syntax_error",coding_prompt("javascript_syntax_error"))

    def test_safe_wrapper_and_rejects_explanations(self):
        tick=chr(96)*3
        self.assertEqual(strip_code_wrapper(tick+"js\n"+GOOD+"\n"+tick),GOOD)
        for bad in ("",tick+"js\n"+GOOD,"<think>hmm</think>"+GOOD,
                    '<script>'+GOOD+'</script>'):
            with self.subTest(bad=bad[:18]):
                with self.assertRaises(ValueError):
                    strip_code_wrapper(bad)

    def test_static_syntax_and_required_terms(self):
        if not shutil.which("node"):self.skipTest("Node unavailable")
        result=inspect_code(GOOD)
        self.assertTrue(result["accepted"],result["reason"])
        self.assertEqual(result["source"],GOOD)
        invalid=inspect_code(GOOD+"const x = {")
        self.assertEqual(invalid["reason"],"javascript_syntax_error")

    def test_rejects_missing_gameplay_network_and_runtime_hooks(self):
        with mock.patch("brain_ssd.chat.game_agent_v3.check_js_syntax",return_value=True):
            self.assertEqual(inspect_code("const x=1",syntax_check=lambda _:True)["reason"],"missing_game_features")
            self.assertEqual(inspect_code(GOOD+"fetch('/x')",syntax_check=lambda _:True)["reason"],"prohibited_api")
            self.assertEqual(inspect_code(GOOD+"eval('x')",syntax_check=lambda _:True)["reason"],"prohibited_api")

    def test_model_inference_and_retry_never_fabricated(self):
        if not shutil.which("node"):self.skipTest("Node unavailable")
        prompts=[]
        replies=["Javascript cannot be generated",GOOD]
        def generate(prompt,tokens):
            prompts.append((prompt,tokens))
            return {"answer":replies.pop(0),"model_generated":True}
        trial=run_native_game_js_trial(generate,attempts=2,save_source=True)
        self.assertEqual(trial["status"],"CANDIDATE_FOR_HUMAN_REVIEW")
        self.assertTrue(trial["accepted_source"])
        self.assertEqual(trial["source"],GOOD)
        self.assertEqual(trial["attempt_count"],2)
        self.assertIn("Diagnóstico",prompts[1][0])
        self.assertTrue(all(tokens==1200 for _,tokens in prompts))
        self.assertFalse(trial["code_executed"])
        self.assertFalse(trial["gameplay_verified"])

    def test_unverified_model_even_valid_code_is_not_accepted(self):
        trial=run_native_game_js_trial(lambda *_:{"answer":GOOD,"model_generated":False},attempts=1)
        self.assertFalse(trial["accepted_source"])
        self.assertEqual(trial["attempts"][0]["reason"],"not_real_inference")

    def test_native_limit_rejects_even_valid_code(self):
        trial=run_native_game_js_trial(lambda *_:{"answer":GOOD,"model_generated":True,
                                                "finish_reason":"length"},attempts=1)
        self.assertFalse(trial["accepted_source"])
        self.assertEqual(trial["attempts"][0]["reason"],"native_token_limit")

    def test_bad_attempt_count_and_no_source_on_failure(self):
        with self.assertRaises(ValueError):
            run_native_game_js_trial(lambda *_: {},attempts=0)
        r=run_native_game_js_trial(lambda *_: {"answer":"xx","model_generated":True},attempts=1,save_source=True)
        self.assertNotIn("source",r)


if __name__=="__main__":
    unittest.main()
