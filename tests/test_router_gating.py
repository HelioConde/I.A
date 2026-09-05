from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brain_ssd.gating import BasalGate, CognitiveState
from brain_ssd.router import LexicalRouter, RouteResult, SemanticIndex
from brain_ssd.semantic import generate_query_dataset, generate_semantic_manifest


class RouterGatingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.manifest = generate_semantic_manifest(root / "semantic.json", 128, 77)
        self.dataset = generate_query_dataset(root / "queries.json", self.manifest, 77)
        self.index = SemanticIndex(self.manifest)
        self.router = LexicalRouter(self.index)
        self.gate = BasalGate(self.index)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_generation_and_routing_are_deterministic(self) -> None:
        root = Path(self.temporary.name)
        second = generate_semantic_manifest(root / "semantic-2.json", 128, 77)
        second_queries = generate_query_dataset(root / "queries-2.json", second, 77)
        self.assertEqual(self.manifest, second)
        self.assertEqual(self.dataset, second_queries)
        query = "como abrir json em python"
        self.assertEqual(self.router.route(query), self.router.route(query))

    def test_gate_enforces_budget_and_threshold(self) -> None:
        result = self.router.route("como abrir json em python")
        plan = self.gate.apply(result, 4)
        self.assertLessEqual(len(plan.activate_pages), 4)
        strict = BasalGate(self.index, activation_threshold=10_000).apply(result, 4)
        self.assertEqual(strict.activate_pages, ())

    def test_inhibition_and_invalid_page(self) -> None:
        biology = next(page["page_id"] for page in self.manifest["pages"] if page["domain"] == "biology")
        result = RouteResult("test", (("programming", 1.0),), (), ((biology, 1.0, "test"),), 1.0, ("biology",))
        self.assertEqual(self.gate.apply(result, 4).inhibit_pages, (biology,))
        bad = RouteResult("test", (), (), ((9999, 1.0, "bad"),), 0.0)
        with self.assertRaises(ValueError):
            self.gate.apply(bad, 4)

    def test_state_decay_and_hysteresis(self) -> None:
        result = self.router.route("como abrir json em python")
        first = self.gate.apply(result, 4)
        state = CognitiveState()
        state.update(result, first.activate_pages)
        before = dict(state.page_strength)
        state.decay(0.5)
        self.assertTrue(all(state.page_strength[key] < value for key, value in before.items()))
        empty = RouteResult("empty", (), (), (), 0.0)
        retained = self.gate.apply(empty, 4, state)
        self.assertTrue(set(retained.keep_hot_pages) <= set(first.activate_pages))
        self.assertTrue(retained.keep_hot_pages)

    def test_unknown_and_zero_budget(self) -> None:
        result = self.router.route("harmonia modal saxofone")
        self.assertEqual(result.candidate_pages, ())
        self.assertEqual(self.gate.apply(result, 0).activate_pages, ())

    def test_ground_truth_pages_are_well_formed(self) -> None:
        valid = set(self.index.pages)
        for query in self.dataset["queries"]:
            self.assertTrue(set(query["required_pages"]) <= valid)
            self.assertFalse(set(query["required_pages"]) & set(query["optional_pages"]))


if __name__ == "__main__":
    unittest.main()
