"""Tests use invented Lua snippets only; never commercial game content."""
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
spec=importlib.util.spec_from_file_location("lua_profile",ROOT/"profile_local_lua.py")
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class LuaProfileTests(unittest.TestCase):
    def test_keywords_do_not_count_strings_or_comments(self):
        sample=(
            "-- function if while for return\n"
            "local instruction = 'function if return'\n"
            "local other = \"while for\"\n"
            "local function update(dt)\n"
            "    if dt > 0 then\n"
            "        for i=1,3 do print(i) end\n"
            "    end\n"
            "    return dt\n"
            "end\n"
        )
        tokens=module.keyword_counts(sample)
        self.assertEqual(tokens["function"],1)
        self.assertEqual(tokens["if"],1)
        self.assertEqual(tokens["for"],1)
        self.assertEqual(tokens["while"],0)
        self.assertEqual(tokens["return"],1)
        self.assertEqual(module.structural_group(tokens),"functions_and_control_flow")

    def test_aggregate_only_and_no_binary_files(self):
        with tempfile.TemporaryDirectory() as base:
            folder=Path(base)/"private"
            folder.mkdir()
            (folder/"secret.lua").write_text("local function update(dt) if dt > 0 then return dt end end\n")
            (folder/"bytecode.lua").write_bytes(b"\x1bLua"+b"\x00"*512)
            (folder/"README.lua").write_text("-- comment only\n")
            (folder/"Account.bak").write_bytes(b"PRIVATE_ACCOUNT_INFORMATION")
            (folder/"client.rar").write_bytes(b"game archive")
            profile=module.analyze(folder)
            dump=json.dumps(profile)
            self.assertEqual(profile["lua_files_sampled"],3)
            self.assertEqual(profile["structure_groups"]["functions_and_control_flow"],1)
            self.assertEqual(profile["format_counts"]["compiled_lua_or_kl"],1)
            self.assertEqual(profile["files_trained"],0)
            self.assertFalse(profile["training_permission_approved"])
            for private in ("secret.lua","Account.bak","PRIVATE_ACCOUNT_INFORMATION","function update",str(folder)):
                self.assertNotIn(private,dump)

    def test_large_file_bounded(self):
        with tempfile.TemporaryDirectory() as base:
            folder=Path(base)
            (folder/"large.lua").write_bytes(b"return 2\n"+b"-"*100000)
            report=module.analyze(folder,peek=4096)
            self.assertEqual(report["files_larger_than_sample"],1)
            self.assertEqual(report["sampled_bytes_read"],4096)

    def test_output_outside_source_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as base:
            folder=Path(base)/"source"
            folder.mkdir()
            (folder/"a.lua").write_text("return 1\n")
            path=ROOT/"profile_local_lua.py"
            wrong=subprocess.run([sys.executable,str(path),str(folder),"--out",str(folder/"x.json")],
                                  capture_output=True,text=True,timeout=10)
            self.assertNotEqual(wrong.returncode,0)
            self.assertFalse((folder/"x.json").exists())
            dest=Path(base)/"report.json"
            cmd=[sys.executable,str(path),str(folder),"--out",str(dest)]
            valid=subprocess.run(cmd,capture_output=True,text=True,timeout=10)
            self.assertEqual(valid.returncode,0,valid.stderr)
            self.assertEqual(json.loads(dest.read_text())["files_executed"],0)
            repeat=subprocess.run(cmd,capture_output=True,text=True,timeout=10)
            self.assertNotEqual(repeat.returncode,0)

if __name__=="__main__":
    unittest.main()
