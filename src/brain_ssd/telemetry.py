from __future__ import annotations

import hashlib
import os
import queue
import re
import subprocess
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

from brain_ssd.system_metrics import cgroup_memory, process_io, process_memory


@dataclass
class ProcessSample:
    monotonic_s: float
    cpu_time_s: float
    rss_bytes: int
    minor_faults: int
    major_faults: int
    read_bytes: int
    write_bytes: int
    read_syscalls: int
    write_syscalls: int
    rchar: int | None
    pss_bytes: int | None
    anonymous_bytes: int | None
    rss_file_bytes: int | None
    private_clean_bytes: int | None
    private_dirty_bytes: int | None
    shared_clean_bytes: int | None
    shared_dirty_bytes: int | None
    cgroup_memory_current_bytes: int | None
    cgroup_memory_peak_bytes: int | None
    cgroup_anon_bytes: int | None
    cgroup_file_bytes: int | None
    cgroup_file_mapped_bytes: int | None
    cgroup_pgfault: int | None
    cgroup_pgmajfault: int | None


def _read_proc(pid: int, started: float) -> ProcessSample | None:
    try:
        stat = Path(f"/proc/{pid}/stat").read_text().split()
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return None
    try:
        memory = process_memory(pid)
        io_map = process_io(pid)
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return None
    cgroup = cgroup_memory()
    ticks = os.sysconf(os.sysconf_names["SC_CLK_TCK"])
    return ProcessSample(
        monotonic_s=time.monotonic() - started,
        cpu_time_s=(int(stat[13]) + int(stat[14])) / ticks,
        rss_bytes=memory.get("rss_bytes") or 0,
        minor_faults=int(stat[9]),
        major_faults=int(stat[11]),
        read_bytes=io_map.get("read_bytes") or 0,
        write_bytes=io_map.get("write_bytes") or 0,
        read_syscalls=io_map.get("syscr") or 0,
        write_syscalls=io_map.get("syscw") or 0,
        rchar=io_map.get("rchar"),
        pss_bytes=memory.get("pss_bytes"),
        anonymous_bytes=memory.get("anonymous_bytes"),
        rss_file_bytes=memory.get("rss_file_bytes_status"),
        private_clean_bytes=memory.get("private_clean_bytes"),
        private_dirty_bytes=memory.get("private_dirty_bytes"),
        shared_clean_bytes=memory.get("shared_clean_bytes"),
        shared_dirty_bytes=memory.get("shared_dirty_bytes"),
        cgroup_memory_current_bytes=cgroup.get("memory_current_bytes"),
        cgroup_memory_peak_bytes=cgroup.get("memory_peak_bytes"),
        cgroup_anon_bytes=cgroup.get("anon_bytes"),
        cgroup_file_bytes=cgroup.get("file_bytes"),
        cgroup_file_mapped_bytes=cgroup.get("file_mapped_bytes"),
        cgroup_pgfault=cgroup.get("pgfault"),
        cgroup_pgmajfault=cgroup.get("pgmajfault"),
    )


def _reader(stream, channel: str, events: queue.Queue, started: float) -> None:
    while True:
        chunk = stream.read(1)
        if not chunk:
            break
        events.put((channel, time.monotonic() - started, chunk))
    events.put((channel, time.monotonic() - started, None))


def _runtime_tokens(stderr: str) -> tuple[int | None, float | None]:
    patterns = (
        r"eval time\s*=.*?/\s*(\d+) runs.*?([0-9.]+) tokens per second",
        r"eval time\s*=.*?/\s*(\d+) tokens.*?([0-9.]+) tokens per second",
    )
    for pattern in patterns:
        match = re.search(pattern, stderr, re.IGNORECASE | re.DOTALL)
        if match:
            return int(match.group(1)), float(match.group(2))
    return None, None


