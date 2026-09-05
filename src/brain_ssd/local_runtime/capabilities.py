from __future__ import annotations

import ctypes
import os
import platform
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


SUPPORTED = "SUPPORTED"
UNSUPPORTED = "UNSUPPORTED"
DEGRADED = "DEGRADED"
NOT_MEASURED = "NOT_MEASURED"
WINDOWS_NATIVE_FUNCTIONAL = "WINDOWS_NATIVE_FUNCTIONAL"
PHASE4E_INVALID_REASON = "Phase 4E canonical physical baseline requires Debian/Linux environment."


@dataclass(frozen=True, slots=True)
class Capability:
    status: str
    reason: str
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _windows_memory() -> dict[str, int | None]:
    if os.name != "nt":
        return {"total_bytes": None, "available_bytes": None}

    class MEMORYSTATUSEX(ctypes.Structure):
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

    status = MEMORYSTATUSEX()
    status.dwLength = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return {"total_bytes": None, "available_bytes": None}
    return {"total_bytes": int(status.ullTotalPhys), "available_bytes": int(status.ullAvailPhys)}


@dataclass(frozen=True, slots=True)
class EnvironmentCapabilities:
    environment_type: str
    phase4e_valid: bool
    phase4e_invalid_reason: str | None
    host: dict[str, Any]
    capabilities: dict[str, Capability]

    @classmethod
    def detect(
        cls,
        root: Path,
        *,
        system_name: str | None = None,
        os_name: str | None = None,
    ) -> "EnvironmentCapabilities":
        system = system_name or platform.system()
        effective_os_name = os_name or os.name
        is_windows = system.casefold() == "windows" or effective_os_name == "nt"
        is_linux = system.casefold() == "linux"
        memory = _windows_memory() if is_windows and os.name == "nt" else {
            "total_bytes": None,
            "available_bytes": None,
        }
        host = {
            "system": system,
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor() or os.environ.get("PROCESSOR_IDENTIFIER") or "unknown",
            "logical_cpu_count": os.cpu_count(),
            "python": platform.python_version(),
            "memory": memory,
        }
        unsupported_windows = {
            "procfs_metrics": Capability(UNSUPPORTED, "unsupported_on_windows"),
            "cgroups_v2": Capability(UNSUPPORTED, "unsupported_on_windows"),
            "psi_pressure": Capability(UNSUPPORTED, "unsupported_on_windows"),
            "madvise_cold": Capability(UNSUPPORTED, "unsupported_on_windows"),
            "madvise_pageout": Capability(UNSUPPORTED, "unsupported_on_windows"),
            "mincore_residency": Capability(UNSUPPORTED, "unsupported_on_windows"),
            "physical_ssd_io": Capability(
                DEGRADED,
                "Windows process I/O counters do not prove physical SSD reads or cache residency.",
            ),
            "temperature": Capability(NOT_MEASURED, "No stable standard-library Windows sensor API is used."),
        }
        if is_windows:
            capabilities = {
                "memory_mapped_brain": Capability(SUPPORTED, "Python mmap uses the native Windows file mapping API."),
                "process_memory": Capability(SUPPORTED, "Measured with GetProcessMemoryInfo."),
                "process_cpu": Capability(SUPPORTED, "Measured with GetProcessTimes."),
                "process_io_transfer": Capability(
                    SUPPORTED,
                    "Measured with GetProcessIoCounters; values are process transfer counters, not physical disk reads.",
                ),
                "windows_working_set": Capability(SUPPORTED, "Working set and peak working set are available."),
                "hud": Capability(SUPPORTED if (root / "hud/index.html").is_file() else DEGRADED, "Existing in-process HUD event bus."),
                **unsupported_windows,
            }
            return cls(WINDOWS_NATIVE_FUNCTIONAL, False, PHASE4E_INVALID_REASON, host, capabilities)

        capabilities = {
            "memory_mapped_brain": Capability(SUPPORTED, "Python mmap is available."),
            "process_memory": Capability(SUPPORTED if is_linux else DEGRADED, "Use the frozen Linux telemetry on Linux."),
            "process_cpu": Capability(SUPPORTED if is_linux else DEGRADED, "Use the frozen Linux telemetry on Linux."),
            "process_io_transfer": Capability(SUPPORTED if is_linux else DEGRADED, "Platform-specific implementation required."),
            "windows_working_set": Capability(UNSUPPORTED, "windows_only"),
            "procfs_metrics": Capability(SUPPORTED if is_linux else UNSUPPORTED, "linux_only"),
            "cgroups_v2": Capability(NOT_MEASURED, "Runtime detection required."),
            "psi_pressure": Capability(NOT_MEASURED, "Runtime detection required."),
            "madvise_cold": Capability(NOT_MEASURED, "Runtime detection required."),
            "madvise_pageout": Capability(NOT_MEASURED, "Runtime detection required."),
            "mincore_residency": Capability(NOT_MEASURED, "Runtime detection required."),
            "physical_ssd_io": Capability(NOT_MEASURED, "Requires the canonical Linux preflight."),
            "temperature": Capability(NOT_MEASURED, "No portable sensor API configured."),
            "hud": Capability(SUPPORTED if (root / "hud/index.html").is_file() else DEGRADED, "Existing in-process HUD event bus."),
        }
        return cls("LINUX_COMPATIBLE" if is_linux else "UNSUPPORTED_PLATFORM", False, PHASE4E_INVALID_REASON, host, capabilities)

    def to_dict(self) -> dict[str, Any]:
        return {
            "environment_type": self.environment_type,
            "phase4e_valid": self.phase4e_valid,
            "phase4e_invalid_reason": self.phase4e_invalid_reason,
            "host": self.host,
            "capabilities": {key: value.to_dict() for key, value in self.capabilities.items()},
        }
