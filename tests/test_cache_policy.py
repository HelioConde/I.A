from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from test_router_gating import ROOT

from brain_ssd.cache_policy import (
    AdaptiveTwoQueuePolicy, BeladyOraclePolicy, CacheEvent, CognitiveCacheV0,
    LFUPolicy, LRFUPolicy, LRUPolicy, NoCachePolicy,
)
from brain_ssd.cache_simulator import simulate
from brain_ssd.cache_trace import read_trace, write_trace


def event(page: int, timestamp: int, turn: int | None = None, topic: str = "python.json", phase: str = "") -> CacheEvent:
    return CacheEvent(
        turn_id=timestamp if turn is None else turn, query_id=f"q{timestamp}", page_id=page,
        logical_timestamp=timestamp, domain="programming", topics=(topic,),
        activation_provenance=("CURRENT_QUERY",), required=None, optional=None,
        route_confidence=1.0, cognitive_state={"topics": [topic], "confidence": 1.0},
        physical_page_size=1024**2, logical_page_size=1024**2, phase_label=phase,
        topic_transition=False, reload_cost=1.0,
    )


class CachePolicyTests(unittest.TestCase):
    def test_lru_budget_eviction_and_no_duplicates(self) -> None:
        policy = LRUPolicy(2)
        for item in (event(1, 0), event(2, 1), event(1, 2), event(3, 3)):
            policy.update_state(item.turn_id, item.cognitive_state); policy.observe_access(item)
        self.assertEqual(policy.resident, {1, 3})
        self.assertEqual(len(policy.resident), 2)
        self.assertEqual(policy.evictions, 1)

    def test_lfu_uses_lru_tie_break(self) -> None:
        policy = LFUPolicy(2)
        for item in (event(1, 0), event(2, 1), event(1, 2), event(3, 3)):
            policy.observe_access(item)
        self.assertEqual(policy.resident, {1, 3})

    def test_all_online_policies_enforce_budget_deterministically(self) -> None:
        sequence = [event(page, index) for index, page in enumerate((1, 2, 3, 1, 4, 2, 1))]
        for constructor in (LRUPolicy, LFUPolicy, LRFUPolicy, AdaptiveTwoQueuePolicy, CognitiveCacheV0):
            first, second = constructor(3), constructor(3)
            decisions = []
            for policy in (first, second):
                current = []
                for item in sequence:
                    policy.update_state(item.turn_id, item.cognitive_state); current.append(policy.observe_access(item))
                    self.assertLessEqual(len(policy.resident), 3)
                decisions.append([(decision.hit, decision.evicted_pages) for decision in current])
            self.assertEqual(decisions[0], decisions[1])

    def test_no_cache_is_all_miss_and_unknown_does_not_mutate(self) -> None:
        policy = NoCachePolicy()
        result = simulate(policy, [event(1, 0), event(1, 1)])
        self.assertEqual(result["page_hit_rate"], 0)
        cognitive = CognitiveCacheV0(4)
        cognitive.observe_access(event(1, 0))
        before = set(cognitive.resident)
        cognitive.update_state(1, {"topics": [], "status": "NO_KNOWLEDGE"})
        self.assertEqual(cognitive.resident, before)

    def test_cognitive_decay_topic_switch_and_hysteresis_components(self) -> None:
        policy = CognitiveCacheV0(4)
        first = event(1, 0, topic="python.json")
        policy.observe_access(first)
        switched = event(2, 1, topic="genetics")
        components = policy.score_components(1, switched)
        self.assertEqual(components["topic"], 0)
        self.assertGreater(components["age"], 0)
        self.assertGreater(components["hysteresis"], 0)

    def test_a_b_a_reactivation_and_regret_metrics(self) -> None:
        events = [event(1, 0, phase="A"), event(2, 1, phase="B"), event(1, 2, phase="RETURN_A")]
        result = simulate(LRUPolicy(1), events)
        self.assertEqual(result["reactivation_hit_rate"], 0)
        self.assertGreater(result["return_cost_bytes"], 0)
        self.assertGreater(result["eviction_regret"]["2"]["rate"], 0)

    def test_belady_is_no_worse_than_lru(self) -> None:
        events = [event(page, index) for index, page in enumerate((1, 2, 3, 1, 2, 3, 1))]
        lru = simulate(LRUPolicy(2), events)
        oracle = simulate(BeladyOraclePolicy(2, events), events)
        self.assertLessEqual(oracle["miss_bytes"], lru["miss_bytes"])

    def test_trace_round_trip_and_metadata_accounting(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "trace.jsonl.gz"
            events = [event(1, 0), event(2, 1)]
            write_trace(path, {"schema_version": 1, "workload": "unit"}, events)
            header, loaded = read_trace(path)
            self.assertEqual(header["workload"], "unit")
            self.assertEqual(loaded, events)
        policy = CognitiveCacheV0(2)
        policy.observe_access(event(1, 0))
        self.assertGreater(policy.metadata_bytes(), 0)


if __name__ == "__main__":
    unittest.main()
