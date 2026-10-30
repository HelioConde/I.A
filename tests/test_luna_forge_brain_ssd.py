"""Standard-library regression tests for Luna Forge Zero's Brain-SSD adapter."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "experiments" / "luna-forge-zero" / "brain_ssd_bridge.py"
spec = importlib.util.spec_from_file_location("luna_forge_bridge", PATH)
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)

class TestLunaForgeBrainSSD(unittest.TestCase):
    def test_router(self):
        self.assertEqual(bridge.select_model("Crie um jogo de plataforma com pulo"), "plan")
        self.assertEqual(bridge.select_model("Escreva codigo GDScript"), "code")
        self.assertEqual(bridge.select_model("GDScript",mode="plan"), "plan")
        with self.assertRaises(ValueError):
            bridge.select_model("teste",mode="other")

    def test_actual_brain_ssd_mmap_backend_and_page_checksum(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            report = bridge.build_knowledge(root, [
                {"title":"Godot colisão","text":"Use CharacterBody2D com move_and_slide"},
                {"title":"Canvas pulo","text":"Use requestAnimationFrame e gravidade"}])
            self.assertEqual(report["pages"],2)
            with bridge.skill_pages(root,"Godot colisão") as result:
                self.assertEqual(result["storage"],"brain_ssd.storage.MMapStorageBackend")
                self.assertEqual(result["page_reads"],1)
                self.assertEqual(result["logical_bytes"],4096)
                self.assertIn("CharacterBody2D",result["skills"][0]["text"])
            with (root/"brain.dat").open("r+b") as stream:
                stream.write(b"CORRUPTED")
            with self.assertRaises(Exception):
                with bridge.skill_pages(root,"Godot colisão"):
                    pass

    def test_feedback_is_pending_review_only(self):
        with tempfile.TemporaryDirectory() as temp:
            db=Path(temp)/"feedback.sqlite3"
            self.assertEqual(bridge.add_feedback(db,"luna","Pulo","código inacabado"),1)
            from contextlib import closing
            with closing(sqlite3.connect(db)) as connection:
                value=connection.execute("SELECT approved FROM feedback").fetchone()[0]
            self.assertEqual(value,0)

    def test_does_not_require_checkpoints_for_status(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertFalse((Path(temp)/"weights.pt").exists())
            self.assertTrue(PATH.exists())

if __name__=="__main__":
    unittest.main()
