"""Safe, separate Windows GameDev runtime archive installer tests."""
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import sys,unittest,zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from install_ornith_game_runtime import TAG,ZIP_SHA256,safe_members,install_archive,DEST

def archive(files):
    buffer=BytesIO()
    with zipfile.ZipFile(buffer,'w') as z:
        for name,data in files.items():z.writestr(name,data)
    buffer.seek(0)
    return buffer

class ModernRuntimeTests(unittest.TestCase):
    def test_pinned_release_and_separate_destination(self):
        self.assertTrue(TAG.startswith('b'))
        self.assertEqual(len(ZIP_SHA256),64)
        self.assertIn("ornith-gamedev",str(DEST))

    def test_rejects_traversal_and_missing_cli(self):
        for name in ("../llama-cli.exe","C:/llama-cli.exe","/llama-cli.exe"):
            with self.subTest(name=name):
                with zipfile.ZipFile(archive({name:b'evil'})) as z:
                    with self.assertRaises(ValueError):safe_members(z)
        with zipfile.ZipFile(archive({'unrelated.dll':b'x'})) as z:
            with self.assertRaisesRegex(ValueError,'missing llama-cli.exe'):
                safe_members(z)

    def test_only_allowed_exe_dll_extracted_and_no_overwrite(self):
        with TemporaryDirectory() as t:
            root=Path(t)
            data=archive({'bin/llama-cli.exe':b'cli','bin/helper.dll':b'dll',
                          'bin/README.txt':b'docs','bin/scripts/install.ps1':b'unsafe'})
            p=root/'runtime.zip';p.write_bytes(data.getvalue())
            result=install_archive(p,root)
            self.assertEqual(result.read_bytes(),b'cli')
            self.assertEqual((result.parent/'helper.dll').read_bytes(),b'dll')
            self.assertFalse((result.parent/'install.ps1').exists())
            with self.assertRaises(FileExistsError):install_archive(p,root)

if __name__=="__main__":unittest.main()
