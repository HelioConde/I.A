"""Opt-in episodic memory checks: privacy, separation, negative controls."""
from __future__ import annotations
import sys
import tempfile
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from brain_ssd.chat.episodic import EpisodicMemory, words


class EpisodicTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.file = Path(self.dir.name)/"mem.sqlite3"
        self.mem = EpisodicMemory(self.file)

    def tearDown(self):
        self.dir.cleanup()

    def test_explicit_only_and_persistent(self):
        self.assertEqual(self.mem.list(), [])
        one=self.mem.add("Meu projeto favorito é o Brain-SSD")
        self.assertTrue(one["confirmed"])
        self.assertEqual(one["source"],"explicit_user")
        reopened=EpisodicMemory(self.file)
        self.assertEqual(len(reopened.list()),1)
        self.assertEqual(len(reopened.recall("Qual o meu projeto favorito?")),1)
        self.assertTrue(reopened.delete(one["id"]))
        self.assertEqual(reopened.list(),[])
        self.assertEqual(reopened.recall("projeto favorito"),[])

    def test_abstain_on_unrelated_and_insufficient_cue(self):
        self.mem.add("O tutorial de Python está na pasta pesquisa")
        self.assertEqual(self.mem.recall("O Palmeiras ganhou ontem?"),[])
        self.assertEqual(self.mem.recall("qual foi"),[])
        self.assertEqual(self.mem.recall("tutorial python")[0]["matched_terms"],["python","tutorial"])

    def test_distinct_similar_episodes_not_overwritten(self):
        self.mem.add("A reunião sobre Python será na terça")
        self.mem.add("A reunião sobre Python será na quinta")
        hits=self.mem.recall("reunião Python")
        self.assertEqual(len(hits),2)
        self.assertNotEqual(hits[0]["id"],hits[1]["id"])

    def test_sqlite_confirmed_field_is_boolean_after_reopen(self):
        self.mem.add("Reunião do projeto rover terça na biblioteca")
        self.mem.add("Reunião do projeto rover quinta na biblioteca")
        reopened=EpisodicMemory(self.file)
        listed=reopened.list()
        self.assertEqual(len(listed),2)
        self.assertTrue(all(row["confirmed"] is True for row in listed))
        from brain_ssd.chat.cognitive_lab import replay_preview, propose_associations
        preview=replay_preview(listed)
        self.assertEqual(len(preview.candidate_ids),2)
        self.assertEqual(len(propose_associations(listed)),1)

    def test_long_question_prioritizes_recent_unique_cues(self):
        note=self.mem.add("Projeto rover biblioteca norte")
        filler=" ".join("termo"+str(i).zfill(3) for i in range(45))
        found=self.mem.recall(filler+" projeto rover biblioteca")
        self.assertEqual(len(found),1)
        self.assertEqual(found[0]["id"],note["id"])

    def test_invalid_and_long_note_rejected(self):
        for note in ("  ","A"*501, {"text":"x"}):
            with self.assertRaises(ValueError):
                self.mem.add(note)
        with self.assertRaises(ValueError):
            self.mem.delete("../../secret")
        self.assertEqual(words("MemÓria de Pesquisa"),frozenset({"memoria","pesquisa"}))

    def test_offline_replay_only_returns_candidates(self):
        note=self.mem.add("Planejamento de tarefas para o Brain-SSD")
        self.assertEqual(self.mem.replay_candidates()[0]["id"],note["id"])
        self.assertEqual(self.mem.list()[0]["content"],note["content"])

if __name__=="__main__":
    unittest.main()
