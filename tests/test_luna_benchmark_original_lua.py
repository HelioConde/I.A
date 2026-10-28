"""Original synthetic test cases for the MiniCoder Lua benchmark; no game files."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

LAB=Path(__file__).resolve().parents[1]/"experiments"/"luna-forge-zero"
sys.path.insert(0,str(LAB))
spec=importlib.util.spec_from_file_location("benchmark_original_lua",LAB/"benchmark_original_lua.py")
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class OriginalLuaBenchmarkTests(unittest.TestCase):
    def test_holdout_has_no_answers_and_stays_lua_specific(self):
        for task in module.HOLDOUT:
            prompt=module.prompt_for(task)
            self.assertEqual(task["split"],"holdout")
            self.assertIsNone(task["answer"])
            self.assertTrue(prompt.startswith("TASK: "))
            self.assertTrue(prompt.endswith("\nLANGUAGE: lua\nCODE:\n"))
            self.assertNotIn("Grand Chase",prompt)
            self.assertNotIn("Elsword",prompt)
        self.assertEqual(len(module.HOLDOUT),3)

    def test_heuristics_are_explicitly_not_syntax_or_gameplay_tests(self):
        snippet="function actor_run(x)\n return x\nend\n"
        outcome=module.summarize(snippet)
        self.assertTrue(outcome["contains_function_keyword"])
        self.assertTrue(outcome["contains_end_keyword"])
        self.assertTrue(outcome["contains_return_keyword"])
        self.assertTrue(outcome["contains_obvious_lua_function_signature"])
        self.assertEqual(outcome["lua_syntax"],"NOT_TESTED")
        self.assertEqual(outcome["gameplay_behavior"],"NOT_TESTED")
        self.assertNotIn(snippet,str(outcome))
        bad=module.summarize("There is a function with an end in this sentence")
        self.assertFalse(bad["contains_obvious_lua_function_signature"])
        self.assertEqual(bad["lua_syntax"],"NOT_TESTED")

    def test_no_eligible_candidate_does_not_read_user_game_files(self):
        with tempfile.TemporaryDirectory() as temp:
            with mock.patch.object(module,"DATA",Path(temp)), \
                 mock.patch.object(module,"candidates",return_value=[]):
                with self.assertRaisesRegex(FileNotFoundError,"MiniCoder"):
                    module.benchmark()

    def test_invalid_budget_and_unapproved_holdout_rejected(self):
        for chars in (0,241,-1):
            with self.assertRaises(ValueError):
                module.benchmark(chars=chars)
        item={"split":"train","answer":"function bad() end","objective":"injected"}
        with self.assertRaisesRegex(ValueError,"holdout"):
            module.prompt_for(item)

if __name__=="__main__":
    unittest.main()
