from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from test_router_gating import ROOT

from brain_ssd.hybrid import HybridContextState, HybridRetrievalV0, SparseSemanticIndex
from brain_ssd.router import SemanticIndex
from brain_ssd.semantic import generate_semantic_manifest
from brain_ssd.semantic_rescue_dataset import generate_semantic_rescue_dataset


class HybridRetrievalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.manifest = generate_semantic_manifest(root / "semantic.json", 1024)
        self.dataset = generate_semantic_rescue_dataset(root / "queries.json", self.manifest)
        self.index = SemanticIndex(self.manifest)
        self.router = HybridRetrievalV0(self.index, "tfidf")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_fast_exact_path_stops_without_semantic(self) -> None:
        result = self.router.route("parse JSON Python")
        self.assertFalse(result.semantic_used)
        self.assertEqual(result.resolved_level, "LEVEL_0_EXACT")
        self.assertEqual(len(result.activate_pages), 2)

    def test_fuzzy_typo_and_character_index(self) -> None:
        result = self.router.route("pythno jsom abrir")
        self.assertGreater(result.fuzzy_match_count, 0)
        self.assertIn("python.json", result.topics)
        char = SparseSemanticIndex(self.index, "char_ngram")
        self.assertTrue(char.query("assincrono non-blocking"))
        self.assertGreater(char.serialized_size_bytes, 0)

    def test_semantic_rescue_and_rerank(self) -> None:
        result = self.router.route("transformar texto estruturado em objetos")
        self.assertTrue(result.semantic_used)
        self.assertIn("python.json", result.topics)
        self.assertEqual(result.activate_pages, tuple(self.index.topic_pages["python.json"][:2]))
        self.assertTrue(all("SEMANTIC_RESCUE" in value for value in result.page_provenance.values()))

    def test_concept_coverage_precedes_redundancy(self) -> None:
        result = self.router.route("NVMe através de API HTTP")
        activated_topics = [self.index.pages[page]["topics"][0] for page in result.activate_pages]
        self.assertEqual(activated_topics.count("nvme"), 2)
        self.assertEqual(activated_topics.count("http"), 2)
        self.assertEqual(len(result.activate_pages), 4)
        self.assertTrue(any(item.redundancy_penalty > 0 for item in result.evidence))

    def test_context_gate_modulation_does_not_expand_full_query(self) -> None:
        state = HybridContextState()
        state.update(("python.json", "python.files"), {"python.json": 1, "python.files": 1})
        state.begin_turn()
        result = self.router.route("explique completamente DNA genes herança", state)
        self.assertEqual(result.topics, ("genetics",))
        self.assertFalse(result.context_expansion_topics)
        self.assertFalse(any("CONTEXT_EXPANSION" in sources for sources in result.page_provenance.values()))

    def test_partial_context_expansion_and_contextual_alias(self) -> None:
        state = HybridContextState()
        state.update(("python.sqlite",), {"python.sqlite": 1})
        state.begin_turn()
        result = self.router.route("e na base?", state)
        self.assertGreaterEqual(result.partial_probability, self.router.partial_threshold)
        self.assertIn("python.sqlite", result.topics)
        self.assertGreater(result.alias_expansion_count, 0)

    def test_context_decay_is_per_concept(self) -> None:
        state = HybridContextState()
        state.update(("python.json",), {"python.json": 1})
        before = state.concepts["python.json"].confidence
        state.begin_turn()
        self.assertLess(state.concepts["python.json"].confidence, before)
        self.assertEqual(state.concepts["python.json"].age, 1)

    def test_unknown_and_nearest_neighbor_traps_are_safe(self) -> None:
        for query in ("harmonia quartal saxofone", "rede harmônica para improvisação musical", "servidor doméstico de receitas"):
            result = self.router.route(query)
            self.assertEqual(result.status, "NO_KNOWLEDGE")
            self.assertEqual(result.activate_pages, ())
            self.assertFalse(result.all_domain_used)

    def test_activation_provenance_and_evidence_are_complete(self) -> None:
        result = self.router.route("pythno jsom abrir")
        self.assertEqual(set(result.activate_pages), set(result.page_provenance))
        self.assertEqual(set(result.activate_pages), {item.page_id for item in result.evidence})
        self.assertTrue(all(item.combined_score > 0 for item in result.evidence))

    def test_deterministic_decision_ignoring_timings(self) -> None:
        first = self.router.route("armazenamento flash baixa latência")
        second = self.router.route("armazenamento flash baixa latência")
        self.assertEqual(first.activate_pages, second.activate_pages)
        self.assertEqual(first.topics, second.topics)
        self.assertEqual(first.page_provenance, second.page_provenance)
        self.assertEqual(first.status, second.status)

    def test_development_and_holdout_are_disjoint(self) -> None:
        development = {item["query_id"] for item in self.dataset["queries"] if item["split"] == "development"}
        holdout = {item["query_id"] for item in self.dataset["queries"] if item["split"] == "holdout"}
        self.assertTrue(development and holdout)
        self.assertFalse(development & holdout)

    def test_development_has_no_false_early_stop_at_default_threshold(self) -> None:
        states: dict[str, HybridContextState] = {}
        for query in self.dataset["queries"]:
            if query["split"] != "development":
                continue
            state = None
            if query["sequence_id"]:
                state = states.setdefault(query["sequence_id"], HybridContextState())
                state.begin_turn()
            result = self.router.route(query["query"], state)
            if state:
                state.update(result.topics, {topic: 1 for topic in result.current_query_topics})
            if query["required_pages"] and result.status == "OK":
                self.assertTrue(set(query["required_pages"]) <= set(result.activate_pages))


if __name__ == "__main__":
    unittest.main()
