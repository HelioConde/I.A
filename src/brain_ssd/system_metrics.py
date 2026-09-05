from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path

KIB = 1024
CGROUP = Path("/sys/fs/cgroup")


def _key_values(path: Path, kib_values: bool = False) -> dict[str, int]:
    result: dict[str, int] = {}
    try:
        lines = path.read_text().splitlines()
    except (FileNotFoundError, PermissionError):
        return result
    for line in lines:
        parts = line.replace(":", "").split()
        if len(parts) < 2:
            continue
        try:
            value = int(parts[1])
        except ValueError:
            continue
        result[parts[0]] = value * KIB if kib_values and len(parts) > 2 and parts[2] == "kB" else value
    return result


def process_memory(pid: int | str = "self") -> dict:
    status = _key_values(Path(f"/proc/{pid}/status"), kib_values=True)
    smaps = _key_values(Path(f"/proc/{pid}/smaps_rollup"), kib_values=True)
    return {
        "rss_bytes": smaps.get("Rss", status.get("VmRSS")),
        "pss_bytes": smaps.get("Pss"),
        "anonymous_bytes": smaps.get("Anonymous", status.get("RssAnon")),
        "rss_anon_bytes_status": status.get("RssAnon"),
        "rss_file_bytes_status": status.get("RssFile"),
        "rss_shmem_bytes_status": status.get("RssShmem"),
        "pss_anon_bytes": smaps.get("Pss_Anon"),
        "pss_file_bytes": smaps.get("Pss_File"),
        "pss_shmem_bytes": smaps.get("Pss_Shmem"),
        "private_clean_bytes": smaps.get("Private_Clean"),
        "private_dirty_bytes": smaps.get("Private_Dirty"),
        "shared_clean_bytes": smaps.get("Shared_Clean"),
        "shared_dirty_bytes": smaps.get("Shared_Dirty"),
        "swap_bytes": smaps.get("Swap"),
    }


def process_io(pid: int | str = "self") -> dict:
    values = _key_values(Path(f"/proc/{pid}/io"))
    return {key: values.get(key) for key in ("read_bytes", "write_bytes", "rchar", "wchar", "syscr", "syscw")}


def process_faults_cpu(pid: int | str = "self") -> dict:
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().split()
    except (FileNotFoundError, PermissionError):
        return {}
    ticks = os.sysconf(os.sysconf_names["SC_CLK_TCK"])
    return {
        "minor_faults": int(fields[9]),
        "major_faults": int(fields[11]),
        "cpu_time_s": (int(fields[13]) + int(fields[14])) / ticks,
    }


def cgroup_memory() -> dict:
    if not (CGROUP / "cgroup.controllers").exists():
        return {"available": False, "reason": "cgroup v2 unified hierarchy not detected"}
    stat = _key_values(CGROUP / "memory.stat")
    def scalar(name: str):
        try:
            text = (CGROUP / name).read_text().strip()
            return text if text == "max" else int(text)
        except (FileNotFoundError, PermissionError, ValueError):
            return None
    return {
        "available": True,
        "memory_current_bytes": scalar("memory.current"),
        "memory_peak_bytes": scalar("memory.peak"),
        "memory_max": scalar("memory.max"),
        "memory_high": scalar("memory.high"),
        "anon_bytes": stat.get("anon"),
        "file_bytes": stat.get("file"),
        "file_mapped_bytes": stat.get("file_mapped"),
        "pgfault": stat.get("pgfault"),
        "pgmajfault": stat.get("pgmajfault"),
        "pgscan": stat.get("pgscan"),
        "pgsteal": stat.get("pgsteal"),
        "pgscan_direct": stat.get("pgscan_direct"),
        "pgsteal_direct": stat.get("pgsteal_direct"),
    }


