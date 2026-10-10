"""Adversarial false-memory guards with explicit provenance and abstention."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))

from brain_ssd.chat.episodic import EpisodicMemory
from brain_ssd.chat.memory_safety import check_memory_ambiguities, _day_names


def episode(identifier, message):
    return {"id":identifier,"content":message,"confirmed":True,"source":"explicit_user"}


class TestMemorySafety(unittest.TestCase):
    def test_weekdays_are_normalized_in_portuguese(self):
        self.assertEqual(_day_names("TERÇA-FEIRA"),frozenset({"terca"}))
        self.assertEqual(_day_names("sábado"),frozenset({"sabado"}))
        self.assertEqual(_day_names("quarta feira"),frozenset({"quarta"}))
        self.assertEqual(_day_names("quarto, quinto, sexto"),frozenset())

    def test_same_event_anchors_different_days_need_clarification(self):
        records=[
            episode("a","Reunião projeto rover terça na biblioteca norte"),
            episode("b","Reunião projeto rover quinta na biblioteca norte"),
        ]
        matches=check_memory_ambiguities(records)
        self.assertEqual(len(matches),1)
        self.assertEqual(matches[0].category,"POSSIBLE_DIFFERENT_WEEKDAY")
        self.assertEqual(matches[0].source_ids,("a","b"))
        # The checker NEVER overwrites/combines the source evidence.
        self.assertEqual(len(records),2)

    def test_no_false_alarm_for_unrelated_and_same_weekday(self):
        records=[
            episode("a","Treino de futebol terça no parque"),
            episode("b","Reunião da equipe Python quinta no escritório"),
            episode("c","Treino de futebol terça no parque"),
        ]
        self.assertEqual(check_memory_ambiguities(records),[])

    def test_missing_source_and_uncertain_multi_day_notes_are_not_promoted(self):
        records=[
            episode("a","Reunião do projeto rover terça e quinta na biblioteca"),
            episode("b","Reunião do projeto rover segunda na biblioteca"),
            {"id":"c","content":"Reunião do projeto rover sexta na biblioteca",
             "confirmed":False,"source":"model_guess"},
        ]
        self.assertEqual(check_memory_ambiguities(records),[])

    def test_deleted_notes_no_longer_participate(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=EpisodicMemory(Path(tmp)/"episodes.sqlite3")
            left=db.add("Reunião projeto rover terça biblioteca norte")
            right=db.add("Reunião projeto rover quinta biblioteca norte")
            first=db.recall("Reunião rover biblioteca")
            self.assertEqual(len(first),2)
            self.assertEqual(len(check_memory_ambiguities(first)),1)
            self.assertTrue(db.delete(left["id"]))
            after=db.recall("Reunião rover biblioteca")
            self.assertEqual(len(after),1)
            self.assertEqual(check_memory_ambiguities(after),[])
            self.assertEqual(after[0]["id"],right["id"])

if __name__=="__main__":
    unittest.main()
