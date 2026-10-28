"""Synthetic fixtures confirm protected Lua counting is metadata-only."""
from __future__ import annotations

from pathlib import Path
import importlib.util
import json
import tempfile
import unittest
from unittest import mock

LAB=Path(__file__).resolve().parents[1]/"experiments"/"luna-forge-zero"
import sys
sys.path.insert(0,str(LAB))
spec=importlib.util.spec_from_file_location(
    "audit_excluded_lua_metadata",LAB/"audit_excluded_lua_metadata.py")
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class LuaExcludedMetadataTests(unittest.TestCase):
    def test_protected_directories_counted_without_content_reads(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/"safe.lua").write_bytes(b"return 1")
            (root/"other.txt").write_bytes(b"not lua")
            game=root/"Elsword"
            game.mkdir()
            (game/"client.lua").write_bytes(b"\x1bLua"+b"\0"*15)
            (game/"world.lua").write_bytes(b"local f=2")
            nested=game/"deep"
            nested.mkdir()
            (nested/"deeper.lua").write_bytes(b"--lua")
            sensitive=root/"database"
            sensitive.mkdir()
            (sensitive/"accounts.lua").write_bytes(b"secret=42")
            (sensitive/"accounts.bak").write_bytes(b"private data")
            with mock.patch("builtins.open",side_effect=AssertionError("Never open data files")):
                report=module.audit(root)
            self.assertEqual(report["lua_files_counted"],5)
            self.assertEqual(report["lua_files_under_protected_directories"],4)
            self.assertEqual(report["scope_counts"]["permitted"]["lua_files"],1)
            self.assertEqual(report["scope_counts"]["game_or_client_excluded"]["lua_files"],3)
            self.assertEqual(report["scope_counts"]["sensitive_or_backup_excluded"]["lua_files"],1)
            self.assertEqual(report["protected_root_counts"]["game_or_client_excluded"],1)
            self.assertEqual(report["protected_root_counts"]["sensitive_or_backup_excluded"],1)
            self.assertEqual(report["file_contents_read"],0)
            self.assertFalse(report["training_started"])
            self.assertFalse(report["model_weights_changed"])
            serialized=json.dumps(report)
            for private in (str(root),"accounts.lua","client.lua","Elsword","secret=42"):
                self.assertNotIn(private,serialized)

    def test_no_protected_dirs_and_entry_limit(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for i in range(7):
                (root/f"game_{i}.lua").write_bytes(b"local a=1")
            report=module.audit(root)
            self.assertEqual(report["lua_files_counted"],7)
            self.assertEqual(report["lua_files_under_protected_directories"],0)
            self.assertFalse(report["partial"])
            bounded=module.audit(root,max_entries=2)
            self.assertTrue(bounded["partial"])
            self.assertLessEqual(bounded["lua_files_counted"],2)

    def test_paths_and_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for budget in (0,200001):
                with self.assertRaisesRegex(ValueError,"Invalid entry limit"):
                    module.audit(root,max_entries=budget)
            with self.assertRaisesRegex(ValueError,"inexistente"):
                module.audit(root/"not_found")

if __name__=="__main__":
    unittest.main()
