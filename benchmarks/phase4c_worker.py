#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import mmap
import os
import resource
import time
from collections import defaultdict
from pathlib import Path

from brain_ssd.cache_simulator import percentile
from brain_ssd.cache_trace import read_trace
from brain_ssd.cold_hint import CognitiveColdHintResidencyController, LRUColdHintResidencyController
from brain_ssd.physical_replay import expand_trace, policy_for
from brain_ssd.residency import AdvisoryResidencyController, KernelOnlyResidencyController, MappedRegion
from brain_ssd.resource_pressure import ResourcePressureMonitor, detect_environment, numeric_delta
from brain_ssd.system_metrics import mapped_file_memory, process_io, process_memory


MIB = 1024**2


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", type=Path, required=True); parser.add_argument("--workload", required=True)
    parser.add_argument("--strategy", choices=("kernel_only", "cognitive_shadow", "lru_cold", "cognitive_cold", "cognitive_pressure_aware", "pageout_negative"), required=True)
    parser.add_argument("--budget-mib", type=int, default=64); parser.add_argument("--universe-pages", type=int, default=1024)
    args = parser.parse_args()
    manifest_path = Path("/brain/brain_data/synthetic-1gib-seed-20260807/manifest-1048576.json")
    manifest = json.loads(manifest_path.read_text()); page_size = manifest["page_size_bytes"]
    data_path = manifest_path.parent / manifest["data_file"]
    _, original = read_trace(args.trace); events = expand_trace(original, args.workload, args.universe_pages)
    if hasattr(os, "posix_fadvise"):
        with data_path.open("rb") as cold: os.posix_fadvise(cold.fileno(), 0, 0, os.POSIX_FADV_DONTNEED)
    data_file = data_path.open("rb"); mapping = mmap.mmap(data_file.fileno(), 0, access=mmap.ACCESS_READ)
    region = MappedRegion.borrow(mapping, data_file.fileno())
    monitor = ResourcePressureMonitor(); before_pressure = monitor.snapshot()
    before_memory = process_memory(); before_io = process_io(); before_usage = resource.getrusage(resource.RUSAGE_SELF)
    try:
        if args.strategy == "kernel_only": policy = policy_for("kernel_only", 0)
        elif args.strategy in {"lru_cold"}: policy = policy_for("lru", args.budget_mib)
        else: policy = policy_for("cognitive_v0", args.budget_mib)
        if args.strategy == "lru_cold": controller = LRUColdHintResidencyController(region, page_size)
        elif args.strategy in {"cognitive_cold", "cognitive_pressure_aware"}: controller = CognitiveColdHintResidencyController(region, page_size)
        elif args.strategy == "pageout_negative": controller = AdvisoryResidencyController(region, page_size, "madv_pageout")
        else: controller = KernelOnlyResidencyController(region, page_size)
        seen = set(); hinted_turn = {}; cold_regret = {window: 0 for window in (1, 2, 4, 8, 16, 32)}
        logical_refaults = hot_reclaims = hot_refaults = opportunistic_hits = 0
        policy_hits = resident_hits = cold_hints = 0; cold_hint_bytes = 0
        access_us = []; hint_us = []; pressure_samples = [before_pressure]
        return_read_bytes = transition_read_bytes = 0; sink = 0; current_turn = -1
        for event in events:
            if event.turn_id != current_turn:
                policy.update_state(event.turn_id, event.cognitive_state); current_turn = event.turn_id
                if current_turn % 25 == 0: pressure_samples.append(monitor.snapshot())
            hot = event.page_id in policy.resident; resident = controller.resident(event.page_id)
            policy_hits += hot; resident_hits += resident; opportunistic_hits += resident and not hot
            if event.page_id in seen and not resident:
                logical_refaults += 1
                if hot: hot_refaults += 1
            if hot and not resident: hot_reclaims += 1
            if event.page_id in hinted_turn and not resident:
                distance = event.turn_id - hinted_turn[event.page_id]
                for window in cold_regret: cold_regret[window] += distance <= window
            phase_io = process_io().get("read_bytes") if event.phase_label == "RETURN_A" or event.topic_transition else None
            started = time.perf_counter_ns(); offset = event.page_id * page_size
            for position in range(offset, offset + page_size, 4096):
                sink = ((sink << 5) - sink) ^ mapping[position]; sink &= 0xFFFFFFFFFFFFFFFF
            access_us.append((time.perf_counter_ns() - started) / 1000); seen.add(event.page_id)
            decision = policy.observe_access(event); controller.keep(event.page_id)
            allow_hint = args.strategy != "cognitive_pressure_aware" or pressure_samples[-1]["pressure_state"] in {"MODERATE", "HIGH", "CRITICAL"}
            if allow_hint:
                for victim in decision.evicted_pages:
                    hint_started = time.perf_counter_ns(); accepted = controller.evict(victim)
                    hint_us.append((time.perf_counter_ns() - hint_started) / 1000)
                    if accepted: cold_hints += 1; cold_hint_bytes += page_size; hinted_turn[victim] = event.turn_id
            if phase_io is not None:
                delta = max(0, process_io().get("read_bytes") - phase_io)
                if event.phase_label == "RETURN_A": return_read_bytes += delta
                if event.topic_transition: transition_read_bytes += delta
        after_pressure = monitor.snapshot(); pressure_samples.append(after_pressure)
        after_memory = process_memory(); after_io = process_io(); after_usage = resource.getrusage(resource.RUSAGE_SELF)
        stat_delta = numeric_delta(before_pressure["stat"], after_pressure["stat"])
        events_delta = numeric_delta(before_pressure["events"], after_pressure["events"])
        physical_read = after_io["read_bytes"] - before_io["read_bytes"]
        output = {
            "environment_type": detect_environment(), "hard_limit_valid": before_pressure["memory_max"] is not None,
            "memory_max": before_pressure["memory_max"], "memory_swap_max": before_pressure["memory_swap_max"],
            "workload": args.workload, "strategy": args.strategy, "budget_mib": args.budget_mib,
            "events": len(events), "unique_pages": len(seen), "physical_read_bytes": physical_read,
            "major_faults": after_usage.ru_majflt - before_usage.ru_majflt,
            "minor_faults": after_usage.ru_minflt - before_usage.ru_minflt,
            "policy_hit_rate": policy_hits / len(events), "resident_hit_rate": resident_hits / len(events),
            "opportunistic_hit_count": opportunistic_hits, "logical_refault_count": logical_refaults,
            "logical_refault_bytes": logical_refaults * page_size, "logical_refault_rate": logical_refaults / len(events),
            "hot_reclaim_count": hot_reclaims, "hot_refault_count": hot_refaults,
            "cold_hint_count": cold_hints, "cold_hint_bytes": cold_hint_bytes,
            "cold_hint_calls_per_1000": cold_hints * 1000 / len(events),
            "cold_hint_us": {"p50": percentile(hint_us, .5), "p95": percentile(hint_us, .95), "p99": percentile(hint_us, .99)},
            "cognitive_cold_regret": {str(key): value for key, value in cold_regret.items()},
            "access_latency_us": {"p50": percentile(access_us, .5), "p95": percentile(access_us, .95), "p99": percentile(access_us, .99)},
            "return_read_bytes": return_read_bytes, "transition_read_bytes": transition_read_bytes,
            "cgroup_stat_delta": stat_delta, "cgroup_events_delta": events_delta,
            "workingset_refault_file": stat_delta.get("workingset_refault_file"),
            "workingset_restore_file": stat_delta.get("workingset_restore_file"),
            "pgscan": stat_delta.get("pgscan"), "pgsteal": stat_delta.get("pgsteal"),
            "pressure_states": {state: sum(sample["pressure_state"] == state for sample in pressure_samples) for state in ("LOW", "MODERATE", "HIGH", "CRITICAL")},
            "pressure_samples": pressure_samples,
            "memory_peak": after_pressure["memory_peak"], "psi_final": after_pressure["psi"],
            "anonymous_rss_growth": after_memory["anonymous_bytes"] - before_memory["anonymous_bytes"],
            "mapped_file_memory": mapped_file_memory(data_path), "controller": controller.stats(), "sink": sink,
        }
        print(json.dumps(output, sort_keys=True))
    finally:
        region.release(); mapping.close(); data_file.close()


if __name__ == "__main__": main()
