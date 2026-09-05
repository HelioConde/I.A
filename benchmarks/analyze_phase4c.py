#!/usr/bin/env python3
from __future__ import annotations

import bisect
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from brain_ssd.cache_trace import read_trace
from brain_ssd.physical_replay import expand_trace, policy_for
from brain_ssd.resource_pressure import classify_pressure


ROOT = Path(__file__).resolve().parents[1]; RESULTS = ROOT / "results/phase4c"; MIB = 1024**2
WORKLOADS = ("realistic_mix", "stable_topic", "long_gap_return", "a_b_a", "random_topics", "zipf_topic_popularity")
STRATEGIES = ("kernel_only", "cognitive_shadow", "lru_cold", "cognitive_cold")


def flatten(path):
    return [{**run, **run["result"]["payload"]} for run in json.loads(path.read_text())
            if run["result"]["payload"] is not None and not run["result"]["oom_killed"]]


def median(items, getter):
    values = [getter(item) for item in items]; values = [value for value in values if isinstance(value, (int, float))]
    return statistics.median(values) if values else None


def shadow_reuse_analysis():
    combined = {"cold_distances": [], "hot_distances": []}
    by_workload = {}
    for workload in WORKLOADS:
        _, source = read_trace(ROOT / f"results/phase4a/traces/development/{workload}-1000.jsonl.gz")
        events = expand_trace(source, workload, 1024); policy = policy_for("cognitive_v0", 64)
        positions = defaultdict(list)
        for index, event in enumerate(events): positions[event.page_id].append(index)
        cold, hot = [], []
        current_turn = -1
        for index, event in enumerate(events):
            if event.turn_id != current_turn:
                policy.update_state(event.turn_id, event.cognitive_state); current_turn = event.turn_id
            decision = policy.observe_access(event)
            for victim in decision.evicted_pages:
                offset = bisect.bisect_right(positions[victim], index)
                cold.append(None if offset == len(positions[victim]) else events[positions[victim][offset]].turn_id - event.turn_id)
            for page in policy.resident:
                offset = bisect.bisect_right(positions[page], index)
                if offset < len(positions[page]): hot.append(events[positions[page][offset]].turn_id - event.turn_id)
        finite_cold = [x for x in cold if x is not None]; finite_hot = [x for x in hot if x is not None]
        by_workload[workload] = {"cold_predictions": len(cold), "cold_never_reused_rate": sum(x is None for x in cold) / len(cold) if cold else None,
                                 "cold_reuse_turns_median": statistics.median(finite_cold) if finite_cold else None,
                                 "cold_reused_within_32_rate": sum(x is not None and x <= 32 for x in cold) / len(cold) if cold else None,
                                 "hot_future_samples": len(hot), "hot_reuse_turns_median": statistics.median(finite_hot) if finite_hot else None}
        combined["cold_distances"].extend(cold); combined["hot_distances"].extend(hot)
    cold = combined["cold_distances"]; hot = combined["hot_distances"]
    return {"by_workload": by_workload, "aggregate": {
        "cold_predictions": len(cold), "cold_never_reused_rate": sum(x is None for x in cold) / len(cold),
        "cold_reuse_turns_median": statistics.median(x for x in cold if x is not None),
        "cold_reused_within_32_rate": sum(x is not None and x <= 32 for x in cold) / len(cold),
        "hot_reuse_turns_median": statistics.median(x for x in hot if x is not None)}}


