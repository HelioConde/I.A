"""Tests for non-content local review of excluded game/client Lua scopes."""
from __future__ import annotations
from pathlib import Path
import importlib.util
import tempfile
import unittest
from unittest import mock
import sys

LAB=Path(__file__).resolve().parents[1]/"experiments"/"luna-forge-zero"
sys.path.insert(0,str(LAB))
spec=importlib.util.spec_from_file_location("review_local_lua_scopes",LAB/"review_local_lua_scopes.py")
review=importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)

class ReviewLocalLuaScopesTests(unittest.TestCase):
    def test_lists_game_and_anticheat_roots_without_content_reads(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            game=root/"Elsword"
            game.mkdir()
            (game/"code.lua").write_bytes(b"\x00"*54)
            deep=game/"maps"
            deep.mkdir()
            (deep/"world.lua").write_bytes(b"any byte content")
            db=game/"database"
            db.mkdir()
            (db/"secret.lua").write_bytes(b"PRIVATE DATA")
            shield=root/"HShield"
            shield.mkdir()
            (shield/"guard.lua").write_bytes(b"not read")
            with mock.patch("builtins.open",side_effect=AssertionError("file content opened")):
                roots=review.scopes(root)
            self.assertEqual(len(roots),2)
            self.assertEqual({x["category"] for x in roots},{"game_client","anti_cheat"})
            game_scope=next(x for x in roots if x["category"]=="game_client")
            self.assertEqual(game_scope["lua_files_metadata"],2)
            self.assertFalse(game_scope["training_permitted"])
            self.assertEqual(game_scope["lua_bytes_metadata"],54+len(b"any byte content"))

    def test_empty_source_has_no_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(review.scopes(Path(tmp)),[])

    def test_does_not_follow_root_missing_or_unsafe(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing=Path(tmp)/"not_here"
            with self.assertRaises(ValueError):
                review.scopes(missing)

if __name__=="__main__":
    unittest.main()
