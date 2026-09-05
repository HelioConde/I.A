from __future__ import annotations

import random
from enum import Enum


class Workload(str, Enum):
    SEQUENTIAL = "sequential"
    UNIFORM_RANDOM = "uniform_random"
    HOT_SET = "hot_set"
    CLUSTERED = "clustered"
    TOPIC_SWITCH = "topic_switch"
    ASSOCIATIVE_WALK = "associative_walk"


def access_sequence(kind: Workload, page_ids: list[int], accesses: int, seed: int, related: dict[int, tuple[int, ...]]) -> list[int]:
    if not page_ids or accesses < 1:
        raise ValueError("page_ids must be non-empty and accesses >= 1")
    rng = random.Random(seed)
    if kind == Workload.SEQUENTIAL:
        return [page_ids[index % len(page_ids)] for index in range(accesses)]
    if kind == Workload.UNIFORM_RANDOM:
        return [rng.choice(page_ids) for _ in range(accesses)]
    if kind == Workload.HOT_SET:
        hot = page_ids[:max(1, len(page_ids) // 5)]
        return [rng.choice(hot if rng.random() < 0.8 else page_ids) for _ in range(accesses)]
    if kind == Workload.CLUSTERED:
        cluster_size = max(1, len(page_ids) // 4)
        result = []
        start = 0
        for index in range(accesses):
            if index and index % 8 == 0:
                start = rng.randrange(max(1, len(page_ids) - cluster_size + 1))
            result.append(rng.choice(page_ids[start:start + cluster_size]))
        return result
    if kind == Workload.TOPIC_SWITCH:
        half = max(1, len(page_ids) // 2)
        topic_a, topic_b = page_ids[:half], page_ids[half:] or page_ids[:half]
        third = max(1, accesses // 3)
        topics = [topic_a] * third + [topic_b] * third + [topic_a] * (accesses - 2 * third)
        return [rng.choice(topic) for topic in topics]
    if kind == Workload.ASSOCIATIVE_WALK:
        allowed = set(page_ids)
        current = rng.choice(page_ids)
        result = []
        for _ in range(accesses):
            result.append(current)
            linked = [item for item in related.get(current, ()) if item in allowed]
            current = rng.choice(linked) if linked and rng.random() < 0.85 else rng.choice(page_ids)
        return result
    raise ValueError(f"unknown workload: {kind}")