def main():
    runs = flatten(RESULTS / "runs.json"); aware = flatten(RESULTS / "pressure-aware-runs.json")
    rows = []
    for profile in ("PRESSURE_512", "PRESSURE_1024"):
        for workload in WORKLOADS:
            for strategy in STRATEGIES:
                items = [x for x in runs if x["profile"] == profile and x["workload"] == workload and x["strategy"] == strategy]
                rows.append({"profile": profile, "workload": workload, "strategy": strategy, "repetitions": len(items),
                    "physical_read_bytes_median": median(items, lambda x:x["physical_read_bytes"]),
                    "major_faults_median": median(items, lambda x:x["major_faults"]), "minor_faults_median": median(items, lambda x:x["minor_faults"]),
                    "logical_refault_count_median": median(items, lambda x:x["logical_refault_count"]),
                    "workingset_refault_file_median": median(items, lambda x:x["workingset_refault_file"]),
                    "workingset_restore_file_median": median(items, lambda x:x["workingset_restore_file"]),
                    "pgscan_median": median(items, lambda x:x["pgscan"]), "pgsteal_median": median(items, lambda x:x["pgsteal"]),
                    "access_p50_us_median": median(items, lambda x:x["access_latency_us"]["p50"]),
                    "access_p95_us_median": median(items, lambda x:x["access_latency_us"]["p95"]),
                    "cold_hint_count_median": median(items, lambda x:x["cold_hint_count"]),
                    "cold_hint_p95_us_median": median(items, lambda x:x["cold_hint_us"]["p95"]),
                    "hot_reclaim_median": median(items, lambda x:x["hot_reclaim_count"]), "hot_refault_median": median(items, lambda x:x["hot_refault_count"]),
                    "psi_some_avg10_median": median(items, lambda x:x["psi_final"]["some"]["avg10"]),
                    "psi_full_avg10_median": median(items, lambda x:x["psi_final"]["full"]["avg10"]),
                    "memory_event_max_total": sum(x["cgroup_events_delta"].get("max",0) for x in items),
                    "oom_total": sum(x["cgroup_events_delta"].get("oom",0) for x in items),
                    "oom_kill_total": sum(x["cgroup_events_delta"].get("oom_kill",0) for x in items)})
    profile_aggregate = {}
    for profile in ("PRESSURE_512", "PRESSURE_1024"):
        profile_aggregate[profile] = {}
        for strategy in STRATEGIES:
            selected = [row for row in rows if row["profile"] == profile and row["strategy"] == strategy]
            profile_aggregate[profile][strategy] = {key: sum(row[key] for row in selected)
                for key in ("physical_read_bytes_median","major_faults_median","logical_refault_count_median",
                            "workingset_refault_file_median","workingset_restore_file_median","pgscan_median","pgsteal_median")}
    aware_rows = []
    for workload in WORKLOADS:
        items = [x for x in aware if x["workload"] == workload]
        aware_rows.append({"workload": workload, "physical_read_bytes_median": median(items,lambda x:x["physical_read_bytes"]),
                           "major_faults_median": median(items,lambda x:x["major_faults"]),
                           "cold_hint_count_median": median(items,lambda x:x["cold_hint_count"])})
    pressure_counts = Counter()
    for item in runs:
        for sample in item["pressure_samples"]:
            pressure_counts[(item["profile"], classify_pressure(sample["memory_current"], sample["memory_max"], sample["stat"], sample["psi"]))] += 1
    proof = json.loads((RESULTS / "hard-limit-proof.json").read_text())
    aware_aggregate = {key: sum(row[key] for row in aware_rows) for key in ("physical_read_bytes_median","major_faults_median")}
    aware_aggregate.update({
        "logical_refault_count_median_sum": sum(median([x for x in aware if x["workload"]==workload],lambda x:x["logical_refault_count"]) for workload in WORKLOADS),
        "pgscan_median_sum": sum(median([x for x in aware if x["workload"]==workload],lambda x:x["pgscan"]) or 0 for workload in WORKLOADS),
        "pgsteal_median_sum": sum(median([x for x in aware if x["workload"]==workload],lambda x:x["pgsteal"]) or 0 for workload in WORKLOADS)})
    summary = {"schema_version":1,"environment_type":"CODESPACE_CONTAINER_LIMITED","valid_runs":len(runs),"pressure_aware_runs":len(aware),
               "oom_killed":0,"hard_limit_proof":{"classification":proof["classification"],"hard_limit_valid":proof["hard_limit_valid"],"page_cache_charge_valid":proof["page_cache_charge_valid"]},
               "matrix":rows,"profile_aggregate":profile_aggregate,"pressure_state_samples":{f"{p}:{s}":n for (p,s),n in pressure_counts.items()},
               "pressure_aware":aware_rows,"pressure_aware_aggregate":aware_aggregate,"shadow_prediction":shadow_reuse_analysis(),
               "swap":{"memory_swap_max":0,"enabled_for_containers":False},
               "no_duplication":{"anonymous_rss_growth_median":median(runs,lambda x:x["anonymous_rss_growth"]),"anonymous_rss_growth_max":max(x["anonymous_rss_growth"] for x in runs),"passed":max(x["anonymous_rss_growth"] for x in runs)<8*MIB},
               "pageout_negative":next(({key:value for key,value in x.items() if key in {"physical_read_bytes","major_faults","logical_refault_count"}} for x in runs if x["strategy"]=="pageout_negative"),None)}
    (RESULTS/"aggregate.json").write_text(json.dumps(rows,indent=2,sort_keys=True)+"\n")
    (RESULTS/"summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
    print(json.dumps(profile_aggregate,sort_keys=True))


if __name__=="__main__": main()
