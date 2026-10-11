"""Conservative Windows resource policy for the experimental Brain-SSD chat.

Do not apply to the frozen research Core. No OS control, background workloads,
or GPU inference: select a safe chat-only llama.cpp mode from RAM headroom.
"""
from __future__ import annotations

import ctypes
import os
from dataclasses import dataclass

GiB = 1024 ** 3


@dataclass(frozen=True)
class MemoryInfo:
    total: int
    available: int


class _MemoryStatusEx(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def windows_memory() -> MemoryInfo | None:
    if os.name != "nt":
        return None
    state = _MemoryStatusEx()
    state.dwLength = ctypes.sizeof(_MemoryStatusEx)
    try:
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(state)):
            return None
    except (OSError, AttributeError, ValueError):
        return None
    if not state.ullTotalPhys or not state.ullAvailPhys:
        return None
    return MemoryInfo(int(state.ullTotalPhys), int(state.ullAvailPhys))


def choose_mode(profile: str, model_bytes: int, server_available: bool,
                memory: MemoryInfo | None) -> tuple[str, str]:
    """Return (mode, reason) without ever assuming swap is equivalent to RAM.

    Reserve at least 2 GiB for Windows and foreground applications. Require
    *additional* available physical RAM because Windows caches file-backed
    model pages, and a persistent llama-server allocates KV/cache memory.
    """
    if profile == "economia":
        return "subprocess", "economy_releases_ram"
    if not server_available:
        return "subprocess", "server_not_installed"
    if memory is None:
        return "subprocess", "physical_ram_unavailable"
    if memory.total < 12 * GiB:
        return "subprocess", "low_total_ram"
    reserve = max(6 * GiB, int(model_bytes * 1.8) + 2 * GiB)
    if memory.available < reserve:
        return "subprocess", "low_available_ram"
    return "persistent", "ram_headroom_sufficient"


def recommended_threads(profile: str, logical_cpus: int | None) -> int:
    """Avoid pegging all cores and competing with the Windows desktop."""
    if profile == "economia":
        return 2
    count = logical_cpus or 4
    if count >= 12:
        return 6
    if count >= 8:
        return 4
    if count >= 6:
        return 3
    return 2


def answer_token_limit(model_bytes: int, requested: int | None = None) -> int:
    """Short by default on >2 GiB CPU-only models; allow explicit longer replies."""
    if requested is not None:
        if type(requested) is not int or requested < 48 or requested > 256:
            raise ValueError("Limite de resposta deve estar entre 48 e 256 tokens.")
        return requested
    return 112 if model_bytes >= 2 * GiB else 160
