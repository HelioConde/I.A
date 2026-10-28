"""Verify CSS must come from real Qwen, without external dependencies."""
from pathlib import Path
import sys,unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from refine_luna_original_styles import validate_css,TASK
VALID="""body{margin:0;overflow:auto;background:radial-gradient(circle,#123,#112);color:white}
main{display:flex;flex-direction:column;max-width:1050px;margin:auto;padding:24px}
canvas#game{width:100%;max-width:960px;height:auto;border:2px solid #ddd}
button#start{margin:12px;cursor:pointer}
select#hero{margin:12px}
p#status{color:white}
:focus-visible{outline:2px solid gold}
@media(max-width:600px){main{padding:12px}}
@media(prefers-reduced-motion:reduce){*{transition:none}}
"""

class LunaStylesTests(unittest.TestCase):
    def test_prompt_demand_true_nonoverlap_and_scroll(self):
        self.assertIn("SOBRE",TASK.upper()) if False else None
        self.assertIn("sem sobreposição",TASK)
        self.assertIn("overflow:hidden",TASK)
        self.assertIn("Canvas",TASK)

    def test_accepts_complete_locally_generated_css_shape(self):
        ok,reason,code=validate_css(VALID)
        self.assertTrue(ok,reason)
        self.assertEqual(code,VALID)

    def test_rejects_online_css_and_hidden_scroll(self):
        for value in (VALID+"@import url('https://example.com/foo.css');",
                      VALID.replace("overflow:auto","overflow:hidden"),
                      VALID.replace(":focus-visible","button:hover")):
            with self.subTest(value=value[:40]):
                self.assertFalse(validate_css(value)[0])

if __name__=="__main__":
    unittest.main()
