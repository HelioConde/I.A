"""Read-only memory database audit, including corruption and privacy."""
from __future__ import annotations
import json
from contextlib import closing
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from brain_ssd.chat.episodic import EpisodicMemory
from brain_ssd.chat.episodic_integrity import audit_episodic_database


class TestIntegrity(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.db=Path(self.temp.name)/"notes.sqlite3"

    def tearDown(self):
        self.temp.cleanup()

    def test_missing_does_not_create_database(self):
        report=audit_episodic_database(self.db)
        self.assertEqual(report["status"],"MISSING")
        self.assertFalse(self.db.exists())

    def test_good_database_survives_edit_reopen_undo_delete(self):
        db=EpisodicMemory(self.db)
        first=db.add("Segredo de teste pessoal: A senha não é para o relatório")
        second=db.add("Visita museu agendada terça")
        revised=db.replace(second["id"],"Visita museu agendada quinta",
                           expected_content=second["content"])
        report=audit_episodic_database(self.db)
        self.assertEqual(report["status"],"OK")
        self.assertEqual(report["episode_count"],2)
        self.assertEqual(report["revision_count"],1)
        db.restore(second["id"],revised["revision_id"],expected_content=revised["content"])
        self.assertEqual(audit_episodic_database(self.db)["status"],"OK")
        db.delete(second["id"])
        result=audit_episodic_database(self.db)
        self.assertEqual(result["status"],"OK")
        self.assertEqual(result["revision_count"],0)
        self.assertNotIn("senha",json.dumps(result,ensure_ascii=False).lower())
        self.assertNotIn(str(self.db),json.dumps(result))
        self.assertEqual(db.recall("segredo pessoal")[0]["id"],first["id"])

    def test_missing_and_stale_index_terms_detected_without_repair(self):
        db=EpisodicMemory(self.db)
        item=db.add("Projeto rover sensor lidar")
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute("DELETE FROM episode_terms WHERE episode_id=? AND term=?",
                         (item["id"],"lidar"))
            conn.execute("INSERT INTO episode_terms VALUES (?,?)",(item["id"],"inventado"))
            conn.commit()
        report=audit_episodic_database(self.db)
        self.assertEqual(report["status"],"ISSUES_FOUND")
        self.assertEqual(report["missing_index_terms"],1)
        self.assertEqual(report["stale_index_terms"],1)
        self.assertEqual(report["read_only"],True)
        # Audit must not modify or repair the user's database implicitly.
        self.assertEqual(audit_episodic_database(self.db)["missing_index_terms"],1)

    def test_orphan_revisions_detected(self):
        db=EpisodicMemory(self.db)
        with sqlite3.connect(self.db) as conn:
            conn.execute("PRAGMA foreign_keys=OFF")
            conn.execute("INSERT INTO episode_revisions VALUES(?,?,?,?,?,?)",
                         ("00000000-0000-0000-0000-000000000001",
                          "00000000-0000-0000-0000-000000000002",
                          "antigo","novo",0,"EDIT"))
            conn.commit()
        report=audit_episodic_database(self.db)
        self.assertEqual(report["status"],"ISSUES_FOUND")
        self.assertEqual(report["orphan_revisions"],1)

    def test_bad_file_returns_generic_status(self):
        self.db.write_text("private password TEST_TOKEN",encoding="utf-8")
        report=audit_episodic_database(self.db)
        self.assertEqual(report["status"],"UNREADABLE")
        self.assertNotIn("TEST_TOKEN",json.dumps(report))


if __name__=="__main__":
    unittest.main()