def mapped_file_memory(path: Path) -> dict:
    totals = {key: 0 for key in ("Size", "Rss", "Pss", "Shared_Clean", "Shared_Dirty", "Private_Clean", "Private_Dirty", "Anonymous")}
    matched = 0
    current_match = False
    try:
        lines = Path("/proc/self/smaps").read_text().splitlines()
    except (FileNotFoundError, PermissionError):
        return {"available": False, "reason": "/proc/self/smaps unavailable"}
    resolved = str(path.resolve())
    for line in lines:
        if "-" in line.split(maxsplit=1)[0] and len(line.split()) >= 5:
            current_match = line.endswith(resolved)
            if current_match:
                matched += 1
            continue
        if current_match and ":" in line:
            key, rest = line.split(":", 1)
            if key in totals:
                parts = rest.split()
                if parts:
                    totals[key] += int(parts[0]) * KIB
    return {"available": bool(matched), "mapping_count": matched, **{f"{key.lower()}_bytes": value for key, value in totals.items()}}


def snapshot() -> dict:
    return {
        "monotonic_s": time.monotonic(),
        "memory": process_memory(),
        "io": process_io(),
        "process": process_faults_cpu(),
        "cgroup": cgroup_memory(),
    }


def numeric_delta(before: dict, after: dict, keys: tuple[str, ...]) -> dict:
    result = {}
    for key in keys:
        left, right = before.get(key), after.get(key)
        result[key] = None if not isinstance(left, (int, float)) or not isinstance(right, (int, float)) else right - left
    return result


@dataclass
class MetricSampler:
    interval_s: float = 0.01

    def __post_init__(self) -> None:
        self.samples: list[dict] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self.samples.append(snapshot())
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.wait(self.interval_s):
            self.samples.append(snapshot())

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join()
        self.samples.append(snapshot())

    def summary(self) -> dict:
        def maximum(section: str, key: str):
            values = [sample[section].get(key) for sample in self.samples]
            values = [value for value in values if isinstance(value, (int, float))]
            return max(values) if values else None
        cpu_intervals = []
        for before, after in zip(self.samples, self.samples[1:]):
            dt = after["monotonic_s"] - before["monotonic_s"]
            dcpu = after["process"].get("cpu_time_s", 0) - before["process"].get("cpu_time_s", 0)
            if dt > 0:
                cpu_intervals.append(100 * dcpu / dt)
        first, last = self.samples[0], self.samples[-1]
        wall = last["monotonic_s"] - first["monotonic_s"]
        cpu = last["process"].get("cpu_time_s", 0) - first["process"].get("cpu_time_s", 0)
        return {
            "sample_count": len(self.samples),
            "rss_bytes_max": maximum("memory", "rss_bytes"),
            "pss_bytes_max": maximum("memory", "pss_bytes"),
            "anonymous_bytes_max": maximum("memory", "anonymous_bytes"),
            "rss_file_bytes_max": maximum("memory", "rss_file_bytes_status"),
            "private_clean_bytes_max": maximum("memory", "private_clean_bytes"),
            "private_dirty_bytes_max": maximum("memory", "private_dirty_bytes"),
            "shared_clean_bytes_max": maximum("memory", "shared_clean_bytes"),
            "shared_dirty_bytes_max": maximum("memory", "shared_dirty_bytes"),
            "cgroup_memory_current_bytes_max": maximum("cgroup", "memory_current_bytes"),
            "cgroup_memory_peak_bytes_reported": maximum("cgroup", "memory_peak_bytes"),
            "cgroup_anon_bytes_max": maximum("cgroup", "anon_bytes"),
            "cgroup_file_bytes_max": maximum("cgroup", "file_bytes"),
            "cgroup_file_mapped_bytes_max": maximum("cgroup", "file_mapped_bytes"),
            "cgroup_pgscan_max": maximum("cgroup", "pgscan"),
            "cgroup_pgsteal_max": maximum("cgroup", "pgsteal"),
            "cpu_percent_avg_single_core_scale": 100 * cpu / wall if wall > 0 else None,
            "cpu_percent_max_single_core_scale": max(cpu_intervals, default=None),
        }
