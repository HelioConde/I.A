from __future__ import annotations

import json
import mmap
import os
import statistics
import time
from collections import defaultdict, deque
from dataclasses import replace
from pathlib import Path

try:  # ``resource`` is a POSIX module and is absent on Windows.
    import resource
except ModuleNotFoundError:  # pragma: no cover - exercised by Windows import smoke tests
    resource = None

from brain_ssd.cache_policy import CognitiveCacheV0, LFUPolicy, LRFUPolicy, LRUPolicy, NoCachePolicy
from brain_ssd.cache_simulator import percentile
from brain_ssd.cache_trace import read_trace
from brain_ssd.residency import MappedRegion, controller_for, resident_vector
from brain_ssd.system_metrics import mapped_file_memory, process_io, process_memory

MIB = 1024**2
COGNITIVE_WEIGHTS = {"recency": .18, "frequency": .16, "topic": .20, "transition": .28,
                     "reload": .03, "provenance": .08, "hysteresis": .10, "age": .03}


def policy_for(name: str, budget_pages: int):
    if name == "kernel_only": return NoCachePolicy()
    if name == "lru": return LRUPolicy(budget_pages)
    if name == "lfu": return LFUPolicy(budget_pages)
    if name == "lrfu": return LRFUPolicy(budget_pages)
    if name == "cognitive_v0": return CognitiveCacheV0(budget_pages, COGNITIVE_WEIGHTS)
    raise ValueError(name)


def expand_trace(events, workload: str, universe_pages: int):
    """Deterministically expand physical cardinality without changing router output/order."""
    if not 1 <= universe_pages <= 1024:
        raise ValueError("the 1 GiB corpus supports 1..1024 logical pages")
    result = []
    for event in events:
        if workload == "stable_topic": bank = event.turn_id // 12
        elif workload in {"a_b_a", "long_gap_return"} and event.phase_label in {"A", "RETURN_A"}: bank = 0
        elif workload in {"a_b_a", "long_gap_return"}: bank = 1 + event.turn_id // 5
        elif workload == "random_topics": bank = (event.turn_id * 17 + event.logical_timestamp * 7)
        elif workload == "zipf_topic_popularity": bank = event.turn_id // 20
        else: bank = event.turn_id // 8
        page_id = (event.page_id + bank * 131) % universe_pages
        result.append(replace(event, page_id=page_id, logical_timestamp=len(result)))
    return result


