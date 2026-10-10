"""Narrow PT-BR alias checks and explicit non-generalization cases."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from brain_ssd.chat.episodic import EpisodicMemory
from brain_ssd.chat.semantic_bridge import BRIDGE_VERSION, canonical, concepts, expand_query


class TestSemanticBridge(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.memory = EpisodicMemory(Path(self.tmp.name)/"notes.sqlite3")

    def tearDown(self):
        self.tmp.cleanup()

    def test_aliases_require_explicit_flag(self):
        note = self.memory.add("A reunião do cachorro será no sábado")
        query = "Quando ocorre o encontro do cão?"
        self.assertEqual(self.memory.recall(query), [])
        hits = self.memory.recall(query, experimental_aliases=True)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["id"], note["id"])
        self.assertEqual(hits[0]["match_mode"], "SEMANTIC_ALIAS")
        self.assertEqual(set(hits[0]["matched_concepts"]), {"reuniao", "cachorro"})

    def test_exact_cues_preserve_existing_ranking(self):
        note = self.memory.add("O conserto do computador está na oficina")
        result = self.memory.recall("conserto computador", experimental_aliases=True)
        self.assertEqual(result[0]["id"], note["id"])
        self.assertEqual(result[0]["match_mode"], "LEXICAL")
        self.assertEqual(result[0]["matched_terms"], ["computador","conserto"])

    def test_single_alias_is_not_enough_for_multiword_query(self):
        self.memory.add("Meu celular está com bateria descarregada")
        self.assertEqual(self.memory.recall("smartphone calendário consulta", experimental_aliases=True), [])

    def test_unrelated_abstains_even_with_aliases(self):
        self.memory.add("Reunião na escola segunda")
        self.assertEqual(self.memory.recall("Remédio na bicicleta ontem", experimental_aliases=True), [])
        self.assertEqual(self.memory.recall("Conserto de notebook", experimental_aliases=True), [])

    def test_restarts_and_removals_are_consistent(self):
        record = self.memory.add("A escola tem computadores no laboratório")
        reopened = EpisodicMemory(self.memory.path)
        self.assertEqual(len(reopened.recall("colégio computadores", experimental_aliases=True)), 1)
        self.assertTrue(reopened.delete(record["id"]))
        self.assertEqual(reopened.recall("colégio computadores", experimental_aliases=True), [])

    def test_does_not_expand_unsafely(self):
        self.assertEqual(canonical("terça"), "terça")
        self.assertEqual(concepts(["reuniao", "encontro"]), frozenset({"reuniao"}))
        self.assertTrue(BRIDGE_VERSION)
        self.assertLessEqual(len(expand_query(["reuniao"]*40)), 2)
        with self.assertRaises(ValueError):
            expand_query(["reuniao"], max_terms=900)


if __name__ == "__main__":
    unittest.main()
