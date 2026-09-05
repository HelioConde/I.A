#!/usr/bin/env python3
"""Cross-platform Phase 4E entry preflight.

This tool never executes the physical matrix and never rewrites a frozen file.
It exists so a Windows transfer host can verify the package honestly before
the native Debian runner performs the authoritative audit and experiment.
"""
from __future__ import annotations

import ctypes
import hashlib
import json
import os
import platform
import subprocess
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FREEZE_PATH = ROOT / "results/phase4e/preparation/phase4d-freeze-manifest.json"
OUTPUT_PATH = ROOT / "results/phase4e/local-preflight.json"
EXPECTED_SOURCE_COMMIT = "217df17ac30ba2a8c374088772f81926cc5beee3"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def verify_file(path: Path, expected: str) -> dict[str, Any]:
    if not path.is_file():
        return {"exists": False, "status": "MISSING", "actual_sha256": None}
    payload = path.read_bytes()
    actual = sha256_bytes(payload)
    if actual == expected:
        return {"exists": True, "status": "RAW_OK", "actual_sha256": actual, "bytes": len(payload)}
    try:
        normalized = payload.decode("utf-8").replace("\r\n", "\n").encode("utf-8")
    except UnicodeDecodeError:
        normalized = b""
    canonical = sha256_bytes(normalized) if normalized else None
    status = "LF_CANONICAL_OK" if canonical == expected else "MISMATCH"
    return {
        "exists": True,
        "status": status,
        "actual_sha256": actual,
        "canonical_lf_sha256": canonical,
        "bytes": len(payload),
    }


def total_ram_bytes() -> int | None:
    if os.name == "nt":
        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("length", ctypes.c_ulong),
                ("memory_load", ctypes.c_ulong),
                ("total_physical", ctypes.c_ulonglong),
                ("available_physical", ctypes.c_ulonglong),
                ("total_page_file", ctypes.c_ulonglong),
                ("available_page_file", ctypes.c_ulonglong),
                ("total_virtual", ctypes.c_ulonglong),
                ("available_virtual", ctypes.c_ulonglong),
                ("available_extended_virtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatus()
        status.length = ctypes.sizeof(status)
        return int(status.total_physical) if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)) else None
    try:
        return int(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"))
    except (AttributeError, OSError, ValueError):
        return None


def source_commit() -> str | None:
    source = ROOT / "third_party/llama.cpp"
    if not (source / ".git").exists():
        return None
    result = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=False,
    )
    return result.stdout.strip() or None


def environment() -> dict[str, Any]:
    system = platform.system()
    release = platform.release()
    proc_version = Path("/proc/version").read_text(errors="replace") if Path("/proc/version").is_file() else ""
    is_wsl = "microsoft" in f"{release} {proc_version}".lower()
    is_codespace = bool(os.environ.get("CODESPACES"))
    is_debian = Path("/etc/debian_version").is_file()
    native_debian = system == "Linux" and is_debian and not is_wsl and not is_codespace
    return {
        "system": system,
        "release": release,
        "machine": platform.machine(),
        "python": platform.python_version(),
        "total_ram_bytes": total_ram_bytes(),
        "is_debian": is_debian,
        "is_wsl": is_wsl,
        "is_codespace": is_codespace,
        "native_debian_candidate": native_debian,
        "classification": "NATIVE_DEBIAN_CANDIDATE" if native_debian else f"{system.upper()}_PREPARATION_ONLY",
    }


def main() -> int:
    freeze = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    files = {
        relative: verify_file(ROOT / relative, expected)
        for relative, expected in freeze["files"].items()
    }
    file_failures = [relative for relative, result in files.items() if result["status"] not in {"RAW_OK", "LF_CANONICAL_OK"}]
    commit = source_commit()
    runtime_candidates = [
        ROOT / "build/llama.cpp/bin/llama-completion",
        ROOT / "build/llama.cpp/bin/llama-completion.exe",
    ]
    runtime = next((path for path in runtime_candidates if path.is_file()), None)
    env = environment()
    source_ok = commit == EXPECTED_SOURCE_COMMIT
    freeze_ok = not file_failures
    transfer_sources_ready = freeze_ok and source_ok
    payload = {
        "schema_version": 1,
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "phase": "4E",
        "state": "PREPARATION_STARTED_PHYSICAL_MATRIX_NOT_EXECUTED",
        "freeze_id": freeze["freeze_id"],
        "freeze_files_ok": freeze_ok,
        "freeze_file_failures": file_failures,
        "freeze_files": files,
        "llama_cpp": {
            "path": "third_party/llama.cpp",
            "commit": commit,
            "expected_commit": EXPECTED_SOURCE_COMMIT,
            "commit_ok": source_ok,
        },
        "runtime": {
            "exists": runtime is not None,
            "path": str(runtime.relative_to(ROOT)) if runtime else None,
            "required_action": None if runtime else "BUILD_ON_NATIVE_DEBIAN_FROM_FROZEN_SOURCE",
        },
        "environment": env,
        "transfer_sources_ready": transfer_sources_ready,
        "physical_matrix_executed": False,
        "target_8gb_status": "NOT_TESTED",
        "physical_execution_allowed_here": False,
        "physical_execution_note": (
            "Run the authoritative audit first; candidate is native Debian."
            if env["native_debian_candidate"]
            else "Current host is preparation-only and cannot produce PHYSICAL_NATIVE or TARGET_8GB results."
        ),
        "next_action": (
            "TRANSFER_TO_NATIVE_DEBIAN_BUILD_RUNTIME_AND_RUN_AUDIT"
            if transfer_sources_ready and runtime is None
            else "RUN_NATIVE_DEBIAN_AUDIT" if transfer_sources_ready else "REPAIR_FREEZE_OR_SOURCE"
        ),
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT_PATH.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(OUTPUT_PATH)
    print(json.dumps({
        "state": payload["state"],
        "freeze_files_ok": freeze_ok,
        "llama_commit_ok": source_ok,
        "environment": env["classification"],
        "next_action": payload["next_action"],
    }, sort_keys=True))
    return 0 if transfer_sources_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