def _snapshot_resident_pages(region: MappedRegion, page_size: int) -> set[int]:
    vector = resident_vector(region, 0, region.length)
    base_per_logical = page_size // os.sysconf("SC_PAGE_SIZE")
    return {index for index in range(region.length // page_size)
            if all(vector[index * base_per_logical:(index + 1) * base_per_logical])}


def _delta(before: dict, after: dict, key: str):
    left, right = before.get(key), after.get(key)
    return right - left if isinstance(left, int) and isinstance(right, int) else None


def run_physical_replay(manifest_path: Path, trace_path: Path, workload: str, universe_pages: int,
                        policy_name: str, budget_mib: int, controller_mode: str,
                        observability: bool = True, snapshot_turns: int = 20) -> dict:
    if resource is None:
        raise OSError("A reprodução física com contadores de falha requer POSIX.")
    manifest = json.loads(manifest_path.read_text())
    page_size = manifest["page_size_bytes"]
    data_path = manifest_path.parent / manifest["data_file"]
    _, original_events = read_trace(trace_path)
    events = expand_trace(original_events, workload, universe_pages)
    if hasattr(os, "posix_fadvise"):
        with data_path.open("rb") as cold_file:
            os.posix_fadvise(cold_file.fileno(), 0, 0, os.POSIX_FADV_DONTNEED)
    data_file = data_path.open("rb")
    mapping = mmap.mmap(data_file.fileno(), 0, access=mmap.ACCESS_READ)
    region = MappedRegion.borrow(mapping, data_file.fileno())
    try:
        initial_resident = _snapshot_resident_pages(region, page_size)
        cold_classification = "COLD" if not initial_resident else "BEST_EFFORT_COLD"
        policy = policy_for(policy_name, budget_mib)
        controller = controller_for(controller_mode, region, page_size)
        policy_hits = resident_hits = ghost_hits = false_hot = 0
        hot_resident = hot_nonresident = cold_resident = cold_nonresident = 0
        access_us: list[float] = []
        policy_us: list[float] = []
        physical_regret = {1: 0, 2: 0, 4: 0, 8: 0, 16: 0}
        effective_evictions = eviction_requests = 0
        evicted: dict[int, tuple[int, bool]] = {}
        budget_overshoot: list[int] = []
        resident_snapshots: list[dict] = []
        return_read_bytes = transition_read_bytes = 0
        return_faults = transition_faults = 0
        sink = 0
        io_before = process_io(); memory_before = process_memory(); usage_before = resource.getrusage(resource.RUSAGE_SELF)
        current_turn = -1
        for event in events:
            if event.turn_id != current_turn:
                policy.update_state(event.turn_id, event.cognitive_state)
                current_turn = event.turn_id
                if observability and current_turn % snapshot_turns == 0:
                    physical = _snapshot_resident_pages(region, page_size)
                    hot = set(policy.resident)
                    resident_snapshots.append({"turn": current_turn, "resident_pages": len(physical),
                                               "hot_pages": len(hot), "ghost_pages": len(physical - hot),
                                               "false_hot_pages": len(hot - physical)})
                    budget_overshoot.append(max(0, len(physical) * page_size - budget_mib * MIB))
            hot_before = event.page_id in policy.resident
            resident_before = controller.resident(event.page_id) if observability else False
            policy_hits += hot_before
            resident_hits += resident_before
            ghost_hits += resident_before and not hot_before
            false_hot += hot_before and not resident_before
            hot_resident += hot_before and resident_before
            hot_nonresident += hot_before and not resident_before
            cold_resident += (not hot_before) and resident_before
            cold_nonresident += (not hot_before) and (not resident_before)
            before_event_io = process_io().get("read_bytes") if observability and (event.phase_label == "RETURN_A" or event.topic_transition) else None
            before_event_faults = resource.getrusage(resource.RUSAGE_SELF).ru_majflt if before_event_io is not None else None
            started = time.perf_counter_ns()
            offset = event.page_id * page_size
            for position in range(offset, offset + page_size, 4096):
                sink = ((sink << 5) - sink) ^ mapping[position]
                sink &= 0xFFFFFFFFFFFFFFFF
            access_us.append((time.perf_counter_ns() - started) / 1000)
            policy_started = time.perf_counter_ns()
            decision = policy.observe_access(event)
            policy_us.append((time.perf_counter_ns() - policy_started) / 1000)
            controller.keep(event.page_id)
            for victim in decision.evicted_pages:
                was_resident = controller.resident(victim) if observability else False
                accepted = controller.evict(victim)
                eviction_requests += accepted
                after_resident = controller.resident(victim) if observability and accepted else was_resident
                effective_evictions += accepted and was_resident and not after_resident
                evicted[victim] = (event.turn_id, accepted and was_resident and not after_resident)
            prior = evicted.get(event.page_id)
            if prior and prior[1]:
                distance = event.turn_id - prior[0]
                for window in physical_regret:
                    physical_regret[window] += distance <= window and not resident_before
            if before_event_io is not None:
                after_event_io = process_io().get("read_bytes")
                read_delta = max(0, after_event_io - before_event_io) if after_event_io is not None else 0
                fault_delta = resource.getrusage(resource.RUSAGE_SELF).ru_majflt - before_event_faults
                if event.phase_label == "RETURN_A": return_read_bytes += read_delta; return_faults += fault_delta
                if event.topic_transition: transition_read_bytes += read_delta; transition_faults += fault_delta
        io_after = process_io(); usage_after = resource.getrusage(resource.RUSAGE_SELF)
        final_physical = _snapshot_resident_pages(region, page_size)
        final_hot = set(policy.resident)
        memory_after = process_memory(); mapped_after = mapped_file_memory(data_path)
        accesses = len(events)
        logical_miss_bytes = (accesses - policy_hits) * page_size
        physical_read_bytes = _delta(io_before, io_after, "read_bytes")
        intervention = controller.stats()
        return {
            "workload": workload, "trace": str(trace_path), "universe_pages": universe_pages,
            "policy": policy_name, "controller": controller_mode, "mode": "observability" if observability else "performance",
            "budget_mib": budget_mib, "events": accesses, "cold_classification": cold_classification,
            "initial_resident_pages": len(initial_resident), "policy_hit_rate": policy_hits / accesses if accesses else 0,
            "resident_hit_rate": resident_hits / accesses if accesses and observability else None,
            "ghost_hit_count": ghost_hits if observability else None, "false_hot_count": false_hot if observability else None,
            "residency_matrix": {"hot_resident": hot_resident, "hot_nonresident": hot_nonresident,
                                  "cold_resident": cold_resident, "cold_nonresident": cold_nonresident},
            "logical_miss_bytes": logical_miss_bytes, "physical_read_bytes": physical_read_bytes,
            "physical_read_amplification": physical_read_bytes / logical_miss_bytes if physical_read_bytes is not None and logical_miss_bytes else None,
            "major_faults": usage_after.ru_majflt - usage_before.ru_majflt,
            "minor_faults": usage_after.ru_minflt - usage_before.ru_minflt,
            "access_latency_us": {"p50": percentile(access_us, .5), "p95": percentile(access_us, .95), "p99": percentile(access_us, .99)},
            "policy_latency_us": {"p50": percentile(policy_us, .5), "p95": percentile(policy_us, .95), "p99": percentile(policy_us, .99)},
            "intervention": intervention, "eviction_requests": eviction_requests,
            "effective_immediate_evictions": effective_evictions,
            "eviction_effectiveness_immediate": effective_evictions / eviction_requests if eviction_requests and observability else None,
            "physical_eviction_regret": {str(key): value for key, value in physical_regret.items()},
            "return_physical_read_bytes": return_read_bytes, "return_major_faults": return_faults,
            "transition_physical_read_bytes": transition_read_bytes, "transition_major_faults": transition_faults,
            "final_resident_pages": len(final_physical), "final_hot_pages": len(final_hot),
            "final_ghost_pages": len(final_physical - final_hot), "final_false_hot_pages": len(final_hot - final_physical),
            "budget_overshoot_bytes": {"median": statistics.median(budget_overshoot) if budget_overshoot else None,
                                        "p95": percentile(budget_overshoot, .95) if budget_overshoot else None,
                                        "max": max(budget_overshoot) if budget_overshoot else None},
            "resident_snapshots": resident_snapshots,
            "process_memory_before": memory_before, "process_memory_after": memory_after,
            "anonymous_rss_growth_bytes": _delta(memory_before, memory_after, "anonymous_bytes"),
            "mapped_file_memory_after": mapped_after, "metadata_bytes": policy.stats()["metadata_bytes_estimated"],
            "sink": sink,
        }
    finally:
        region.release(); mapping.close(); data_file.close()
