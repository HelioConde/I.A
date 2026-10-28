"""Offline verification of model safety and game constraints."""
from pathlib import Path
import sys,unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from benchmark_luna_game_models import PROMPT,clean,syntax_valid,command
from install_ornith_game_model import MODEL_SHA256,MODEL_REVISION,MODEL_FILE,MODEL_URL
GOOD="""const canvas=document.getElementById('game');const ctx=canvas.getContext('2d');
const player={x:80,y:392,hp:100},enemies=[{x:410,hp:3}],mode='game';
const keys=['ArrowLeft','ArrowRight','Space','KeyZ'];
window.__LUNA_GAMEDEV_QA__={snapshot:()=>({player,enemies,mode})};
function tick(){ctx.clearRect(0,0,800,480);requestAnimationFrame(tick)}
requestAnimationFrame(tick);"""
class ModelTests(unittest.TestCase):
  def test_pin(self):
    self.assertEqual(len(MODEL_SHA256),64)
    self.assertIn(MODEL_REVISION,MODEL_URL)
    self.assertIn("Ornith-1.5-9B",MODEL_FILE)
  def test_good_output(self):
    self.assertEqual(clean(GOOD),GOOD+"\n")
    self.assertTrue(syntax_valid(GOOD))
  def test_reject(self):
    with self.assertRaises(ValueError):
      clean(GOOD+"fetch('https://example.com')")
    with self.assertRaises(ValueError):
      clean("<think>incomplete"+GOOD)
    self.assertFalse(syntax_valid(GOOD+"\nconst broken={"))
  def test_cli(self):
    args=command(Path("/tmp/llama-cli"),Path("/tmp/model.gguf"),PROMPT,900)
    self.assertIn("--no-warmup",args)
    self.assertIn("900",args)
if __name__=="__main__":unittest.main()
