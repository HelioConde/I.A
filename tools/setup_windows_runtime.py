#!/usr/bin/env python3
"""Read-only Windows-native runtime audit. It never installs or downloads anything."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brain_ssd.local_runtime.backend import probe_llama, resolve_llama_executable
from brain_ssd.local_runtime.capabilities import EnvironmentCapabilities
from brain_ssd.local_runtime.pipeline import MODEL_RELATIVE, file_sha256


VS_ROOT = Path(r"C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools")
CMAKE = VS_ROOT / r"Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe"
NINJA = VS_ROOT / r"Common7\IDE\CommonExtensions\Microsoft\CMake\Ninja\ninja.exe"
VCVARS = VS_ROOT / r"VC\Auxiliary\Build\vcvars64.bat"


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit the Brain-SSD Windows native functional runtime")
    parser.add_argument("--runtime", type=Path, help="Explicit llama-completion executable")
    args = parser.parse_args()
    model = ROOT / MODEL_RELATIVE
    payload: dict[str, object] = {
        "root": str(ROOT),
        **EnvironmentCapabilities.detect(ROOT).to_dict(),
        "tools": {
            "git": shutil.which("git"),
            "cmake": str(CMAKE) if CMAKE.is_file() else shutil.which("cmake"),
            "ninja": str(NINJA) if NINJA.is_file() else shutil.which("ninja"),
            "vcvars64": str(VCVARS) if VCVARS.is_file() else None,
            "python": sys.executable,
        },
        "model": {
            "path": str(model),
            "exists": model.is_file(),
            "bytes": model.stat().st_size if model.is_file() else None,
            "sha256": file_sha256(model) if model.is_file() else None,
        },
    }
    try:
        executable = resolve_llama_executable(ROOT, args.runtime)
        payload["runtime"] = probe_llama(executable)
    except (FileNotFoundError, OSError) as error:
        payload["runtime"] = {"status": "MISSING", "error": str(error)}
    payload["ready"] = bool(
        model.is_file()
        and isinstance(payload["runtime"], dict)
        and payload["runtime"].get("frozen_commit_match")
        and payload["runtime"].get("cpu_only_build")
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
