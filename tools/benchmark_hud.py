#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import tracemalloc
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brain_ssd.hud.state import HudRuntime
from brain_ssd.observability.demo import build_demo_events


def _measure(iterations: int, enabled: bool) -> dict[str, float | int]:
    samples = []
    runtime = HudRuntime() if enabled else None
    events = build_demo_events(1.0)
    tracemalloc.start()
    start_cpu = time.process_time_ns()
    start = time.perf_counter_ns()
    for _ in range(iterations):
        if runtime:
            runtime.state.reset(data_source="BENCHMARK SYNTHETIC", demo_data=True)
            for event in events:
                tick = time.perf_counter_ns()
                runtime.emit(event)
                samples.append(time.perf_counter_ns() - tick)
        else:
            for event in events:
                tick = time.perf_counter_ns()
                _ = event.event_type
                samples.append(time.perf_counter_ns() - tick)
    wall_ns = time.perf_counter_ns() - start
    cpu_ns = time.process_time_ns() - start_cpu
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    if runtime:
        runtime.close()
    return {
        "iterations": iterations,
        "events_per_iteration": len(events),
        "wall_ms": wall_ns / 1e6,
        "cpu_ms": cpu_ns / 1e6,
        "peak_tracemalloc_bytes": peak_bytes,
        "mean_event_us": statistics.fmean(samples) / 1e3,
        "p95_event_us": sorted(samples)[int(len(samples) * 0.95) - 1] / 1e3,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure synthetic HUD projection overhead")
    parser.add_argument("--iterations", type=int, default=250)
    parser.add_argument("--output", type=Path, default=ROOT / "results/hud/overhead.json")
    args = parser.parse_args()
    disabled = _measure(args.iterations, False)
    enabled = _measure(args.iterations, True)
    result = {
        "schema_version": 1,
        "kind": "synthetic_observability_microbenchmark",
        "disclaimer": "This does not execute Qwen or Phase 4D. It isolates event serialization, bounded publication, narration and state projection.",
        "hud_off": disabled,
        "hud_on": enabled,
        "delta": {
            "wall_ms": enabled["wall_ms"] - disabled["wall_ms"],
            "cpu_ms": enabled["cpu_ms"] - disabled["cpu_ms"],
            "peak_tracemalloc_bytes": enabled["peak_tracemalloc_bytes"] - disabled["peak_tracemalloc_bytes"],
            "mean_event_us": enabled["mean_event_us"] - disabled["mean_event_us"],
        },
        "pipeline_metrics": {
            "ttft_delta_ms": None,
            "generation_latency_delta_ms": None,
            "router_latency_delta_ms": None,
            "reason": "A real OFF/ON inference rerun would create new cognitive experiment results and was outside this observability-only pass.",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
