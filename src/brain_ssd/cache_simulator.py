from __future__ import annotations

import bisect
import statistics
import time
from collections import defaultdict

from brain_ssd.cache_policy import CacheEvent, CachePolicy


def percentile(values: list[float], fraction: float) -> float:
    if not values: return 0.0
    ordered = sorted(values); position = (len(ordered) - 1) * fraction
    low, high = int(position), min(int(position) + 1, len(ordered) - 1)
    return ordered[low] * (high - position) + ordered[high] * (position - low) if high != low else ordered[low]


def simulate(policy: CachePolicy, events: list[CacheEvent], regret_windows=(1, 2, 4, 8, 16)) -> dict:
    access_turns: dict[int, list[int]] = defaultdict(list)
    for event in events: access_turns[event.page_id].append(event.turn_id)
    hits = misses = hit_bytes = miss_bytes = cold_loads = eviction_count = 0
    admitted_turn: dict[int, int] = {}
    reused_since_admit: dict[int, bool] = {}
    pollution_bytes = pollution_turns = useful_residency_turns = 0
    evictions: list[tuple[int, int]] = []
    total_us: list[float] = []; observe_us: list[float] = []; choose_us: list[float] = []
    churn_by_turn: dict[int, int] = defaultdict(int)
    transition_misses = transition_accesses = return_misses = return_accesses = return_hits = 0
    current_turn = None
    for event in events:
        if event.turn_id != current_turn:
            policy.update_state(event.turn_id, event.cognitive_state)
            current_turn = event.turn_id
        started = time.perf_counter_ns()
        decision = policy.observe_access(event)
        total = time.perf_counter_ns() - started
        choose = getattr(policy, "last_choose_ns", 0)
        total_us.append(total / 1000); choose_us.append(choose / 1000); observe_us.append(max(0, total - choose) / 1000)
        if decision.hit:
            hits += 1; hit_bytes += event.logical_page_size; reused_since_admit[event.page_id] = True
        else:
            misses += 1; miss_bytes += event.logical_page_size; cold_loads += 1
        if event.topic_transition:
            transition_accesses += 1; transition_misses += not decision.hit
        if event.phase_label == "RETURN_A":
            return_accesses += 1; return_misses += not decision.hit; return_hits += decision.hit
        if decision.admitted:
            admitted_turn[event.page_id] = event.turn_id; reused_since_admit[event.page_id] = False; churn_by_turn[event.turn_id] += 1
        for victim in decision.evicted_pages:
            eviction_count += 1; churn_by_turn[event.turn_id] += 1; evictions.append((victim, event.turn_id))
            residency = max(0, event.turn_id - admitted_turn.pop(victim, event.turn_id))
            if reused_since_admit.pop(victim, False): useful_residency_turns += residency
            else: pollution_bytes += event.logical_page_size; pollution_turns += residency
    final_turn = max((event.turn_id for event in events), default=0)
    for page in policy.resident:
        residency = max(0, final_turn - admitted_turn.get(page, final_turn) + 1)
        if reused_since_admit.get(page, False): useful_residency_turns += residency
        else:
            page_size = next((event.logical_page_size for event in reversed(events) if event.page_id == page), 0)
            pollution_bytes += page_size; pollution_turns += residency
    regret = {}
    for window in regret_windows:
        regretted = 0
        for page, turn in evictions:
            turns = access_turns[page]; position = bisect.bisect_right(turns, turn)
            if position < len(turns) and turns[position] - turn <= window: regretted += 1
        regret[str(window)] = {"count": regretted, "rate": regretted / eviction_count if eviction_count else 0.0}
    total_bytes = hit_bytes + miss_bytes
    turns = len({event.turn_id for event in events})
    stats = policy.stats()
    return {
        "policy": policy.name, "budget_pages": policy.budget_pages, "accesses": len(events),
        "page_hit_rate": hits / len(events) if events else 0.0,
        "byte_hit_rate": hit_bytes / total_bytes if total_bytes else 0.0,
        "miss_bytes": miss_bytes, "cold_load_count": cold_loads, "eviction_count": eviction_count,
        "eviction_regret": regret, "pollution_bytes": pollution_bytes,
        "pollution_residency_turns": pollution_turns, "useful_residency_turns": useful_residency_turns,
        "cache_churn_pages_total": sum(churn_by_turn.values()),
        "cache_churn_pages_per_turn_mean": sum(churn_by_turn.values()) / turns if turns else 0.0,
        "cache_churn_pages_per_turn_max": max(churn_by_turn.values(), default=0),
        "reactivation_hit_rate": return_hits / return_accesses if return_accesses else None,
        "return_cost_bytes": return_misses * (events[0].logical_page_size if events else 0),
        "topic_transition_miss_count": transition_misses, "topic_transition_accesses": transition_accesses,
        "topic_transition_cost_bytes": transition_misses * (events[0].logical_page_size if events else 0),
        "decision_overhead_us": {
            "observe_p50": percentile(observe_us, .5), "observe_p95": percentile(observe_us, .95), "observe_p99": percentile(observe_us, .99),
            "choose_p50": percentile(choose_us, .5), "choose_p95": percentile(choose_us, .95), "choose_p99": percentile(choose_us, .99),
            "total_p50": percentile(total_us, .5), "total_p95": percentile(total_us, .95), "total_p99": percentile(total_us, .99),
            "cpu_proxy_total_us": sum(total_us),
        },
        "metadata_bytes": stats["metadata_bytes_estimated"], "resident_pages_final": stats["resident_pages"],
    }
