"""No fabricated model patch; validate repairs of original Ornith's own JS."""
from pathlib import Path
import sys,unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from ornith_game_self_repair import TASKS,repair,validate_piece

ORIGINAL=(
"player = { x: 80, y: 392, w: 28, h: 28, hp: 3, onGround: true };\n"
"const k = e.key;\n"
)
RESP=[
"player = { x: 80, y: 392, w: 28, h: 28, hp: 3, onGround: true, vy: 0 };",
"const k = e.code;"
]

class GenuineRepairTests(unittest.TestCase):
    def test_two_model_patches_change_only_necessary_lines(self):
        queue=list(RESP)
        result,game=repair(ORIGINAL,lambda *_:{"answer":queue.pop(0),"real_model":True,
                                                    "raw_sha256":"d"*64},attempts=1)
        self.assertEqual(result["status"],"STATIC_REPAIR")
        self.assertEqual(result["patch_count"],2)
        self.assertIn("vy: 0",game)
        self.assertIn("e.code",game)
        self.assertFalse(result["assistant_gameplay_code_used"])
        self.assertFalse(result["gameplay_verified"])

    def test_reject_unverified_inference_and_bad_properties(self):
        result,game=repair(ORIGINAL,lambda *_:{"answer":RESP[0],"real_model":False},
                           attempts=1)
        self.assertEqual(result["status"],"INCOMPLETE")
        self.assertIsNone(game)
        self.assertFalse(validate_piece("const k = e.key;",TASKS[1])[0])
        self.assertFalse(validate_piece("player = {x:1,vy:4};",TASKS[0])[0])

    def test_original_markers_required(self):
        result,game=repair("const meaningless=1;",lambda *_:{},attempts=1)
        self.assertEqual(result["status"],"SOURCE_MARKER_MISMATCH")
        self.assertIsNone(game)

if __name__=="__main__":unittest.main()
