#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brain_ssd.hardware import collect_hardware
from brain_ssd.storage import MMapStorageBackend, StorageIntegrityError, touch_view
from brain_ssd.system_metrics import MetricSampler, mapped_file_memory, numeric_delta, process_io, snapshot
from brain_ssd.workloads import Workload, access_sequence


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] * (upper - position) + ordered[upper] * (position - lower)


def touch_pages(backend: MMapStorageBackend, page_ids: list[int], validation_mode: str) -> int:
    sink = 0
    for page_id in page_ids:
        page = backend.get_page(page_id, validate=validation_mode == "integrity")
        if validation_mode != "integrity":
            sink ^= touch_view(page.data)
        backend.release_page(page)
    return sink


def main() -> int:
    parser = argparse.ArgumentParser(description="Isolated Brain-SSD mmap storage benchmark")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--workload", required=True, choices=[item.value for item in Workload])
    parser.add_argument("--seed", type=int, default=20260807)
    parser.add_argument("--accesses", type=int, default=16)
    parser.add_argument("--working-set-mib", type=int, required=True)
    parser.add_argument("--memory-budget-mib", type=int, required=True)
    parser.add_argument("--cache-state", choices=("cold", "warm", "hot"), required=True)
    parser.add_argument("--validation-mode", choices=("integrity", "performance", "first_activation"), default="integrity")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    backend = MMapStorageBackend(args.manifest)
    cache_reset_advice_applied = backend.advise_drop_cache()
    backend.open_brain()
    manifest = backend.manifest
    page_size = manifest["page_size_bytes"]
    working_bytes = args.working_set_mib * 1024 * 1024
    budget_bytes = args.memory_budget_mib * 1024 * 1024
    if page_size > budget_bytes:
        parser.error("a single page exceeds --memory-budget-mib")
    working_pages = min(manifest["page_count"], max(1, working_bytes // page_size))
    page_ids = list(range(working_pages))
    related = {item["page_id"]: tuple(item.get("related_pages", ())) for item in manifest["pages"]}
    sequence = access_sequence(Workload(args.workload), page_ids, args.accesses, args.seed, related)

    mapping_before_precondition = mapped_file_memory(backend.data_path)
    access_sink = 0
    if args.cache_state == "warm":
        unique = list(dict.fromkeys(sequence))
        access_sink ^= touch_pages(backend, unique[:max(1, len(unique) // 4)], args.validation_mode)
    elif args.cache_state == "hot":
        access_sink ^= touch_pages(backend, list(dict.fromkeys(sequence)), args.validation_mode)
    mapping_after_precondition = mapped_file_memory(backend.data_path)

    before = snapshot()
    sampler = MetricSampler()
    sampler.start()
    latencies_ns = []
    failure = None
    first_activation = None
    operation_cpu_started = time.process_time()
    started = time.perf_counter_ns()
    try:
        for page_id in sequence:
            first_before_io = process_io() if first_activation is None else None
            first_cpu = time.process_time() if first_activation is None else None
            access_started = time.perf_counter_ns()
            policy = "always" if args.validation_mode == "integrity" else "first" if args.validation_mode == "first_activation" else "never"
            page = backend.get_page(page_id, validate=policy)
            if args.validation_mode != "integrity":
                access_sink ^= touch_view(page.data)
            backend.release_page(page)
            access_elapsed = time.perf_counter_ns() - access_started
            latencies_ns.append(access_elapsed)
            if first_activation is None:
                first_cpu_ms = (time.process_time() - first_cpu) * 1000
                first_after_io = process_io()
                first_io = numeric_delta(first_before_io, first_after_io, ("read_bytes", "rchar", "syscr"))
                physical_mib = (first_io["read_bytes"] or 0) / 1024**2
                first_activation = {
                    "latency_ms": access_elapsed / 1e6,
                    "physical_read_bytes": first_io["read_bytes"],
                    "cpu_ms": first_cpu_ms,
                    "score_ms_plus_mib_plus_cpu_ms": access_elapsed / 1e6 + physical_mib + first_cpu_ms,
                    "score_definition": "latency_ms + physical_read_MiB + cpu_ms; experimental scalar for screening",
                }
    except StorageIntegrityError as error:
        failure = str(error)
    elapsed_ns = time.perf_counter_ns() - started
    operation_cpu_s = time.process_time() - operation_cpu_started
    sampler.stop()
    after = snapshot()
    mapping_after = mapped_file_memory(backend.data_path)
    stats = backend.stats()
    backend.close_brain()

    process_io_delta = numeric_delta(before["io"], after["io"], ("read_bytes", "write_bytes", "rchar", "wchar", "syscr", "syscw"))
    process_delta = numeric_delta(before["process"], after["process"], ("minor_faults", "major_faults", "cpu_time_s"))
    cgroup_delta = numeric_delta(before["cgroup"], after["cgroup"], (
        "memory_current_bytes", "anon_bytes", "file_bytes", "file_mapped_bytes", "pgfault", "pgmajfault",
        "pgscan", "pgsteal", "pgscan_direct", "pgsteal_direct",
    ))
    logical_bytes = len(latencies_ns) * page_size
    physical_bytes = process_io_delta["read_bytes"]
    payload = {
        "schema_version": 1,
        "experiment": "phase2-mmap-storage-v0",
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "configuration": {
            "manifest": str(args.manifest), "corpus_size_bytes": manifest["corpus_size_bytes"],
            "page_size_bytes": page_size, "page_count": manifest["page_count"], "workload": args.workload,
            "seed": args.seed, "accesses_requested": args.accesses, "working_set_bytes_requested": working_bytes,
            "working_set_pages": working_pages, "memory_budget_bytes_logical": budget_bytes,
            "memory_budget_is_hard_limit": False, "cache_state": args.cache_state,
            "validation_mode": args.validation_mode,
            "performance_touch": "one byte per 4096-byte OS page plus final byte; deterministic 64-bit sink" if args.validation_mode != "integrity" else None,
            "manifest_bytes": args.manifest.stat().st_size,
            "metadata_bytes_per_page": args.manifest.stat().st_size / manifest["page_count"],
        },
        "cache_evidence": {
            "classification": f"best-effort {args.cache_state}",
            "posix_fadvise_dontneed_applied": cache_reset_advice_applied,
            "mapping_before_precondition": mapping_before_precondition,
            "mapping_after_precondition": mapping_after_precondition,
            "mapping_after_benchmark": mapping_after,
            "brain_managed_cache_bytes": 0,
            "linux_page_cache_direct_hit_count": None,
            "limitation": "Linux exposes residency and physical read deltas, not an exact per-access page-cache hit counter.",
        },
        "metrics": {
            "success": failure is None and stats["checksum_errors"] == 0 and len(latencies_ns) == args.accesses,
            "failure": failure,
            "accesses_completed": len(latencies_ns), "elapsed_ms": elapsed_ns / 1e6,
            "accesses_per_second": len(latencies_ns) / (elapsed_ns / 1e9) if elapsed_ns else None,
            "logical_bytes_requested": logical_bytes,
            "logical_throughput_bytes_per_second": logical_bytes / (elapsed_ns / 1e9) if elapsed_ns else None,
            "physical_read_bytes": physical_bytes,
            "physical_read_amplification": physical_bytes / logical_bytes if physical_bytes is not None and logical_bytes else None,
            "useful_byte_ratio": logical_bytes / physical_bytes if physical_bytes not in (None, 0) else None,
            "latency_ms_p50": percentile(latencies_ns, .50) / 1e6 if latencies_ns else None,
            "latency_ms_p95": percentile(latencies_ns, .95) / 1e6 if latencies_ns else None,
            "latency_ms_p99": percentile(latencies_ns, .99) / 1e6 if latencies_ns else None,
            "latency_ms_mean": statistics.mean(latencies_ns) / 1e6 if latencies_ns else None,
            "checksum_errors": stats["checksum_errors"],
            "verified_pages": stats["verified_pages"],
            "access_sink": access_sink,
            "minor_faults_per_access": process_delta["minor_faults"] / len(latencies_ns) if latencies_ns else None,
            "major_faults_per_access": process_delta["major_faults"] / len(latencies_ns) if latencies_ns else None,
            "cpu_ms_per_access": operation_cpu_s * 1000 / len(latencies_ns) if latencies_ns else None,
            "activation_cost": first_activation,
            **process_delta, **{f"io_{key}": value for key, value in process_io_delta.items()},
            **{f"cgroup_delta_{key}": value for key, value in cgroup_delta.items()},
            **sampler.summary(),
            "cpu_percent_avg_single_core_scale": 100 * operation_cpu_s / (elapsed_ns / 1e9) if elapsed_ns else None,
            "cpu_average_basis": "process CPU time during measured loop; includes checksum validation",
            "cpu_max_limitation": "sampled process peak includes telemetry-thread overhead",
        },
        "before": before, "after": after,
        "hardware": collect_hardware(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": str(args.output), "success": payload["metrics"]["success"]}))
    return 0 if payload["metrics"]["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
