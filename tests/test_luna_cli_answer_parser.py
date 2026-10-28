"""Native GGUF output envelope regression tests for llama.cpp interactive logs."""
from pathlib import Path
import sys,unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from luna_cli_answer_parser import extract_native_answer
from benchmark_luna_game_models import clean

CODE="""const canvas=document.getElementById('game');
const ctx=canvas.getContext('2d');
let player={x:80,y:392,hp:3}, enemies=[{x:410,hp:3}], mode='playing';
window.__LUNA_GAMEDEV_QA__={snapshot:()=>({player,enemies,mode})};
let keys=['ArrowLeft','ArrowRight','Space','KeyZ'];
requestAnimationFrame(()=>{ctx.fillRect(player.x,player.y,28,28)});"""
LOG=(
  "Loading model... \n\nbuild : b1-f4d8af6\nmodel : models/Ornith.gguf\n"
  "available commands:\n/exit    stop\n\n> Você é Luna, escreva código "
  "sem fetch nem bibliotecas. ... (truncated)\n"
  +CODE+"\n\n[ Prompt: 22.8 t/s | Generation: 8.3 t/s ]\n\n> \nExiting...\n"
)
class ParserTests(unittest.TestCase):
    def test_sanitizes_only_cli_wrapper(self):
        self.assertEqual(extract_native_answer(LOG),CODE)
        self.assertEqual(clean(extract_native_answer(LOG)),CODE+"\n")
        self.assertEqual(extract_native_answer(CODE),CODE)

    def test_fail_closed_when_terminal_format_changes(self):
        with self.assertRaisesRegex(ValueError,"prompt_echo"):
            extract_native_answer("Loading model... \nNO_PROMPT\n[ Prompt: 2 t/s | Generation: 3 t/s ]")
        with self.assertRaisesRegex(ValueError,"completion_footer"):
            extract_native_answer("Loading model... \n> input\ncode without timings")
        with self.assertRaisesRegex(ValueError,"empty"):
            extract_native_answer("")

    def test_html_generation_not_accepted_as_javascript(self):
        ticks=chr(96)*3
        html=ticks+"html\n<canvas id='game'></canvas><script>1</script>\n"+ticks
        with self.assertRaises(ValueError):
            clean(extract_native_answer(LOG.replace(CODE,html)))

if __name__=="__main__":unittest.main()
