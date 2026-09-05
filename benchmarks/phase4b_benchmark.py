#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results/phase4b"
MANIFEST = ROOT / "brain_data/synthetic-1gib-seed-20260807/manifest-1048576.json"
WORKLOADS = ("realistic_mix", "long_gap_return", "a_b_a", "random_topics", "zipf_topic_popularity", "stable_topic")
POLICIES = ("kernel_only", "lru", "lfu", "lrfu", "cognitive_v0")
BUDGETS = (8, 16, 32, 64)


def worker(config: dict) -> dict:
    trace = ROOT / f"results/phase4a/traces/holdout/{config['workload']}-100.jsonl.gz"
    command = [sys.executable, str(ROOT / "benchmarks/phase4b_worker.py"), "--manifest", str(MANIFEST),
               "--trace", str(trace), "--workload", config["workload"], "--universe-pages", str(config["universe_pages"]),
               "--policy", config["policy"], "--budget-mib", str(config["budget_mib"]), "--controller", config["controller"]]
    if config.get("performance"): command.append("--performance")
    environment = dict(os.environ); environment["PYTHONPATH"] = str(ROOT / "src")
    completed = subprocess.run(command, check=True, capture_output=True, text=True, env=environment)
    result = json.loads(completed.stdout); result.update({"repetition": config["repetition"], "order_index": config["order_index"]})
    return result


def aggregate(runs: list[dict]) -> list[dict]:
    groups = {}
    for run in runs:
        key = (run["track"], run["mode"], run["workload"], run["universe_pages"], run["policy"], run["controller"], run["budget_mib"])
        groups.setdefault(key, []).append(run)
    output = []
    for key, items in sorted(groups.items()):
        def median(path):
            values = []
            for item in items:
                value = item
                for part in path.split("."): value = value.get(part) if isinstance(value, dict) else None
                if isinstance(value, (int, float)): values.append(value)
            return statistics.median(values) if values else None
        output.append({"track": key[0], "mode": key[1], "workload": key[2], "universe_pages": key[3], "policy": key[4], "controller": key[5], "budget_mib": key[6],
                       "repetitions": len(items), "policy_hit_rate_median": median("policy_hit_rate"),
                       "resident_hit_rate_median": median("resident_hit_rate"), "physical_read_bytes_median": median("physical_read_bytes"),
                       "logical_miss_bytes_median": median("logical_miss_bytes"), "major_faults_median": median("major_faults"),
                       "minor_faults_median": median("minor_faults"), "access_p50_us_median": median("access_latency_us.p50"),
                       "access_p95_us_median": median("access_latency_us.p95"), "ghost_hits_median": median("ghost_hit_count"),
                       "false_hot_median": median("false_hot_count"), "eviction_effectiveness_median": median("eviction_effectiveness_immediate"),
                       "anonymous_growth_median": median("anonymous_rss_growth_bytes"),
                       "return_read_bytes_median": median("return_physical_read_bytes"),
                       "transition_read_bytes_median": median("transition_physical_read_bytes"),
                       "intervention_p95_us_median": median("intervention.intervention_us.p95"),
                       "budget_overshoot_p95_median": median("budget_overshoot_bytes.p95")})
    return output


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--repetitions", type=int, default=2); args = parser.parse_args()
    RESULTS.mkdir(parents=True, exist_ok=True)
    # Screen each advisory API on the two most diagnostic workloads before selecting the main guided controller.
    configs = []
    for controller in ("kernel_only", "madv_cold", "madv_dontneed", "fadv_dontneed", "madv_pageout"):
        for workload in ("realistic_mix", "long_gap_return"):
            for policy in ("lru", "cognitive_v0"):
                configs.append({"track": "controller_screen", "workload": workload, "universe_pages": 1024,
                                "policy": policy, "budget_mib": 64, "controller": controller, "repetition": 0})
    # Main physical track: same 1,024-page universe, policies/budgets, with shadow and safest active demotion.
    for repetition in range(args.repetitions):
        for workload in WORKLOADS:
            for budget in BUDGETS:
                for policy in POLICIES:
                    controller = "kernel_only" if policy == "kernel_only" else "madv_pageout"
                    configs.append({"track": "main", "workload": workload, "universe_pages": 1024,
                                    "policy": policy, "budget_mib": budget, "controller": controller, "repetition": repetition})
        # Shadow comparison at the Phase 4A candidate budget.
        for workload in WORKLOADS:
            for policy in POLICIES[1:]:
                configs.append({"track": "shadow", "workload": workload, "universe_pages": 1024,
                                "policy": policy, "budget_mib": 64, "controller": "kernel_only", "repetition": repetition})
    # Cardinality curve for physical working sets.
    for universe in (128, 256, 512, 1024):
        for policy in ("kernel_only", "lru", "cognitive_v0"):
            configs.append({"track": "cardinality", "workload": "realistic_mix", "universe_pages": universe,
                            "policy": policy, "budget_mib": 64,
                            "controller": "kernel_only" if policy == "kernel_only" else "madv_pageout", "repetition": 0})
    # Minimal-instrumentation latency track; mincore is not called per access.
    for repetition in range(args.repetitions):
        for workload in WORKLOADS:
            for policy in ("kernel_only", "lru", "cognitive_v0"):
                configs.append({"track": "performance", "workload": workload, "universe_pages": 1024,
                                "policy": policy, "budget_mib": 64,
                                "controller": "kernel_only" if policy == "kernel_only" else "madv_pageout",
                                "repetition": repetition, "performance": True})
    rng = random.Random(20260807); rng.shuffle(configs)
    for index, config in enumerate(configs): config["order_index"] = index
    runs = []
    for index, config in enumerate(configs, 1):
        result = worker(config); result["track"] = config["track"]; runs.append(result)
        if index % 20 == 0: print(f"completed {index}/{len(configs)}", flush=True)
    (RESULTS / "runs.json").write_text(json.dumps(runs, indent=2, sort_keys=True) + "\n")
    summary = aggregate(runs)
    (RESULTS / "aggregate.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    (RESULTS / "run-order.json").write_text(json.dumps({"seed": 20260807, "configs": configs}, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"runs": len(runs), "groups": len(summary)}, sort_keys=True))


if __name__ == "__main__": main()
