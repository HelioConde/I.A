"""Unit tests: parse generated Lua without running it or reporting private paths."""
from __future__ import annotations
from pathlib import Path
from subprocess import CompletedProcess, TimeoutExpired
import sys
import unittest
from unittest import mock

LAB=Path(__file__).resolve().parents[1]/"experiments"/"luna-forge-zero"
sys.path.insert(0,str(LAB))
from luna_lua_syntax import syntax_check_lua
from luna_codegen_model import Config,LunaMiniCoder
import torch

class GeneratedLuaSyntaxTests(unittest.TestCase):
    def test_missing_luac_is_unavailable_not_false_success(self):
        with mock.patch("luna_lua_syntax.shutil.which",return_value=None):
            self.assertEqual(syntax_check_lua("function go() end"),"UNAVAILABLE_NO_LUAC")

    def test_only_parse_only_compiler_is_launched(self):
        def fake_run(argv,**kwargs):
            self.assertEqual(argv[0],"fake-luac")
            self.assertEqual(argv[1],"-p")
            self.assertEqual(kwargs.get("check"),False)
            self.assertTrue(kwargs.get("capture_output"))
            self.assertFalse(kwargs.get("shell",False))
            generated=Path(argv[2])
            self.assertEqual(generated.read_text(encoding="utf-8"),"function go() end")
            return CompletedProcess(args=argv,returncode=0)
        with mock.patch("luna_lua_syntax.subprocess.run",side_effect=fake_run):
            self.assertEqual(syntax_check_lua("function go() end",compiler="fake-luac"),"PASS")

    def test_failed_syntax_and_timeout_are_not_success(self):
        with mock.patch("luna_lua_syntax.subprocess.run",
                        return_value=CompletedProcess([],returncode=1)):
            self.assertEqual(syntax_check_lua("THIS IS NOT LUA",compiler="fake-luac"),"FAIL")
        with mock.patch("luna_lua_syntax.subprocess.run",
                        side_effect=TimeoutExpired(cmd="luac -p",timeout=8)):
            self.assertEqual(syntax_check_lua("return 1",compiler="fake-luac"),"TIMEOUT")
        self.assertEqual(syntax_check_lua("",compiler="fake-luac"),"FAIL_EMPTY")
        with self.assertRaises(ValueError):
            syntax_check_lua("x"*12001,compiler="fake-luac")

    def test_greedy_generation_is_seed_independent(self):
        model=LunaMiniCoder(Config(vocab=128,block=16,width=16,heads=4,layers=1))
        torch.manual_seed(1)
        out1=model.generate("function x",chars=6,temperature=0)
        torch.manual_seed(9876)
        out2=model.generate("function x",chars=6,temperature=0)
        self.assertEqual(out1,out2)
        self.assertTrue(out1.startswith("function x"))
        self.assertEqual(len(out1),len("function x")+6)
        for temp in (-1,3.5):
            with self.assertRaises(ValueError):
                model.generate("lua",chars=5,temperature=temp)
        with self.assertRaises(ValueError):
            model.generate("lua",chars=0,temperature=0)

if __name__=="__main__":
    unittest.main()
