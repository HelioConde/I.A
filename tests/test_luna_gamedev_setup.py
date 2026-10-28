"""One-command setup: never download unless explicitly approved."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import sys,unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import setup_luna_gamedev_v4 as setup

class SetupTests(unittest.TestCase):
    def test_opt_in_prevents_any_download(self):
        with patch.object(sys,"argv",["setup_luna_gamedev_v4.py"]):
            with patch.object(setup,"provision",side_effect=AssertionError("must not install")):
                self.assertEqual(setup.main(),0)

    def test_two_verified_install_steps_and_no_chat_change(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            with patch.object(setup,"install_native",return_value=root/"new/llama-cli.exe") as runtime:
                with patch.object(setup,"install_gguf",return_value="GGUF verified") as model:
                    with patch.object(setup,"choose_game_coder",return_value=("ornith-1.5-9b",setup.MODEL_FILE)):
                        r=setup.provision(root,check_space=False)
                        self.assertFalse(r["regular_chat_changed"])
                        self.assertEqual(r["selector"],"ornith-1.5-9b")
                        runtime.assert_called_once()
                        model.assert_called_once()

if __name__=="__main__":unittest.main()
