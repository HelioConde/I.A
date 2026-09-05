from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def parse_limit(value: str) -> int | None:
    value = value.strip()
    if value == "max": return None
    parsed = int(value)
    if parsed < 0: raise ValueError("negative cgroup limit")
    return parsed


def parse_flat_key_values(text: str) -> dict[str, int]:
    result = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            try: result[parts[0]] = int(parts[1])
            except ValueError: continue
    return result


def parse_psi(text: str) -> dict[str, dict[str, float]]:
    result = {}
    for line in text.splitlines():
        parts = line.split()
        if not parts: continue
        values = {}
        for token in parts[1:]:
            if "=" in token:
                key, value = token.split("=", 1)
                values[key] = float(value)
        result[parts[0]] = values
    return result


def detect_environment() -> str:
    if os.environ.get("BRAIN_SSD_PHYSICAL_NATIVE") == "1": return "PHYSICAL_NATIVE"
    if Path("/.dockerenv").exists() or Path("/run/.containerenv").exists():
        try: limit = parse_limit(Path("/sys/fs/cgroup/memory.max").read_text())
        except (OSError, ValueError): limit = None
        return "CODESPACE_CONTAINER_LIMITED" if limit is not None else "CODESPACE_UNCONSTRAINED"
    return "PHYSICAL_NATIVE"


def classify_pressure(current: int | None, maximum: int | None, stat: dict[str, int], psi: dict) -> str:
    ratio = current / maximum if isinstance(current, int) and isinstance(maximum, int) and maximum else 0.0
    full10 = psi.get("full", {}).get("avg10", 0.0)
    some10 = psi.get("some", {}).get("avg10", 0.0)
    reclaim = stat.get("pgscan", 0) + stat.get("workingset_refault_file", 0)
    if (ratio >= .98 and (full10 > 0 or reclaim > 0)) or full10 >= 1.0: return "CRITICAL"
    if (ratio >= .90 and (some10 > 0 or reclaim > 0)) or some10 >= 1.0 or reclaim > 10000: return "HIGH"
    if ratio >= .65 or some10 > 0 or reclaim > 0: return "MODERATE"
    return "LOW"


@dataclass
class ResourcePressureMonitor:
    root: Path = Path("/sys/fs/cgroup")

    def _text(self, name: str) -> str:
        try: return (self.root / name).read_text()
        except (FileNotFoundError, PermissionError): return ""

    def snapshot(self) -> dict:
        try: maximum = parse_limit(self._text("memory.max"))
        except ValueError: maximum = None
        try: swap_maximum = parse_limit(self._text("memory.swap.max"))
        except ValueError: swap_maximum = None
        try: current = int(self._text("memory.current").strip())
        except ValueError: current = None
        try: peak = int(self._text("memory.peak").strip())
        except ValueError: peak = None
        stat = parse_flat_key_values(self._text("memory.stat"))
        events = parse_flat_key_values(self._text("memory.events"))
        psi_text = self._text("memory.pressure") or (Path("/proc/pressure/memory").read_text() if Path("/proc/pressure/memory").exists() else "")
        psi = parse_psi(psi_text)
        return {"memory_current": current, "memory_peak": peak, "memory_max": maximum,
                "memory_swap_max": swap_maximum, "stat": stat, "events": events, "psi": psi,
                "pressure_state": classify_pressure(current, maximum, stat, psi)}


def numeric_delta(before: dict, after: dict) -> dict:
    keys = set(before) | set(after)
    return {key: after.get(key, 0) - before.get(key, 0) for key in keys
            if isinstance(before.get(key, 0), int) and isinstance(after.get(key, 0), int)}


def classify_container_result(returncode: int, oom_killed: bool, payload: object) -> str:
    if oom_killed: return "OOM_INVALID"
    if returncode != 0 or not isinstance(payload, dict): return "FAILED"
    events = payload.get("cgroup_events_delta", {})
    if events.get("oom", 0) or events.get("oom_kill", 0): return "OOM_INVALID"
    return "VALID"
