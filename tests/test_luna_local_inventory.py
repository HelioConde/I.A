"""Tests for local private archive inventory (no file contents inspected)."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]/"experiments"/"luna-forge-zero"
spec=importlib.util.spec_from_file_location("luna_inventory",ROOT/"inventory_local_data.py")
inventory=importlib.util.module_from_spec(spec)
spec.loader.exec_module(inventory)

class LocalDataInventoryTests(unittest.TestCase):
    def test_categories_and_metadata_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/"private-game-files"
            root.mkdir()
            (root/"client.rar").write_bytes(b"RAR")
            (root/"Account.bak").write_bytes(b"database-key material")
            (root/"main.exe").write_bytes(b"exe")
            (root/"Texture").mkdir()
            (root/"Texture"/"body.dds").write_bytes(b"image content")
            (root/"Motion").mkdir()
            (root/"Motion"/"example.lua").write_bytes(b"-- source without a license")
            result=inventory.inspect(root)
            self.assertEqual(result["files"],5)
            self.assertEqual(result["subdirectories"],2)
            self.assertEqual(result["raw_commercial_content_training_approved"],False)
            self.assertEqual(result["files_copied_or_uploaded"],0)
            self.assertEqual(result["files_opened_or_executed"],0)
            self.assertNotIn("Account.bak",json.dumps(result))
            self.assertNotIn(str(root),json.dumps(result))
            cats={c["category"]:c["files"] for c in result["categories"]}
            self.assertEqual(cats["sensitive_database_backup"],1)
            self.assertEqual(cats["closed_archive_not_processed"],1)
            self.assertEqual(cats["do_not_execute_binary_or_script"],1)
            self.assertEqual(cats["commercial_game_assets_do_not_train"],1)
            self.assertEqual(cats["possible_code_permission_review_required"],1)

    def test_missing_folder_rejected(self):
        with self.assertRaises(ValueError):
            inventory.inspect(Path("nonexistent_folder_inventory_tests"))

    def test_limit_is_honored(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for i in range(5):
                (root/f"sample_{i}.txt").write_text("x")
            result=inventory.inspect(root,max_entries=2)
            self.assertEqual(result["files"],2)
            self.assertTrue(result["partial"])

    def test_cli_rejects_writing_into_source_folder(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/"raw"
            root.mkdir()
            process=subprocess.run([sys.executable,str(ROOT/"inventory_local_data.py"),
                                    str(root),"--out",str(root/"report.json")],
                                   text=True,capture_output=True)
            self.assertNotEqual(process.returncode,0)
            self.assertFalse((root/"report.json").exists())

    def test_cli_writes_aggregate_report_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/"raw"
            root.mkdir()
            (root/"Game01.bak").write_bytes(b"sensitive")
            target=Path(temp)/"out"/"inventory.json"
            process=subprocess.run([sys.executable,str(ROOT/"inventory_local_data.py"),
                                    str(root),"--out",str(target)],
                                   text=True,capture_output=True,timeout=15)
            self.assertEqual(process.returncode,0,process.stderr)
            report=json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(report["files"],1)
            self.assertNotIn("Game01.bak",target.read_text(encoding="utf-8"))
            self.assertEqual(report["files_copied_or_uploaded"],0)
            again=subprocess.run([sys.executable,str(ROOT/"inventory_local_data.py"),
                                  str(root),"--out",str(target)],capture_output=True)
            self.assertNotEqual(again.returncode,0)

if __name__=="__main__":
    unittest.main()
