from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from test_router_gating import ROOT

from brain_ssd.gating import CognitiveState
from brain_ssd.progressive import LexicalProgressiveRouter
from brain_ssd.recall_dataset import generate_recall_dataset
from brain_ssd.router import SemanticIndex
from brain_ssd.semantic import generate_semantic_manifest


class ProgressiveRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.manifest = generate_semantic_manifest(root / "semantic.json", 1024, 20260807)
        self.dataset = generate_recall_dataset(root / "queries.json", self.manifest)
        self.index = SemanticIndex(self.manifest)
        self.router = LexicalProgressiveRouter(self.index)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_progressive_budget_and_early_stop_do_not_fill_cap(self) -> None:
        result = self.router.route("decodificar documento JSON no Python")
        self.assertEqual(result.initial_budget_mib, 4)
        self.assertEqual(result.final_budget_mib, 4)
        self.assertEqual(result.expansion_count, 0)
        self.assertEqual(len(result.activate_pages), 2)
        self.assertLess(result.budget_used_mib, result.final_budget_mib)

    def test_decomposition_and_multi_domain(self) -> None:
        result = self.router.route("expor NVMe através de API HTTP")
        self.assertIn("nvme", result.topics)
        self.assertIn("http", result.topics)
        self.assertGreaterEqual(len(result.analysis.groups), 1)
        self.assertGreaterEqual(len(result.domains), 2)

    def test_contextual_partial_cue_recovers_async(self) -> None:
        state = CognitiveState(current_domain="programming", current_topics=("python.files", "python.json"), topic_confidence=0.9)
        result = self.router.route("e executar sem bloquear?", state, use_context=True)
        self.assertTrue(result.analysis.partial_cue)
        self.assertTrue(result.analysis.context_terms)
        self.assertIn("python.asyncio", result.topics)

    def test_unknown_is_safe_and_never_all_domain(self) -> None:
        result = self.router.route("harmonia quartal saxofone")
        self.assertEqual(result.status, "NO_KNOWLEDGE")
        self.assertEqual(result.activate_pages, ())
        self.assertNotIn("all_domain_limited", result.fallback_levels)

    def test_adaptive_hysteresis_and_topic_switch(self) -> None:
        state = CognitiveState(current_domain="programming", current_topics=("python.json",), topic_confidence=1.0)
        state.page_strength = {0: 1.0, 39: 0.8}
        state.page_age = {0: 0, 39: 0}
        continuation = self.router.route("e depois salvar no banco", state)
        switch = self.router.route("agora explique DNA genética herança", state)
        self.assertGreaterEqual(continuation.hysteresis_budget_fraction, 0.0)
        self.assertEqual(switch.hysteresis_budget_fraction, 0.0)
        self.assertGreaterEqual(switch.analysis.new_topic_score, 0.75)

    def test_fallback_hierarchy_and_insufficient_status(self) -> None:
        result = self.router.route("expor dados do NVMe através de API HTTP")
        self.assertIn("budget_expansion", result.fallback_levels)
        self.assertIn("all_domain_limited", result.fallback_levels)
        self.assertEqual(result.status, "INSUFFICIENT_RETRIEVAL_CONFIDENCE")

    def test_confidence_signals_are_exposed(self) -> None:
        result = self.router.route("abrir json python")
        unknown = self.router.route("harmonia quartal saxofone")
        self.assertGreater(result.signals.query_coverage, 0)
        self.assertGreaterEqual(result.signals.score_gap, 0)
        self.assertGreaterEqual(result.signals.unknown_token_ratio, 0)
        self.assertLessEqual(result.signals.confidence, 1)
        self.assertGreater(result.signals.confidence, unknown.signals.confidence)

    def test_determinism_and_holdout_separation(self) -> None:
        query = "PYHTON abriir JsOn"
        first, second = self.router.route(query), self.router.route(query)
        self.assertEqual(first.activate_pages, second.activate_pages)
        self.assertEqual(first.topics, second.topics)
        self.assertEqual(first.fallback_levels, second.fallback_levels)
        self.assertEqual(first.status, second.status)
        development = {item["query_id"] for item in self.dataset["queries"] if item["split"] == "development"}
        holdout = {item["query_id"] for item in self.dataset["queries"] if item["split"] == "holdout"}
        self.assertTrue(development)
        self.assertTrue(holdout)
        self.assertFalse(development & holdout)


if __name__ == "__main__":
    unittest.main()
