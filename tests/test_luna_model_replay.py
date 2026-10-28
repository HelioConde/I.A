"""Replay only genuine archived model tokens, never assistant-written game output."""
from pathlib import Path
from tempfile import TemporaryDirectory
import hashlib,json,sys,unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from replay_luna_model_benchmark import replay

JS="""const canvas=document.getElementById('game');const ctx=canvas.getContext('2d');
const player={x:80,y:392,hp:100},enemies=[{x:410,hp:3}],mode='play';
window.__LUNA_GAMEDEV_QA__={snapshot:()=>({player,enemies,mode})};
const keys=['ArrowLeft','ArrowRight','Space','KeyZ'];
function tick(){ctx.fillRect(0,0,50,50);requestAnimationFrame(tick)}
requestAnimationFrame(tick);"""
class ReplayTests(unittest.TestCase):
    def test_raw_model_artifact_is_provenance_tracked_and_no_rewrite(self):
        with TemporaryDirectory() as tmp:
            base=Path(tmp)
            raw=base/"raw";raw.mkdir()
            original={"model":"ornith-1.5-9b","benchmark":"Luna native GameDev v4",
                      "model_sha256":"a"*64,"status":"INCOMPLETE"}
            (raw/"provenance.json").write_text(json.dumps(original))
            (raw/"attempt-1.raw.txt").write_text(
              "Loading model...\n> Este e o prompt ... (truncated)\n"+JS+
              "\n[ Prompt: 18.2 t/s | Generation: 9.4 t/s ]\n\n> \nExiting...")
            (raw/"attempt-2.raw.txt").write_text("broken")
            result=replay(raw,base/"out","ornith-1.5-9b")
            self.assertEqual(result["attempts"][0]["status"],"VALID_JS_PENDING_BROWSER")
            self.assertEqual((base/"out/attempt-1/game.js").read_text(),JS+"\n")
            self.assertEqual(result["attempts"][1]["playable"],False)
            self.assertFalse(result["gameplay_verified"])
            self.assertTrue(result["provenance_replayed_not_regenerated"])
    def test_reject_spoofed_model_identity(self):
        with TemporaryDirectory() as tmp:
            base=Path(tmp)
            (base/"provenance.json").write_text(json.dumps({"model":"fake","benchmark":"Luna native GameDev v4"}))
            with self.assertRaisesRegex(ValueError,"provenance_model_mismatch"):
                replay(base,base/"out","qwen3-4b")

if __name__=="__main__":unittest.main()
