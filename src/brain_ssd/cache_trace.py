from __future__ import annotations

import gzip
import json
import os
import random
from dataclasses import asdict
from pathlib import Path

from brain_ssd.cache_policy import CacheEvent
from brain_ssd.hybrid import HybridContextState, HybridRetrievalV0
from brain_ssd.router import SemanticIndex

TRACE_SCHEMA_VERSION = 1
WORKLOADS = (
    "stable_topic", "burst", "a_b_a", "alternating", "multi_domain",
    "long_gap_return", "random_topics", "zipf_topic_popularity", "realistic_mix",
)


def write_trace(path: Path, header: dict, events: list[CacheEvent]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with gzip.open(temporary, "wt", encoding="utf-8") as stream:
        stream.write(json.dumps({"record_type": "header", **header}, sort_keys=True) + "\n")
        for event in events:
            stream.write(json.dumps({"record_type": "access", **asdict(event)}, sort_keys=True) + "\n")
    os.replace(temporary, path)


def read_trace(path: Path) -> tuple[dict, list[CacheEvent]]:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        header_record = json.loads(next(stream))
        if header_record.pop("record_type", None) != "header" or header_record.get("schema_version") != TRACE_SCHEMA_VERSION:
            raise ValueError("unsupported trace header")
        events = []
        for line in stream:
            item = json.loads(line)
            if item.pop("record_type", None) != "access":
                raise ValueError("invalid trace record")
            item["topics"] = tuple(item["topics"])
            item["activation_provenance"] = tuple(item["activation_provenance"])
            events.append(CacheEvent(**item))
    return header_record, events


class CognitiveTraceGenerator:
    def __init__(self, index: SemanticIndex, semantic_method: str = "tfidf", semantic_threshold: float = 0.24, semantic_margin: float = 0.05, seed: int = 20260807):
        self.index = index
        self.router = HybridRetrievalV0(index, semantic_method, semantic_threshold, semantic_margin)
        self.seed = seed
        self.topics = tuple(sorted(index.topic_pages))
        self.python = ("python.json", "python.files", "python.sqlite", "python.asyncio")
        self.linux = ("files", "processes", "networking", "packages")
        self.biology = ("genetics", "cells", "evolution", "ecology")

    def _schedule(self, workload: str, turns: int, seed: int) -> list[tuple[tuple[str, ...], str]]:
        rng = random.Random(seed)
        schedule = []
        for turn in range(turns):
            if workload == "stable_topic": topics, phase = (self.python[turn % len(self.python)],), "A"
            elif workload == "burst":
                cycle = turn % 45
                topics, phase = ((self.linux[turn % 4],), "B") if 20 <= cycle < 25 else ((self.python[turn % 4],), "A" if cycle < 20 else "RETURN_A")
            elif workload == "a_b_a":
                third = max(1, turns // 3)
                if turn < third: topics, phase = (self.python[turn % 4],), "A"
                elif turn < 2 * third: topics, phase = (self.biology[turn % 4],), "B"
                else: topics, phase = (self.python[turn % 4],), "RETURN_A"
            elif workload == "alternating": topics, phase = ((self.python[turn % 4],), "A") if turn % 2 == 0 else ((self.linux[turn % 4],), "B")
            elif workload == "multi_domain": topics, phase = (self.python[turn % 4], self.linux[(turn + 1) % 4]), "MULTI"
            elif workload == "long_gap_return":
                edge = max(2, turns // 10)
                if turn < edge: topics, phase = (self.python[turn % 4],), "A"
                elif turn >= turns - edge: topics, phase = (self.python[turn % 4],), "RETURN_A"
                else: topics, phase = (self.topics[(turn * 7) % len(self.topics)],), "GAP"
            elif workload == "random_topics": topics, phase = (rng.choice(self.topics),), "RANDOM"
            elif workload == "zipf_topic_popularity":
                rank = min(len(self.topics) - 1, int(rng.paretovariate(1.4)) - 1)
                topics, phase = (self.topics[rank],), "ZIPF"
            elif workload == "realistic_mix":
                choice = turn % 10
                if choice == 0: topics, phase = (), "UNKNOWN"
                elif choice in (1, 2): topics, phase = (self.python[choice],), "CONTINUATION"
                elif choice == 3: topics, phase = ("python.asyncio",), "PARTIAL"
                elif choice == 4: topics, phase = ("nvme", "http"), "MULTI"
                elif choice == 5: topics, phase = ("checksums",), "PARAPHRASE"
                elif choice == 6: topics, phase = ("python.json",), "TYPO"
                elif choice == 7: topics, phase = ("genetics",), "SWITCH"
                else: topics, phase = (self.topics[(turn * 11) % len(self.topics)],), "MIX"
            else: raise ValueError(workload)
            schedule.append((tuple(topics), phase))
        return schedule

    def _query(self, topics: tuple[str, ...], phase: str, turn: int) -> str:
        if not topics: return "harmonia quartal para saxofone"
        if phase == "PARTIAL": return "e executar sem bloquear?"
        if phase == "PARAPHRASE": return "verificar soma criptográfica contra dano"
        if phase == "TYPO": return "pythno jsom abriir"
        pieces = []
        for topic in topics:
            page = self.index.pages[self.index.topic_pages[topic][0]]
            words = [word for word in page["keywords"] if word not in {page["domain"], *topic.split(".")}]
            pieces.append(" ".join([topic.replace(".", " "), *words[:2]]))
        return " e ".join(pieces)

    def generate(self, workload: str, turns: int, split: str, seed_offset: int = 0) -> tuple[dict, list[CacheEvent]]:
        if workload not in WORKLOADS or split not in {"development", "holdout"}:
            raise ValueError("invalid workload or split")
        schedule = self._schedule(workload, turns, self.seed + seed_offset)
        state = HybridContextState()
        events: list[CacheEvent] = []
        previous_topics: tuple[str, ...] = ()
        logical_timestamp = 0
        for turn_id, (expected_topics, phase) in enumerate(schedule):
            state.begin_turn()
            query = self._query(expected_topics, phase, turn_id)
            result = self.router.route(query, state, True)
            state.update(result.topics, {topic: 1.0 for topic in result.current_query_topics})
            required = {page for topic in expected_topics for page in self.index.topic_pages[topic][:2]}
            optional = {page for topic in expected_topics for page in self.index.topic_pages[topic][2:5]}
            transition = turn_id > 0 and set(expected_topics) != set(previous_topics)
            cognitive_state = {
                "domains": list(result.domains), "topics": list(result.topics),
                "confidence": result.post_rescue_confidence,
                "recent_topics": [topic for topic, concept in sorted(state.concepts.items(), key=lambda item: (-item[1].confidence, item[0]))[:4]],
            }
            for page_id in result.activate_pages:
                page = self.index.pages[page_id]
                events.append(CacheEvent(
                    turn_id=turn_id, query_id=f"{workload}-{split}-{turn_id}", page_id=page_id,
                    logical_timestamp=logical_timestamp, domain=page["domain"], topics=tuple(page["topics"]),
                    activation_provenance=result.page_provenance[page_id], required=page_id in required,
                    optional=page_id in optional, route_confidence=result.post_rescue_confidence,
                    cognitive_state=cognitive_state, physical_page_size=1024**2, logical_page_size=1024**2,
                    phase_label=phase, topic_transition=transition, reload_cost=1.0 + (page_id % 4) * 0.15,
                ))
                logical_timestamp += 1
            previous_topics = expected_topics
        header = {
            "schema_version": TRACE_SCHEMA_VERSION, "workload": workload, "split": split,
            "turns": turns, "event_count": len(events), "seed": self.seed + seed_offset,
            "router": "hybrid_retrieval_v0_tfidf", "logical_page_size": 1024**2,
            "ground_truth_policy_input": False,
        }
        return header, events
