from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path


def _text(path: str) -> str | None:
    try:
        return Path(path).read_text().strip()
    except (FileNotFoundError, PermissionError):
        return None


def _command(*args: str) -> str | None:
    if shutil.which(args[0]) is None:
        return None
    result = subprocess.run(args, text=True, capture_output=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def collect_hardware() -> dict:
    cpu_max = _text("/sys/fs/cgroup/cpu.max")
    effective_cpu_quota = None
    if cpu_max:
        quota, period = cpu_max.split()
        if quota != "max":
            effective_cpu_quota = int(quota) / int(period)
    return {
        "schema_version": 1,
        "platform": platform.platform(),
        "kernel": platform.release(),
        "machine": platform.machine(),
        "logical_cpus_visible": os.cpu_count(),
        "cgroup": {
            "version": 2 if _text("/sys/fs/cgroup/cgroup.controllers") is not None else None,
            "cpu_max": cpu_max,
            "effective_cpu_quota": effective_cpu_quota,
            "cpuset_cpus_effective": _text("/sys/fs/cgroup/cpuset.cpus.effective"),
            "memory_max": _text("/sys/fs/cgroup/memory.max"),
            "memory_high": _text("/sys/fs/cgroup/memory.high"),
            "memory_current": _text("/sys/fs/cgroup/memory.current"),
            "memory_peak": _text("/sys/fs/cgroup/memory.peak"),
            "memory_stat": _text("/sys/fs/cgroup/memory.stat"),
        },
        "lscpu": _command("lscpu", "--json"),
        "memory": _text("/proc/meminfo"),
        "swaps": _text("/proc/swaps"),
        "block_devices": _command("lsblk", "--json", "-o", "NAME,TYPE,SIZE,FSTYPE,MOUNTPOINTS,ROTA,MODEL"),
        "workspace_filesystem": _command("findmnt", "--json", "-T", str(Path.cwd())),
        "gpu": {
            "nvidia_smi": _command("nvidia-smi", "-L"),
            "lspci_display": _command("sh", "-c", "lspci | grep -Ei 'vga|3d|display'"),
        },
    }
