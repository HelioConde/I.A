#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import resource
import statistics
import sys
import time
import tracemalloc
from array import array
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brain_ssd.gating import BasalGate, CognitiveState
from brain_ssd.router import BenchmarkRouter, LexicalRouter, SemanticIndex, normalize
from brain_ssd.semantic import TAXONOMY, generate_query_dataset, generate_semantic_manifest
from brain_ssd.storage import MMapStorageBackend, touch_view
from brain_ssd.system_metrics import process_io, process_memory

MIB = 1024**2
SEED = 20260807


def percentile(values: list[float], percentile_value: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile_value
    low, high = int(position), min(int(position) + 1, len(ordered) - 1)
    fraction = position - low
    return ordered[low] * (1 - fraction) + ordered[high] * fraction


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    os.replace(temporary, path)


def score(query: dict, activated: tuple[int, ...], page_count: int, domain_pages: int) -> dict:
    active = set(activated)
    required = set(query["required_pages"])
    relevant = required | set(query["optional_pages"])
    recall = len(active & required) / len(required) if required else 1.0
    precision = len(active & relevant) / len(active) if active else (1.0 if not relevant else 0.0)
    active_bytes = len(active) * MIB
    return {
        "required_count": len(required), "relevant_count": len(relevant),
        "routing_recall": recall, "routing_precision": precision,
        "required_page_miss_rate": 1.0 - recall,
        "activated_pages": len(active), "active_brain_size_bytes": active_bytes,
        "circuit_activation_rate": len(active) / page_count,
        "avoided_logical_bytes_vs_all_brain": (page_count - len(active)) * MIB,
        "avoided_logical_bytes_vs_all_domain": max(0, domain_pages - len(active)) * MIB,
    }


def measured_route(router, query: str, state, repeats: int = 31):
    wall, cpu = [], []
    result = None
    for _ in range(repeats):
        cpu_start = time.process_time_ns()
        start = time.perf_counter_ns()
        result = router.route(query, state)
        wall.append((time.perf_counter_ns() - start) / 1e6)
        cpu.append((time.process_time_ns() - cpu_start) / 1e6)
    assert result is not None
    return result, wall, cpu


def canonical(manifest: dict, dataset: dict) -> dict:
    index = SemanticIndex(manifest)
    lexical = LexicalRouter(index)
    routers = {
        "oracle": BenchmarkRouter("oracle", index, dataset["queries"]),
        "all_domain": BenchmarkRouter("all_domain", index, dataset["queries"]),
        "random_k": BenchmarkRouter("random_k", index, dataset["queries"]),
        "lexical": lexical,
    }
    gate = BasalGate(index)
    records = []
    for router_name, router in routers.items():
        for budget in (4, 8, 16, 32, 64):
            for query in dataset["queries"]:
                routed, wall, cpu = measured_route(router, query["query"], None)
                gate_start = time.perf_counter_ns()
                plan = gate.apply(routed, budget)
                gate_ms = (time.perf_counter_ns() - gate_start) / 1e6
                domain_count = len(index.domain_pages.get(query["expected_domain"], ()))
                metrics = score(query, plan.activate_pages, index.page_count, domain_count)
                records.append({
                    "router": router_name, "budget_mib": budget,
                    "query_id": query["query_id"], "query_type": query["category"],
                    "expected_domain": query["expected_domain"],
                    "selected_domain": routed.domains[0][0] if routed.domains else None,
                    "router_latency_ms_p50": percentile(wall, .5),
                    "router_latency_ms_p95": percentile(wall, .95),
                    "router_latency_ms_p99": percentile(wall, .99),
                    "router_cpu_ms_p50": percentile(cpu, .5), "gate_latency_ms": gate_ms,
                    "candidate_pages": len(routed.candidate_pages),
                    "inhibited_pages": len(plan.inhibit_pages),
                    "rejected_candidates": len(plan.rejected_candidates),
                    **metrics,
                })
    all_brain = {
        "activated_pages": index.page_count, "active_brain_size_bytes": index.page_count * MIB,
        "circuit_activation_rate": 1.0, "avoided_logical_bytes_vs_all_brain": 0,
    }
    return {
        "schema_version": 1, "kind": "phase3_canonical", "seed": SEED,
        "baseline": {"logical_page_mib": 1, "storage_extent_mib": 4, "access": "logical-only", "full_extent": False, "custom_brain_cache": 0, "linux_page_cache": True},
        "brain_pages": index.page_count, "all_brain_baseline": all_brain,
        "index": {"serialized_bytes": index.serialized_size_bytes, "estimated_resident_bytes": index.estimated_resident_bytes(), "terms": len(index.inverted)},
        "records": records,
    }


def state_experiment(manifest: dict, dataset: dict) -> dict:
    index, records = SemanticIndex(manifest), []
    sequence = [q for q in dataset["queries"] if q["sequence_id"] == "switch"]
    for mode in ("stateless", "state", "hysteresis"):
        for budget in (4, 8, 16):
            router, gate, state = LexicalRouter(index), BasalGate(index), CognitiveState()
            previous: set[int] = set()
            for query in sequence:
                if mode != "stateless":
                    state.decay()
                routed, wall, cpu = measured_route(router, query["query"], state if mode != "stateless" else None)
                plan = gate.apply(routed, budget, state if mode == "hysteresis" else None)
                active = set(plan.activate_pages)
                metrics = score(query, plan.activate_pages, index.page_count, len(index.domain_pages[query["expected_domain"]]))
                records.append({
                    "mode": mode, "budget_mib": budget, "turn": query["turn_index"],
                    "query_id": query["query_id"], "expected_domain": query["expected_domain"],
                    "selected_domain": routed.domains[0][0] if routed.domains else None,
                    "activation_churn_pages": len(active.symmetric_difference(previous)),
                    "entered_pages": len(active - previous), "exited_pages": len(previous - active),
                    "kept_by_hysteresis": len(plan.keep_hot_pages),
                    "router_latency_ms_p50": percentile(wall, .5), **metrics,
                })
                if mode != "stateless":
                    state.update(routed, plan.activate_pages)
                previous = active
    return {"schema_version": 1, "kind": "phase3_topic_switch", "sequence": "A A A A -> B B B -> A A", "records": records}


def cardinality_experiment() -> dict:
    terms = sorted({token for domains in TAXONOMY.values() for topic, words in domains.items() for token in normalize(" ".join([topic, *words]))})
    records = []
    for count in (1_000, 10_000, 100_000, 1_000_000):
        tracemalloc.start()
        start = time.perf_counter()
        postings = {term: array("I") for term in terms}
        for page_id in range(count):
            for offset in range(5):
                postings[terms[(page_id * 5 + offset) % len(terms)]].append(page_id)
        build_ms = (time.perf_counter() - start) * 1000
        _, peak = tracemalloc.get_traced_memory()
        query_times = []
        for iteration in range(101):
            selected = terms[(iteration * 17) % len(terms)]
            tick = time.perf_counter_ns()
            _ = postings[selected][:64]
            query_times.append((time.perf_counter_ns() - tick) / 1e6)
        payload_bytes = sum(len(values) * values.itemsize for values in postings.values())
        tracemalloc.stop()
        records.append({
            "page_count": count, "build_ms": build_ms, "posting_payload_bytes": payload_bytes,
            "tracemalloc_peak_bytes": peak, "bytes_per_page_payload": payload_bytes / count,
            "lookup_latency_ms_p50": percentile(query_times, .5), "lookup_latency_ms_p99": percentile(query_times, .99),
            "method": "compact uint32 postings; metadata bodies not materialized",
        })
        del postings
    return {"schema_version": 1, "kind": "phase3_cardinality", "term_count": len(terms), "records": records}


def integrated(manifest: dict, dataset: dict, physical_manifest: Path) -> dict:
    index, gate = SemanticIndex(manifest), BasalGate(SemanticIndex(manifest))
    routers = {"oracle": BenchmarkRouter("oracle", index, dataset["queries"]), "lexical": LexicalRouter(index)}
    selected_queries = [q for q in dataset["queries"] if q["category"] in {"easy_single_topic", "multi_topic", "ambiguous", "unknown"}]
    records = []
    for router_name, router in routers.items():
        for budget in (4, 8, 16):
            for query in selected_queries:
                backend = MMapStorageBackend(physical_manifest)
                cold = backend.advise_drop_cache()
                io_before, memory_before = process_io(), process_memory()
                cpu_before, started = time.process_time_ns(), time.perf_counter_ns()
                routed = router.route(query["query"], None)
                plan = gate.apply(routed, budget)
                sink = 0
                with backend:
                    for page_id in plan.activate_pages:
                        page = backend.get_page(page_id, validate=False)
                        sink ^= touch_view(page.data)
                        backend.release_page(page)
                elapsed = (time.perf_counter_ns() - started) / 1e6
                cpu_ms = (time.process_time_ns() - cpu_before) / 1e6
                io_after, memory_after = process_io(), process_memory()
                physical = max(0, (io_after.get("read_bytes") or 0) - (io_before.get("read_bytes") or 0))
                logical = len(plan.activate_pages) * MIB
                records.append({
                    "router": router_name, "budget_mib": budget, "query_id": query["query_id"],
                    "best_effort_cold": cold, "latency_ms": elapsed, "cpu_ms": cpu_ms,
                    "activated_pages": len(plan.activate_pages), "logical_bytes": logical,
                    "physical_read_bytes": physical,
                    "physical_read_amplification": physical / logical if logical else 0.0,
                    "rss_delta_bytes": (memory_after.get("rss_bytes") or 0) - (memory_before.get("rss_bytes") or 0),
                    "pss_delta_bytes": (memory_after.get("pss_bytes") or 0) - (memory_before.get("pss_bytes") or 0),
                    "sink": sink,
                })
    return {"schema_version": 1, "kind": "phase3_integrated_route_gate_storage", "physical_manifest": str(physical_manifest), "records": records}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results/phase3")
    parser.add_argument("--semantic-manifest", type=Path, default=ROOT / "brain_data/synthetic-1gib-seed-20260807/semantic-manifest.json")
    parser.add_argument("--queries", type=Path, default=ROOT / "benchmarks/data/phase3-queries.json")
    parser.add_argument("--physical-manifest", type=Path, default=ROOT / "brain_data/synthetic-1gib-seed-20260807/manifest-1048576.json")
    args = parser.parse_args()
    manifest = generate_semantic_manifest(args.semantic_manifest, 1024, SEED)
    dataset = generate_query_dataset(args.queries, manifest, SEED)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    atomic_json(args.output_dir / "canonical.json", canonical(manifest, dataset))
    atomic_json(args.output_dir / "topic-switch.json", state_experiment(manifest, dataset))
    atomic_json(args.output_dir / "cardinality.json", cardinality_experiment())
    if args.physical_manifest.exists():
        atomic_json(args.output_dir / "integrated-storage.json", integrated(manifest, dataset, args.physical_manifest))
    print(args.output_dir)


if __name__ == "__main__":
    main()
