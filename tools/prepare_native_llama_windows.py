"""Opt-in pinned source checkout + isolated Windows CPU build of llama.cpp.

Default run is READ-ONLY. --fetch explicitly permits network access and
--build explicitly permits compilation. Never modifies Brain-SSD binaries.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

UPSTREAM_URL = "https://github.com/ggml-org/llama.cpp"
DEFAULT_REVISION = "972b5fcc19670e597f8de9bf5cacfb85752a5fff"


def valid_revision(value: str) -> str:
    if not re.fullmatch(r"[0-9a-fA-F]{40}", value):
        raise ValueError("Revision must be a full 40-character commit SHA.")
    return value.lower()


def default_source_dir(revision: str) -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        base = str(Path.home() / ".local" / "share")
    return Path(base) / "BrainSSD" / "native-llama-source" / revision[:12]


def commands(source: Path, revision: str) -> dict[str, list[str]]:
    return {
        "clone": ["git", "clone", "--filter=blob:none", "--no-checkout", UPSTREAM_URL, str(source)],
        "checkout": ["git", "-C", str(source), "checkout", "--detach", revision],
        "verify": ["git", "-C", str(source), "rev-parse", "HEAD"],
        "configure": [
            "cmake", "-S", str(source), "-B", str(source / "build-brainssd-cpu"),
            "-DGGML_CUDA=OFF", "-DGGML_VULKAN=OFF", "-DGGML_HIP=OFF",
            "-DGGML_SYCL=OFF", "-DGGML_RPC=OFF", "-DLLAMA_CURL=OFF",
            "-DLLAMA_BUILD_TESTS=OFF", "-DLLAMA_BUILD_EXAMPLES=ON",
        ],
        "build": ["cmake", "--build", str(source / "build-brainssd-cpu"),
                  "--config", "Release", "-j", "4"],
    }


def invoke(command: list[str], *, capture: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        command, check=True, text=True, shell=False, timeout=1800,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )


def inspect(source: Path, revision: str) -> dict:
    if not source.exists():
        return {"status": "not_present", "verified": False}
    if not (source / ".git").exists():
        raise RuntimeError("Target exists but is not a Git checkout. Nothing overwritten.")
    if not (source / "CMakeLists.txt").is_file():
        raise RuntimeError("Incomplete checkout: CMakeLists.txt not found.")
    actual = invoke(commands(source, revision)["verify"], capture=True).stdout.strip().lower()
    if actual != revision:
        raise RuntimeError("Source revision differs from pinned SHA; build refused.")
    return {"status": "pinned_checkout", "verified": True, "commit": actual}


def fingerprint_binaries(source: Path) -> list[dict]:
    build = source / "build-brainssd-cpu" / "bin"
    result = []
    for name in ("llama-cli.exe", "llama-completion.exe"):
        for candidate in (build / "Release" / name, build / name):
            if not candidate.is_file():
                continue
            digest = hashlib.sha256()
            with candidate.open("rb") as stream:
                for data in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(data)
            result.append({"executable": name, "sha256": digest.hexdigest(),
                           "size_bytes": candidate.stat().st_size})
            break
    return result


def prepare(args: argparse.Namespace) -> dict:
    revision = valid_revision(args.revision)
    source = (args.source_dir or default_source_dir(revision)).expanduser().resolve()
    ops = commands(source, revision)
    environment = {
        "platform": platform.system(), "python": platform.python_version(),
        "git": bool(shutil.which("git")), "cmake": bool(shutil.which("cmake")),
    }
    if args.fetch or args.build:
        if os.name != "nt":
            raise RuntimeError("Source build is enabled only on Windows.")
        if not environment["git"] or not environment["cmake"]:
            raise RuntimeError("Install Git and CMake / Visual Studio C++ first.")
        if args.fetch:
            if source.exists():
                raise RuntimeError("Source directory already exists; refusing overwrite.")
            source.parent.mkdir(parents=True, exist_ok=True)
            invoke(ops["clone"])
            invoke(ops["checkout"])
    state = inspect(source, revision)
    if args.build:
        if not state["verified"]:
            raise RuntimeError("Pinned source not present; run --fetch first.")
        invoke(ops["configure"])
        invoke(ops["build"])
    return {
        "schema": 1,
        "status": "source_verified" if state["verified"] else "preflight_only",
        "upstream": UPSTREAM_URL, "revision": revision,
        "environment": environment, "checkout": state,
        "fetch_requested": bool(args.fetch), "build_requested": bool(args.build),
        "binaries": fingerprint_binaries(source) if state["verified"] else [],
        "notice": "No Qwen inference or weight-streaming executed. Existing Chat runtime remains untouched. "
                  "Pinned source can differ from the bundled llama.cpp version.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", default=DEFAULT_REVISION)
    parser.add_argument("--source-dir", type=Path, default=None)
    parser.add_argument("--fetch", action="store_true", help="Allow explicit network clone")
    parser.add_argument("--build", action="store_true", help="Compile isolated CPU-only source")
    parser.add_argument("--output", type=Path, help="Optional JSON report")
    args = parser.parse_args(argv)
    try:
        report = prepare(args)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                                   encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError,
            subprocess.TimeoutExpired) as exc:
        print("Native source preparation blocked: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
