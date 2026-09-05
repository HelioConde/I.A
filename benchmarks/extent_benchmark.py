#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brain_ssd.storage import MMapStorageBackend, touch_view
from brain_ssd.system_metrics import MetricSampler, mapped_file_memory, numeric_delta, process_faults_cpu, process_io, snapshot
from brain_ssd.workloads import Workload, access_sequence


def percentile(values: list[float], fraction: float) -> float:
    values = sorted(values)
    position = (len(values) - 1) * fraction
    low, high = math.floor(position), math.ceil(position)
    return values[low] if low == high else values[low] * (high - position) + values[high] * (position - low)


def execute(backend: MMapStorageBackend, sequence: list[int], mode: str, extent_size: int, group_window: int) -> tuple[list[int], int, int]:
    latencies = []
    sink = 0
    storage_bytes_touched = 0
    if mode in ("logical_only", "full_extent"):
        for page_id in sequence:
            started = time.perf_counter_ns()
            if mode == "logical_only":
                page = backend.get_page(page_id, validate=False)
                sink ^= touch_view(page.data)
                storage_bytes_touched += len(page.data)
                backend.release_page(page)
            else:
                extent = backend.get_extent(page_id, extent_size)
                sink ^= touch_view(extent)
                storage_bytes_touched += len(extent)
                extent.release()
            latencies.append(time.perf_counter_ns() - started)
        return latencies, sink, storage_bytes_touched

    if mode != "group_required":
        raise ValueError(mode)
    for start in range(0, len(sequence), group_window):
        batch = sequence[start:start + group_window]
        groups: dict[int, list[int]] = {}
        for page_id in batch:
            metadata = backend.page_metadata(page_id)
            groups.setdefault(metadata.offset // extent_size, []).append(page_id)
        batch_started = time.perf_counter_ns()
        for page_ids in groups.values():
            unique = list(dict.fromkeys(page_ids))
            if len(unique) > 1:
                extent = backend.get_extent(unique[0], extent_size)
                sink ^= touch_view(extent)
                storage_bytes_touched += len(extent)
                extent.release()
            else:
                page = backend.get_page(unique[0], validate=False)
                sink ^= touch_view(page.data)
                storage_bytes_touched += len(page.data)
                backend.release_page(page)
        per_request = (time.perf_counter_ns() - batch_started) / len(batch)
        latencies.extend([int(per_request)] * len(batch))
    return latencies, sink, storage_bytes_touched


def main() -> int:
    parser = argparse.ArgumentParser(description="Logical page vs physical extent experiment")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--workload", choices=("associative_walk", "topic_switch"), required=True)
    parser.add_argument("--access-mode", choices=("logical_only", "full_extent", "group_required"), required=True)
    parser.add_argument("--cache-state", choices=("cold", "hot"), default="cold")
    parser.add_argument("--seed", type=int, default=20260807)
    parser.add_argument("--accesses", type=int, default=256)
    parser.add_argument("--working-set-mib", type=int, default=256)
    parser.add_argument("--group-window", type=int, default=8)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    backend = MMapStorageBackend(args.manifest)
    reset = backend.advise_drop_cache()
    backend.open_brain()
    manifest = backend.manifest
    logical_size = manifest["page_size_bytes"]
    extent_size = manifest["storage_extent_size_bytes"]
    working_pages = min(manifest["page_count"], max(1, args.working_set_mib * 1024**2 // logical_size))
    ids = list(range(working_pages))
    related = {item["page_id"]: tuple(item["related_pages"]) for item in manifest["pages"]}
    sequence = access_sequence(Workload(args.workload), ids, args.accesses, args.seed, related)
    sequence_sha = hashlib.sha256(json.dumps(sequence, separators=(",", ":")).encode()).hexdigest()
    mapping_initial = mapped_file_memory(backend.data_path)
    if args.cache_state == "hot":
        execute(backend, sequence, args.access_mode, extent_size, args.group_window)
    mapping_preconditioned = mapped_file_memory(backend.data_path)

    before = snapshot()
    sampler = MetricSampler()
    sampler.start()
    first_cpu = time.process_time()
    started_cpu = first_cpu
    started = time.perf_counter_ns()
    segment_metrics = []
    latencies, sink, storage_bytes_touched = [], 0, 0
    if args.workload == "topic_switch":
        third = max(1, len(sequence) // 3)
        segments = (("A1", sequence[:third]), ("B", sequence[third:2 * third]), ("A2", sequence[2 * third:]))
    else:
        segments = (("all", sequence),)
    for segment_name, segment_sequence in segments:
        segment_io_before = process_io()
        segment_faults_before = process_faults_cpu()
        segment_started = time.perf_counter_ns()
        segment_latencies, segment_sink, segment_touched = execute(
            backend, segment_sequence, args.access_mode, extent_size, args.group_window
        )
        segment_elapsed = time.perf_counter_ns() - segment_started
        segment_io_after = process_io()
        segment_faults_after = process_faults_cpu()
        segment_io = numeric_delta(segment_io_before, segment_io_after, ("read_bytes",))
        segment_faults = numeric_delta(segment_faults_before, segment_faults_after, ("minor_faults", "major_faults"))
        segment_metrics.append({
            "segment": segment_name, "accesses": len(segment_sequence), "elapsed_ms": segment_elapsed / 1e6,
            "latency_ms_p50": percentile(segment_latencies, .50) / 1e6,
            "latency_ms_p95": percentile(segment_latencies, .95) / 1e6,
            "physical_read_bytes": segment_io["read_bytes"], **segment_faults,
        })
        latencies.extend(segment_latencies)
        sink ^= segment_sink
        storage_bytes_touched += segment_touched
    elapsed_ns = time.perf_counter_ns() - started
    cpu_s = time.process_time() - started_cpu
    sampler.stop()
    after = snapshot()
    mapping_after = mapped_file_memory(backend.data_path)
    stats = backend.stats()
    backend.close_brain()

    io_delta = numeric_delta(before["io"], after["io"], ("read_bytes", "rchar", "syscr"))
    proc_delta = numeric_delta(before["process"], after["process"], ("minor_faults", "major_faults"))
    physical = io_delta["read_bytes"]
    useful = len(sequence) * logical_size
    first_latency = latencies[0] / 1e6
    first_cpu_ms = cpu_s * 1000 / len(sequence)
    physical_per_activation = physical / len(sequence) if physical is not None else None
    metrics = {
        "success": stats["checksum_errors"] == 0 and len(latencies) == len(sequence),
        "elapsed_ms": elapsed_ns / 1e6,
        "accesses_per_second": len(sequence) / (elapsed_ns / 1e9),
        "latency_ms_p50": percentile(latencies, .50) / 1e6,
        "latency_ms_p95": percentile(latencies, .95) / 1e6,
        "latency_ms_p99": percentile(latencies, .99) / 1e6,
        "cognitive_requested_bytes": useful,
        "storage_bytes_touched": storage_bytes_touched,
        "physical_read_bytes": physical,
        "physical_read_amplification": physical / useful if physical is not None else None,
        "useful_byte_ratio": useful / physical if physical else None,
        "coalesced_touch_amplification": storage_bytes_touched / useful,
        "cache_reuse_ratio": 1 - physical / storage_bytes_touched if physical is not None and storage_bytes_touched else None,
        "minor_faults": proc_delta["minor_faults"], "major_faults": proc_delta["major_faults"],
        "minor_faults_per_access": proc_delta["minor_faults"] / len(sequence),
        "cpu_ms_per_access": cpu_s * 1000 / len(sequence),
        "access_sink": sink, "checksum_errors": stats["checksum_errors"],
        "activation_cost": {
            "first_latency_ms": first_latency, "physical_read_bytes_per_activation": physical_per_activation,
            "cpu_ms_per_access": first_cpu_ms,
            "score_ms_plus_mib_plus_cpu_ms": first_latency + (physical_per_activation or 0) / 1024**2 + first_cpu_ms,
            "score_definition": "first latency ms + mean physical MiB/activation + mean CPU ms/activation",
        },
        **sampler.summary(),
    }
    payload = {
        "schema_version": 1, "experiment": "phase2_5-storage-extent",
        "configuration": {
            "manifest": str(args.manifest), "layout": manifest["layout"],
            "logical_page_size_bytes": logical_size, "storage_extent_size_bytes": extent_size,
            "workload": args.workload, "access_mode": args.access_mode, "cache_state": args.cache_state,
            "seed": args.seed, "accesses": args.accesses, "working_set_mib": args.working_set_mib,
            "group_window": args.group_window,
        },
        "sequence_sha256": sequence_sha,
        "segments": segment_metrics,
        "cache_evidence": {"fadvise": reset, "initial": mapping_initial, "preconditioned": mapping_preconditioned, "after": mapping_after},
        "metrics": metrics,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": str(args.output), "success": metrics["success"]}))
    return 0 if metrics["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
