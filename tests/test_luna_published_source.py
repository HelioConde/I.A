"""Published model-source attestation contract: use fabricated source only in tests."""
import hashlib,json,pathlib,sys,tempfile,unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import check_luna_published_source as mod

HTML='<html lang="pt-BR"><canvas id="game"></canvas><button id="start"></button><select id="hero"></select><p id="status"></p></html>'
CSS='body{color:white}canvas{width:100%}'
JS='let enemies=[],wave=0;'

class AttestationTests(unittest.TestCase):
    def fixture(self,game):
        sources={'index.html':HTML,'styles.css':CSS,'game.js':JS}
        for n,code in sources.items():
            (game/n).write_text(code,encoding='utf-8')
        return {
            'model':'Qwen3-4B-Q4_K_M.gguf',
            'game_code_author':'Luna Qwen3-4B',
            'assistant_gameplay_code_used':False,
            'source_original_run':40636116071,
            'source_runs':[40636116071,40648093762,40648389270],
            'files':{n:{'source_run':40636116071,
                       'sha256':hashlib.sha256(code.encode()).hexdigest()}
                     for n,code in sources.items()},
        }

    def test_correct_model_hashes_required(self):
        with tempfile.TemporaryDirectory() as td,patch.object(mod,'GAME',pathlib.Path(td)):
            data=self.fixture(mod.GAME)
            (mod.GAME/'provenance.json').write_text(json.dumps(data),encoding='utf-8')
            self.assertEqual(mod.validate()['model'],'Qwen3-4B-Q4_K_M.gguf')

    def test_wrong_source_and_source_claim_rejected(self):
        with tempfile.TemporaryDirectory() as td,patch.object(mod,'GAME',pathlib.Path(td)):
            data=self.fixture(mod.GAME)
            data['files']['game.js']['sha256']='a'*64
            (mod.GAME/'provenance.json').write_text(json.dumps(data),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'unverified_qwen_source_bytes'):
                mod.validate()
            data=self.fixture(mod.GAME)
            data['assistant_gameplay_code_used']=True
            (mod.GAME/'provenance.json').write_text(json.dumps(data),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'misattributed'):
                mod.validate()

    def test_network_exfiltration_disallowed(self):
        with tempfile.TemporaryDirectory() as td,patch.object(mod,'GAME',pathlib.Path(td)):
            data=self.fixture(mod.GAME)
            code='fetch("https://example.com/sensitive")'
            (mod.GAME/'game.js').write_text(code,encoding='utf-8')
            data['files']['game.js']['sha256']=hashlib.sha256(code.encode()).hexdigest()
            (mod.GAME/'provenance.json').write_text(json.dumps(data),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'network_or_dynamic_code'):
                mod.validate()

if __name__=="__main__":
    unittest.main()
