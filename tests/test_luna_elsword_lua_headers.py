"""Tests stage-2 Elsword Lua header audit using synthetic invented data only."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE=Path(__file__).resolve().parents[1]/"experiments"/"luna-forge-zero"
sys.path.insert(0,str(HERE))
spec=importlib.util.spec_from_file_location("audit_elsword_lua_headers",HERE/"audit_elsword_lua_headers.py")
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class ElswordHeaderAuditTests(unittest.TestCase):
    def test_sample_only_and_nested_sensitive_directories_excluded(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/"Elsword"
            root.mkdir()
            code=(root/"gameplay.lua")
            code.write_text("function step() return true end\n",encoding="utf-8")
            (root/"compiled.lua").write_bytes(b"\x1bLua\x53\x00"+b"x"*600)
            (root/"bytes.lua").write_bytes(b"\x00"*250)
            (root/"binary.kom").write_bytes(b"NO_CODE")
            protected=root/"database"
            protected.mkdir()
            (protected/"password.lua").write_bytes(b"protected private data")
            anticheat=root/"HShield"
            anticheat.mkdir()
            (anticheat/"unsafe.lua").write_bytes(b"not read")
            report=mod.inspect(root)
            self.assertEqual(report["lua_files_sampled"],3)
            self.assertEqual(report["excluded_sensitive_subdirectories"],2)
            self.assertEqual(report["classification_counts"]["utf8_text_candidate"],1)
            self.assertEqual(report["classification_counts"]["compiled_lua_or_kl"],1)
            self.assertEqual(report["files_under_256_bytes"],2)
            self.assertEqual(report["sampled_bytes_read"],
                             code.stat().st_size+606+250)
            self.assertEqual(report["files_uploaded_or_copied"],0)
            self.assertFalse(report["training_started"])
            self.assertFalse(report["weights_changed"])
            serialized=json.dumps(report,ensure_ascii=False)
            for secret in ("password.lua","gameplay.lua",str(root),"NO_CODE"):
                self.assertNotIn(secret,serialized)

    def test_wrong_folder_rejected_even_when_it_contains_lua(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp)
            with self.assertRaisesRegex(ValueError,"Elsword"):
                mod.inspect(base)

    def test_bounded_limit_and_no_follow_reparse_points(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/"Elsword"
            root.mkdir()
            for i in range(4):
                (root/f"script_{i}.lua").write_bytes(b"return 1")
            summary=mod.inspect(root,max_entries=2)
            self.assertEqual(summary["lua_files_sampled"],2)
            self.assertTrue(summary["partial"])
            self.assertLessEqual(summary["sampled_bytes_read"],8192)

if __name__=="__main__":
    unittest.main()
