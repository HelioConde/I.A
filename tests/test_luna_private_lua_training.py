"""Offline test fixtures with newly authored synthetic Lua; no user assets."""
from __future__ import annotations
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

LAB=Path(__file__).resolve().parents[1]/"experiments"/"luna-forge-zero"
spec=importlib.util.spec_from_file_location("train_private_lua",LAB/"train_private_lua.py")
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

SAMPLE=(
    "local function step(actor, axis, dt)\n"
    "  if axis < 0 then actor.x = actor.x - dt end\n"
    "  if axis > 0 then actor.x = actor.x + dt end\n"
    "  return actor\nend\n"
)*12

class LocalRightsGatedLuaTests(unittest.TestCase):
    def test_provenance_filters_and_no_non_lua_reads(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/"gamefolder"
            root.mkdir()
            for n in range(38):
                (root/f"game_{n:02d}.lua").write_text(SAMPLE,encoding="utf-8")
            (root/"binary.lua").write_bytes(b"\x1bLua"+b"x"*1000)
            (root/"sensitive_data.lua").write_text("local password = 'x'\n"+SAMPLE)
            (root/"utf16.lua").write_bytes(("\ufeff"+SAMPLE).encode("utf-16-le"))
            (root/"account.bak").write_bytes(b"private database data")
            (root/"client.rar").write_bytes(b"private archive bytes")
            hidden=root/"Elsword"
            hidden.mkdir()
            (hidden/"world.lua").write_text(SAMPLE,encoding="utf-8")
            summary,train,holdout=mod.prepare(root,max_mib=1)
            self.assertEqual(summary["source_lua_files_discovered"],41)
            self.assertEqual(summary["sampled_files"],38)
            self.assertEqual(len(train)+len(holdout),38)
            self.assertGreaterEqual(summary["heldout_files"],2)
            self.assertEqual(summary["backups_and_archives_opened"],0)
            self.assertEqual(summary["source_files_exported"],0)
            self.assertEqual(summary["network_requests"],0)
            self.assertNotIn(str(root),json.dumps(summary))
            self.assertNotIn("game_00.lua",json.dumps(summary))
            self.assertTrue(all(len(item)>129 for item in train+holdout))
            self.assertGreaterEqual(summary["skipped_by_reason"].get("bytecode",0),1)
            self.assertGreaterEqual(summary["skipped_by_reason"].get("potential_secret",0),1)

    def test_missing_rights_flag_stops_before_read(self):
        with tempfile.TemporaryDirectory() as temp:
            import subprocess,sys
            process=subprocess.run([sys.executable,str(LAB/"train_private_lua.py"),
                "dry-run","--source",temp],capture_output=True,text=True,timeout=15)
            self.assertNotEqual(process.returncode,0)
            self.assertIn("rights not confirmed",process.stderr)
            self.assertNotIn(temp,process.stderr)

    def test_source_does_not_have_to_contain_subdirectories(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            files,seen,skipped=mod.list_safe_lua(root)
            self.assertEqual((files,seen,skipped),([],0,0))
            with self.assertRaisesRegex(ValueError,"Poucos arquivos"):
                mod.prepare(root,max_mib=1)

    def test_dry_run_reports_why_lua_files_are_unavailable(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/"private_game"
            root.mkdir()
            # Extension inventories see these files, but the private trainer
            # deliberately refuses to traverse protected directories.
            hidden=root/"Elsword"
            hidden.mkdir()
            for i in range(25):
                (hidden/f"combat_{i}.lua").write_text(SAMPLE,encoding="utf-8")
            (root/"tiny.lua").write_text("return 1",encoding="utf-8")
            summary,train,holdout=mod.prepare(root,max_mib=1,strict=False)
            self.assertFalse(summary["training_ready"])
            self.assertEqual(summary["source_lua_files_discovered"],1)
            self.assertEqual(summary["excluded_entry_counts"]["protected_directory_skipped"],1)
            self.assertEqual(summary["excluded_entry_counts"]["files_under_256_bytes"],1)
            self.assertEqual((train,holdout),([],[]))
            report=json.dumps(summary,ensure_ascii=False)
            self.assertNotIn(str(root),report)
            self.assertNotIn("combat_0.lua",report)
            with self.assertRaises(mod.InsufficientLuaData) as ctx:
                mod.prepare(root,max_mib=1)
            self.assertFalse(ctx.exception.summary["training_ready"])
            import subprocess,sys
            cli=subprocess.run([sys.executable,str(LAB/"train_private_lua.py"),
                "dry-run","--source",str(root),"--acknowledge-rights","--max-mib","1"],
                capture_output=True,text=True,timeout=15)
            self.assertEqual(cli.returncode,3,cli.stderr)
            data=json.loads(cli.stdout)
            self.assertFalse(data["training_ready"])
            self.assertEqual(data["weights_modified"],False)
            self.assertNotIn(str(root),cli.stdout)

    def test_minimum_holdout_is_deterministic_when_ten_files_are_eligible(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for i in range(10):
                (root/f"script_{i}.lua").write_text(SAMPLE,encoding="utf-8")
            summary,train,heldout=mod.prepare(root,max_mib=1)
            self.assertTrue(summary["training_ready"])
            self.assertEqual((len(train),len(heldout)),(8,2))
            summary2,train2,heldout2=mod.prepare(root,max_mib=1)
            self.assertEqual(summary,summary2)
            self.assertEqual(train,train2)
            self.assertEqual(heldout,heldout2)

    def test_compiled_and_sensitive_files_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            bad=root/"protected.lua"
            bad.write_text("local api_key = 'not_for_training'\n"+SAMPLE)
            self.assertEqual(mod.safe_sample(bad)[1],"potential_secret")
            bad.write_bytes(b"\x1bLua"+b"\x10"*300)
            self.assertEqual(mod.safe_sample(bad)[1],"bytecode")
            bad.write_text(SAMPLE,encoding="utf-8")
            self.assertEqual(mod.safe_sample(bad)[1],"eligible")

    def test_rejects_budget_and_source_under_repo(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for budget in (0,97):
                with self.assertRaises(ValueError):
                    mod.prepare(root,max_mib=budget)
        with self.assertRaisesRegex(ValueError,"fora do repositorio"):
            mod.check_root(LAB)

    @unittest.skipUnless(hasattr(os,"symlink"),"No symlink support")
    def test_skips_linked_sources(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            external=Path(temp).parent/"DO_NOT_OPEN"
            link=root/"link.lua"
            try:
                os.symlink(str(external),str(link))
            except OSError:
                self.skipTest("Symlink creation not permitted")
            paths,seen,skipped=mod.list_safe_lua(root)
            self.assertEqual(paths,[])
            self.assertEqual(seen,1)
            self.assertEqual(skipped,1)

if __name__=="__main__":
    unittest.main()