def run_measured(command: Sequence[str], sample_interval_s: float = 0.05) -> dict:
    if not command:
        raise ValueError("command cannot be empty")
    started = time.monotonic()
    proc = subprocess.Popen(
        list(command), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=0
    )
    assert proc.stdout is not None and proc.stderr is not None
    events: queue.Queue = queue.Queue()
    threads = [
        threading.Thread(target=_reader, args=(proc.stdout, "stdout", events, started), daemon=True),
        threading.Thread(target=_reader, args=(proc.stderr, "stderr", events, started), daemon=True),
    ]
    for thread in threads:
        thread.start()

    samples: list[ProcessSample] = []
    stdout_parts: list[str] = []
    stderr_parts: list[str] = []
    first_output_s: float | None = None
    closed = set()
    while proc.poll() is None or len(closed) < 2:
        sample = _read_proc(proc.pid, started)
        if sample is not None:
            samples.append(sample)
        deadline = time.monotonic() + sample_interval_s
        while time.monotonic() < deadline:
            try:
                channel, elapsed, chunk = events.get(timeout=max(0.001, deadline - time.monotonic()))
            except queue.Empty:
                break
            if chunk is None:
                closed.add(channel)
            elif channel == "stdout":
                stdout_parts.append(chunk)
                if first_output_s is None and not chunk.isspace():
                    first_output_s = elapsed
            else:
                stderr_parts.append(chunk)

    return_code = proc.wait()
    for thread in threads:
        thread.join(timeout=1)
    proc.stdout.close()
    proc.stderr.close()
    elapsed_s = time.monotonic() - started
    stdout = "".join(stdout_parts)
    stderr = "".join(stderr_parts)
    generated_tokens, runtime_tps = _runtime_tokens(stderr)

    first = samples[0] if samples else None
    last = samples[-1] if samples else None
    cpu_percent_avg = None
    cpu_percent_max = None
    if len(samples) >= 2:
        cpu_delta = last.cpu_time_s - first.cpu_time_s
        wall_delta = last.monotonic_s - first.monotonic_s
        cpu_percent_avg = 100.0 * cpu_delta / wall_delta if wall_delta > 0 else None
        interval_cpu = []
        for older, newer in zip(samples, samples[1:]):
            dt = newer.monotonic_s - older.monotonic_s
            if dt > 0:
                interval_cpu.append(100.0 * (newer.cpu_time_s - older.cpu_time_s) / dt)
        cpu_percent_max = max(interval_cpu, default=None)

    def delta(field: str) -> int | None:
        if first is None or last is None:
            return None
        start_value, end_value = getattr(first, field), getattr(last, field)
        if start_value is None or end_value is None:
            return None
        return max(0, end_value - start_value)

    metrics = {
        "ttft_ms": first_output_s * 1000 if first_output_s is not None else None,
        "latency_ms": elapsed_s * 1000,
        "generated_tokens": generated_tokens,
        "tokens_per_second": runtime_tps,
        "cpu_percent_avg_single_core_scale": cpu_percent_avg,
        "cpu_percent_max_single_core_scale": cpu_percent_max,
        "rss_bytes_max": max((sample.rss_bytes for sample in samples), default=None),
        "pss_bytes_max": max((sample.pss_bytes for sample in samples if sample.pss_bytes is not None), default=None),
        "anonymous_bytes_max": max((sample.anonymous_bytes for sample in samples if sample.anonymous_bytes is not None), default=None),
        "rss_file_bytes_max": max((sample.rss_file_bytes for sample in samples if sample.rss_file_bytes is not None), default=None),
        "private_clean_bytes_max": max((sample.private_clean_bytes for sample in samples if sample.private_clean_bytes is not None), default=None),
        "private_dirty_bytes_max": max((sample.private_dirty_bytes for sample in samples if sample.private_dirty_bytes is not None), default=None),
        "shared_clean_bytes_max": max((sample.shared_clean_bytes for sample in samples if sample.shared_clean_bytes is not None), default=None),
        "shared_dirty_bytes_max": max((sample.shared_dirty_bytes for sample in samples if sample.shared_dirty_bytes is not None), default=None),
        "minor_page_faults": delta("minor_faults"),
        "major_page_faults": delta("major_faults"),
        "storage_read_bytes": delta("read_bytes"),
        "storage_read_bytes_process_total": last.read_bytes if last is not None else None,
        "storage_write_bytes": delta("write_bytes"),
        "read_syscalls": delta("read_syscalls"),
        "rchar": delta("rchar"),
        "cgroup_memory_current_bytes_max": max((sample.cgroup_memory_current_bytes for sample in samples if sample.cgroup_memory_current_bytes is not None), default=None),
        "cgroup_memory_peak_bytes_reported": max((sample.cgroup_memory_peak_bytes for sample in samples if sample.cgroup_memory_peak_bytes is not None), default=None),
        "cgroup_anon_bytes_max": max((sample.cgroup_anon_bytes for sample in samples if sample.cgroup_anon_bytes is not None), default=None),
        "cgroup_file_bytes_max": max((sample.cgroup_file_bytes for sample in samples if sample.cgroup_file_bytes is not None), default=None),
        "cgroup_file_mapped_bytes_max": max((sample.cgroup_file_mapped_bytes for sample in samples if sample.cgroup_file_mapped_bytes is not None), default=None),
        "cgroup_pgfault_delta": delta("cgroup_pgfault"),
        "cgroup_pgmajfault_delta": delta("cgroup_pgmajfault"),
        "write_syscalls": delta("write_syscalls"),
        "io_latency_ms": None,
        "active_brain_size_bytes": None,
        "cognitive_cache_hit_rate": None,
        "prefetch_hit_rate": None,
        "prefetch_waste_bytes": None,
        "circuit_activation_rate": None,
        "knowledge_io_per_answer_bytes": None,
        "activated_cortical_pages": None,
    }
    unavailable = {
        "io_latency_ms": "not exposed per-process by /proc; requires a later controlled tracer",
        "active_brain_size_bytes": "Storage Brain is not implemented; RSS is not equivalent",
        "cognitive_cache_hit_rate": "cognitive cache is not implemented",
        "prefetch_hit_rate": "prefetch is not implemented",
        "prefetch_waste_bytes": "prefetch is not implemented",
        "circuit_activation_rate": "router/gating are not implemented",
        "knowledge_io_per_answer_bytes": "no Cortical Pages exist in Phase 1",
        "activated_cortical_pages": "no Cortical Pages exist in Phase 1",
    }
    return {
        "schema_version": 1,
        "command": list(command),
        "return_code": return_code,
        "stdout": stdout,
        "stderr": stderr,
        "stdout_sha256": hashlib.sha256(stdout.encode()).hexdigest(),
        "metrics": metrics,
        "unavailable_metrics": unavailable,
        "sample_count": len(samples),
        "samples": [asdict(sample) for sample in samples],
    }
