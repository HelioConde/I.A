"""Adversarial false-memory guards with explicit provenance and abstention."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))

from brain_ssd.chat.episodic import EpisodicMemory
from brain_ssd.chat.memory_safety import check_memory_ambiguities, _day_names, _calendar_dates, _times, _prices


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

    def test_different_calendar_dates_need_clarification(self):
        notes=[
            episode("a","Consulta veterinária gato 04/11/2026 na clínica"),
            episode("b","Consulta veterinária gato 2026-11-05 na clínica"),
        ]
        issues=check_memory_ambiguities(notes)
        self.assertEqual([x.category for x in issues],["POSSIBLE_DIFFERENT_DATE"])
        self.assertEqual(_calendar_dates("31/02/2026"),frozenset())
        self.assertEqual(_calendar_dates("2026-11-04"),frozenset({"2026-11-04"}))

    def test_clock_formats_are_compared_conservatively(self):
        notes=[
            episode("a","Reunião projeto rover na biblioteca às 14h30"),
            episode("b","Reunião projeto rover na biblioteca às 15:30"),
        ]
        self.assertEqual([x.category for x in check_memory_ambiguities(notes)],
                         ["POSSIBLE_DIFFERENT_TIME"])
        self.assertEqual(_times("14h00"),_times("14:00"))
        self.assertEqual(_times("14h"),frozenset({"14:00"}))

    def test_prices_are_brl_only_and_never_infer_truth(self):
        notes=[
            episode("a","Preço arroz integral marca norte R$ 12,50"),
            episode("b","Preço arroz integral marca norte R$ 13,90"),
        ]
        issues=check_memory_ambiguities(notes)
        self.assertEqual(len(issues),1)
        self.assertEqual(issues[0].category,"POSSIBLE_DIFFERENT_PRICE")
        self.assertEqual(_prices("R$ 1.299,90"),frozenset({129990}))
        self.assertEqual(_prices("US$ 9,90"),frozenset())
        self.assertEqual(_prices("R$ 12,50"),frozenset({1250}))

    def test_multi_values_and_disconnected_topics_do_not_trigger(self):
        notes=[
            episode("a","Preço arroz integral marca norte R$ 12,50 ou R$ 13,90"),
            episode("b","Preço arroz integral marca norte R$ 15,00"),
        ]
        self.assertEqual(check_memory_ambiguities(notes),[])
        unrelated=[
            episode("a","Reunião do conselho bairro 14h"),
            episode("b","Consulta médica rotina 15h"),
        ]
        self.assertEqual(check_memory_ambiguities(unrelated),[])

    def test_duplicate_day_and_price_conflicts_are_only_warnings(self):
        notes=[
            episode("a","Oferta arroz integral terça R$ 12,50"),
            episode("b","Oferta arroz integral quinta R$ 14,50"),
        ]
        issues=check_memory_ambiguities(notes)
        self.assertEqual({x.category for x in issues},
                         {"POSSIBLE_DIFFERENT_WEEKDAY","POSSIBLE_DIFFERENT_PRICE"})
        self.assertEqual(len(notes),2)

    def test_explicit_query_mismatch_abstains_on_four_structured_fields(self):
        from brain_ssd.chat.memory_safety import disagrees_with_explicit_cue
        self.assertTrue(disagrees_with_explicit_cue(
            "Visita ao museu terça", "Visita ao museu quinta"
        ))
        self.assertTrue(disagrees_with_explicit_cue(
            "Consulta veterinária 05/11/2026", "Consulta veterinária 04/11/2026"
        ))
        self.assertTrue(disagrees_with_explicit_cue(
            "Reunião projeto rover às 14:00", "Reunião projeto rover às 15h"
        ))
        self.assertTrue(disagrees_with_explicit_cue(
            "Preço arroz integral R$ 12,50", "Preço arroz integral R$ 13,90"
        ))
        self.assertFalse(disagrees_with_explicit_cue(
            "Qual dia da visita ao museu?", "Visita ao museu quinta"
        ))
        self.assertFalse(disagrees_with_explicit_cue(
            "Mudou de terça para quinta?", "Visita ao museu quinta"
        ))
        self.assertFalse(disagrees_with_explicit_cue(
            "Visita terça", "Visita terça"
        ))

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
