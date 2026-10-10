"""Consolidation never promotes or fabricates knowledge without human review."""
from __future__ import annotations
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from brain_ssd.chat.episodic import EpisodicMemory
from brain_ssd.chat.consolidation import ConsolidationQueue


class TestOfflineConsolidation(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        root=Path(self.temp.name)
        self.episodes=EpisodicMemory(root/"notes.sqlite3")
        self.queue=ConsolidationQueue(root/"review.sqlite3",self.episodes)
        self.a=self.episodes.add("Reunião do projeto rover terça na biblioteca")
        self.b=self.episodes.add("Reunião do projeto rover quinta na biblioteca")
        self.other=self.episodes.add("Receita de bolo de laranja")

    def tearDown(self):
        self.temp.cleanup()

    def test_draft_has_provenance_and_requires_manual_review(self):
        draft=self.queue.create_draft([self.a["id"],self.b["id"]])
        self.assertEqual(draft["state"],"DRAFT")
        self.assertIn("rover",draft["shared_cues"])
        self.assertIsNone(draft["summary"])
        self.assertEqual(len(self.episodes.list()),3)
        with self.assertRaises(ValueError):
            self.queue.review(draft["id"],"approve",None)
        reviewed=self.queue.review(draft["id"],"approve","Duas reuniões distintas sobre o projeto rover")
        self.assertEqual(reviewed["state"],"REVIEWED")
        self.assertEqual(reviewed["source_ids"],[self.a["id"],self.b["id"]])
        self.assertTrue(self.queue.revoke(draft["id"]))
        self.assertEqual(self.queue.list()[0]["state"],"REVOKED")
        self.assertFalse(self.queue.revoke(draft["id"]))
        self.assertTrue(self.queue.delete(draft["id"]))

    def test_missing_conflicting_and_duplicate_inputs_abstain(self):
        with self.assertRaises(ValueError):
            self.queue.create_draft([self.a["id"],self.other["id"]])
        with self.assertRaises(ValueError):
            self.queue.create_draft([self.a["id"],self.a["id"]])
        draft=self.queue.create_draft([self.a["id"],self.b["id"]])
        self.assertTrue(self.episodes.delete(self.b["id"]))
        with self.assertRaises(ValueError):
            self.queue.review(draft["id"],"approve","Ambas as reuniões")
        self.assertEqual(self.queue.list()[0]["state"],"DRAFT")

    def test_edited_source_invalidates_draft_and_approved_review(self):
        first=self.queue.create_draft([self.a["id"],self.b["id"]])
        initial=self.queue.review(first["id"],"approve","Duas reuniões sobre rover")
        self.assertEqual(initial["effective_state"],"REVIEWED")
        draft=self.queue.create_draft([self.a["id"],self.b["id"]])
        changed=self.episodes.replace(
            self.a["id"],"Reunião do projeto rover sexta na biblioteca",
            expected_content=self.a["content"])
        self.assertTrue(changed["changed"])
        self.assertEqual(self.queue._row(first["id"])["effective_state"],
                         "SOURCE_CHANGED_OR_UNVERIFIED")
        with self.assertRaises(ValueError):
            self.queue.review(draft["id"],"approve","Resumir nota corrigida")
        current=self.queue.create_draft([self.a["id"],self.b["id"]])
        fresh=self.queue.review(current["id"],"approve","Reuniões com nota corrigida")
        self.assertEqual(fresh["effective_state"],"REVIEWED")

    def test_missing_source_invalidates_approved_review(self):
        draft=self.queue.create_draft([self.a["id"],self.b["id"]])
        self.queue.review(draft["id"],"approve","Resumo revisado")
        self.episodes.delete(self.a["id"])
        stale=self.queue._row(draft["id"])
        self.assertEqual(stale["effective_state"],"SOURCE_DELETED")
        self.assertTrue(self.queue.revoke(draft["id"]))

    def test_rejection_and_reopen_are_persistent(self):
        draft=self.queue.create_draft([self.a["id"],self.b["id"]])
        rejected=self.queue.review(draft["id"],"reject")
        self.assertEqual(rejected["state"],"REJECTED")
        reopened=ConsolidationQueue(self.queue.path,self.episodes)
        self.assertEqual(reopened.list()[0]["state"],"REJECTED")
        with self.assertRaises(ValueError):
            reopened.review(draft["id"],"approve","Outro texto")


if __name__=="__main__":
    unittest.main()
