"""No download: test that GameDev auto-selection is verified and reversible."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import sys,unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from luna_game_model_selector import choose_game_coder,ORNITH_FILE,QWEN_FILE

class SelectorTests(unittest.TestCase):
    def test_prefer_ornith_only_if_present_and_verified(self):
        with TemporaryDirectory() as t:
            base=Path(t); (base/"models").mkdir()
            (base/"models"/QWEN_FILE).write_bytes(b"GGUF")
            with patch("luna_game_model_selector.verified_file",return_value=True):
                self.assertEqual(choose_game_coder(base)[1],QWEN_FILE)
                (base/"models"/ORNITH_FILE).write_bytes(b"GGUF")
                self.assertEqual(choose_game_coder(base)[1],ORNITH_FILE)
                self.assertEqual(choose_game_coder(base,"qwen3-4b")[1],QWEN_FILE)

    def test_reject_corrupt_or_unknown(self):
        with TemporaryDirectory() as t:
            base=Path(t);(base/"models").mkdir()
            (base/"models"/ORNITH_FILE).write_bytes(b"bad")
            with patch("luna_game_model_selector.verified_file",return_value=False):
                with self.assertRaisesRegex(ValueError,"SHA256"):
                    choose_game_coder(base)
            with self.assertRaisesRegex(ValueError,"Unrecognized"):
                choose_game_coder(base,"evil-model")
            (base/"models"/ORNITH_FILE).unlink()
            with self.assertRaises(FileNotFoundError):
                choose_game_coder(base)

if __name__=="__main__": unittest.main()
