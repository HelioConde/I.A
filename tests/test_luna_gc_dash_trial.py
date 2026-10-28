"""Unit-level constraints: only native-model pieces may modify the game."""
from pathlib import Path
import sys,unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from luna_gc_s1_dash_trial import TASKS,run,valid_piece

BASE="""let attackTarget = null;
document.addEventListener('keydown',(e)=>{
 if(e.key==='ArrowRight'){player.vx = 5;}
 else if(e.key==='ArrowLeft'){player.vx = -5;}
});
"""
EXAMPLE=[
 "let lastRightTap = 0, lastLeftTap = 0;",
 "const t = performance.now(); player.vx = !e.repeat && t-lastRightTap<=260 ? 14 : 5; if(!e.repeat)lastRightTap=t;",
 "const t = performance.now(); player.vx = !e.repeat && t-lastLeftTap<=260 ? -14 : -5; if(!e.repeat)lastLeftTap=t;"
]

class DashTests(unittest.TestCase):
    def test_three_small_isolated_patches(self):
        self.assertEqual(len(TASKS),3)
        for k,t in enumerate(TASKS):
            ok,reason,piece=valid_piece(EXAMPLE[k],t)
            self.assertTrue(ok,reason)
            self.assertTrue(piece)

    def test_only_model_accepted_source(self):
        responses=list(EXAMPLE)
        result,code=run(BASE,lambda *_:{"model_generated":True,"answer":responses.pop(0)},
                        attempts=1,syntax_check=lambda _:True)
        self.assertEqual(result["status"],"STATIC_CANDIDATE")
        self.assertTrue(result["model_authored_game_changes"])
        self.assertFalse(result["assistant_gameplay_code_used"])
        self.assertIn("lastRightTap",code)
        self.assertIn("lastLeftTap",code)
        self.assertIn("player.vx = !e.repeat",code)
        self.assertEqual(code.count("if(e.key==='ArrowRight')"),1)

    def test_fake_inference_cannot_pass(self):
        result,code=run(BASE,lambda *_:{"model_generated":False,"answer":EXAMPLE[0]},
                        attempts=1,syntax_check=lambda _:True)
        self.assertEqual(result["status"],"INCOMPLETE")
        self.assertIsNone(code)
        self.assertEqual(result["attempts"][0]["trials"][0]["reason"],"not_real_inference")

    def test_syntax_or_external_code_blocks_progress(self):
        for answer in ("fetch('https://evil')", "const x=1;"):
            self.assertFalse(valid_piece(answer,TASKS[0])[0])
        result,code=run(BASE,lambda *_:{"model_generated":True,"answer":EXAMPLE[0]},
                        attempts=1,syntax_check=lambda _:False)
        self.assertIsNone(code)
        self.assertEqual(result["attempts"][0]["trials"][0]["reason"],"javascript_syntax_error")

    def test_does_not_accept_mismatched_original_source(self):
        result,code=run("let someOtherVar = true;",lambda *_:{"model_generated":True,
                      "answer":EXAMPLE[0]},attempts=1,syntax_check=lambda _:True)
        self.assertIsNone(code)
        self.assertTrue(result["attempts"][0]["trials"][0]["reason"].startswith("native_"))

if __name__=="__main__":
    unittest.main()
