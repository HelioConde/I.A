"""Offline tests for local Lua audit, using only invented synthetic examples."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]/"experiments"/"luna-forge-zero"
sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location("lua_audit",ROOT/"analyze_local_lua.py")
lua=importlib.util.module_from_spec(spec)
spec.loader.exec_module(lua)

class LuaLocalAuditTests(unittest.TestCase):
    def test_format_signatures(self):
        self.assertEqual(lua.kind(b"\x1bLua\x51\x00",6),"compiled_lua_or_kl")
        self.assertEqual(lua.kind(b"\x1bLJ\x02",4),"compiled_lua_or_kl")
        self.assertEqual(lua.kind(b"\x1bKL\x84",4),"compiled_lua_or_kl")
        self.assertEqual(lua.kind(b"local x=1\nfunction f() return x end",35),"utf8_text_candidate")
        self.assertEqual(lua.kind(b"\xef\xbb\xbflocal x=1\n",15),"utf8_text_candidate")
        self.assertEqual(lua.kind(b"",0),"empty")
        self.assertEqual(lua.kind(b"\x01\x02\x03\x04\x05abc",8),"binary_or_obfuscated")
        self.assertEqual(lua.kind(b"\xff\xfe" + "print(1)".encode("utf-16-le"),18),"utf16_text_candidate")
        self.assertEqual(lua.kind(b"ol\xe1",3),"non_utf8_or_binary_unknown")

    def test_no_non_lua_or_raw_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/"private"
            root.mkdir()
            (root/"source.lua").write_bytes(b"local SECRET_SAMPLE = 'DO_NOT_SAVE_THIS'\n")
            (root/"bytecode.lua").write_bytes(b"\x1bLua" + b"\x00"*200)
            for name in ("Account.bak","client.rar","game.exe","img.kom","manual.txt"):
                (root/name).write_bytes(b"USER_PRIVATE_DO_NOT_READ")
            result=lua.analyze(root)
            serialized=json.dumps(result)
            self.assertEqual(result["lua_files_sampled"],2)
            self.assertEqual(result["files_copied_or_uploaded"],0)
            self.assertEqual(result["files_transferred_to_training"],0)
            self.assertIs(result["training_permission_approved"],False)
            self.assertNotIn("SECRET_SAMPLE",serialized)
            self.assertNotIn("source.lua",serialized)
            self.assertNotIn("Account.bak",serialized)
            self.assertNotIn(str(root),serialized)
            self.assertEqual({x["format"]:x["files"] for x in result["counts"]},
                             {"utf8_text_candidate":1,"compiled_lua_or_kl":1})

    def test_limit_and_missing_folder(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for i in range(5):
                (root/f"src{i}.lua").write_bytes(b"return 1\n")
            result=lua.analyze(root,max_entries=2)
            self.assertEqual(result["lua_files_sampled"],2)
            self.assertTrue(result["partial"])
        with self.assertRaises(ValueError):
            lua.analyze(Path("nonexistent-luna-audit-test"))

    def test_reject_output_inside_input_folder(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/"input"
            root.mkdir()
            target=root/"report.json"
            code=subprocess.run([sys.executable,str(ROOT/"analyze_local_lua.py"),str(root),
                                  "--out",str(target)],capture_output=True,text=True,timeout=8)
            self.assertNotEqual(code.returncode,0)
            self.assertFalse(target.exists())

    def test_cli_aggregate_report_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/"input"
            root.mkdir()
            (root/"a.lua").write_text("function original() return true end\n",encoding="utf-8")
            target=Path(temp)/"reports"/"format.json"
            args=[sys.executable,str(ROOT/"analyze_local_lua.py"),str(root),"--out",str(target)]
            first=subprocess.run(args,capture_output=True,text=True,timeout=8)
            self.assertEqual(first.returncode,0,first.stderr)
            data=json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(data["lua_files_sampled"],1)
            self.assertNotIn("function original",target.read_text(encoding="utf-8"))
            second=subprocess.run(args,capture_output=True,text=True,timeout=8)
            self.assertNotEqual(second.returncode,0)

if __name__=="__main__":
    unittest.main()
