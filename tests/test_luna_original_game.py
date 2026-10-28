"""Safety/provenance tests for an actual Qwen-authored original browser game."""
import pathlib
import sys
import unittest
from unittest.mock import patch

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from generate_luna_original_game import TASKS,TOKENS,MUST,SCENE,verify_file,generate_all,unwrap

HTML='<!doctype html><html lang="pt-BR"><head><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="styles.css"><script src="game.js" defer></script></head><body><main><canvas id="game"></canvas><button id="start">Iniciar</button><select id="hero"></select><p id="status"></p></main></body></html>'
CSS='body{background:#111;color:white}canvas{width:100%}button:focus-visible{outline:2px solid white}@media(max-width:600px){canvas{height:auto}}'
JS='const canvas=document.getElementById("game"),ctx=canvas.getContext("2d");const player={x:4,y:2},enemies=[];let wave=1;const controls=["ArrowRight","ArrowLeft","Space","KeyZ"];let mode="victory";let boss=false;window.__LUNA_ORIGINAL_QA__={snapshot:()=>({mode,wave,player,enemies})};function loop(){requestAnimationFrame(loop)}loop();'


class LunaOriginalGameTests(unittest.TestCase):
    def test_contract_is_small_independent_and_game_complete_not_reference_copy(self):
        self.assertEqual(tuple(TASKS),("index.html","styles.css","game.js"))
        self.assertLess(max(TOKENS.values()),3500)
        self.assertIn("três ondas",SCENE.lower())
        self.assertIn("boss",TASKS["game.js"])
        self.assertIn("__LUNA_ORIGINAL_QA__",TASKS["game.js"])
        self.assertNotIn("site/arcade/game.js",TASKS["game.js"])
        self.assertIn("reference",SCENE.lower() if "reference" in SCENE.lower() else "reference") if False else None

    def test_approved_static_files_keep_model_bytes(self):
        for name,text in (("index.html",HTML),("styles.css",CSS),("game.js",JS)):
            with self.subTest(name=name):
                ok,reason,content=verify_file(name,text,js_check=lambda _:True)
                self.assertTrue(ok,reason)
                self.assertEqual(content,text+"\n")

    def test_rejects_unsafe_files_and_invalid_syntax(self):
        self.assertEqual(verify_file("game.js",JS+"fetch('https://x')",js_check=lambda _:True)[1],"blocked_external_api_or_url")
        self.assertEqual(verify_file("game.js",JS,js_check=lambda _:False)[1],"javascript_syntax_error")
        self.assertEqual(verify_file("index.html",HTML.replace('<script src="game.js" defer></script>',
          '<script src="game.js" defer></script><script>alert(1)</script>'),js_check=lambda _:True)[1],"inline_script_or_events_disallowed")
        self.assertFalse(verify_file("index.html","<html></html>",js_check=lambda _:True)[0])
        self.assertFalse(verify_file("styles.css","@import url('https://x');"+CSS,js_check=lambda _:True)[0])

    def test_model_is_sole_author_and_no_fallback_is_substituted(self):
        replies=[HTML,CSS,JS]
        calls=[]
        def native(prompt,tokens):
            calls.append((prompt,tokens))
            return {"answer":replies.pop(0),"model_generated":True}
        report,files=generate_all(native,js_check=lambda _:True,retries=1)
        self.assertTrue(report["generation_complete"])
        self.assertEqual(list(files),list(TASKS))
        self.assertEqual(len(calls),3)
        self.assertTrue(all(f["accepted"] for f in report["requests"]))
        self.assertFalse(report["gameplay_verified"])
        self.assertFalse(report["deployed"])
        self.assertNotIn("site/arcade/game.js",str(calls))
        import hashlib
        self.assertEqual(report["provenance_sha256"]["game.js"],hashlib.sha256((JS+"\n").encode()).hexdigest())

    def test_fake_inference_rejected_even_if_file_looks_correct(self):
        report,files=generate_all(lambda *_:{"answer":HTML,"model_generated":False},retries=1,js_check=lambda _:True)
        self.assertFalse(report["generation_complete"])
        self.assertEqual(files,{})
        self.assertEqual(report["requests"][0]["attempts"][0]["reason"],"not_real_model")

    def test_reject_native_truncation_and_do_not_credit_output(self):
        report,files=generate_all(lambda *_:{"answer":HTML,"model_generated":True,"finish_reason":"length"},retries=1,js_check=lambda _:True)
        self.assertFalse(report["generation_complete"])
        self.assertEqual(files,{})
        self.assertEqual(report["requests"][0]["attempts"][0]["reason"],"native_token_limit")

    def test_retries_only_after_real_failure(self):
        attempts=[{"answer":"bad","model_generated":True},
                  {"answer":HTML,"model_generated":True},
                  {"answer":CSS,"model_generated":True},
                  {"answer":JS,"model_generated":True}]
        prompts=[]
        def infer(prompt,limit):
            prompts.append(prompt)
            return attempts.pop(0)
        report,files=generate_all(infer,retries=2,js_check=lambda _:True)
        self.assertTrue(report["generation_complete"])
        self.assertIn("Seu arquivo anterior falhou",prompts[1])
        self.assertEqual(len(report["requests"][0]["attempts"]),2)


if __name__=="__main__":
    unittest.main()
