#!/usr/bin/env python3
"""Measure an isolated, source-built llama.cpp process on Windows.

This runner deliberately invokes the supplied ``llama-cli.exe`` rather than
the Brain-SSD Chat runtime.  It is useful for comparing upstream load modes
while keeping that runtime untouched.  It does *not* claim that upstream mmap
is the Brain-SSD native weight loader and it cannot obtain logits from the
command-line interface.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class ProcessCounters:
    working_set_bytes: int
    peak_working_set_bytes: int
    private_bytes: int
    peak_private_bytes: int
    page_fault_count: int
    read_bytes: int
    write_bytes: int
    cpu_seconds: float


class _PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
        ("PrivateUsage", ctypes.c_size_t),
    ]


class _IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_ulonglong), ("WriteOperationCount", ctypes.c_ulonglong),
        ("OtherOperationCount", ctypes.c_ulonglong), ("ReadTransferCount", ctypes.c_ulonglong),
        ("WriteTransferCount", ctypes.c_ulonglong), ("OtherTransferCount", ctypes.c_ulonglong),
    ]


class _FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", ctypes.c_ulong), ("dwHighDateTime", ctypes.c_ulong)]


def _filetime_seconds(value: _FILETIME) -> float:
    return ((value.dwHighDateTime << 32) | value.dwLowDateTime) / 10_000_000


def windows_counters(process_handle: int) -> ProcessCounters:
    """Read process-owned Windows counters; file-cache residency is excluded."""
    if os.name != "nt":
        raise OSError("Native llama process counters are implemented for Windows only.")
    memory = _PROCESS_MEMORY_COUNTERS_EX()
    memory.cb = ctypes.sizeof(memory)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    if not psapi.GetProcessMemoryInfo(process_handle, ctypes.byref(memory), memory.cb):
        raise ctypes.WinError(ctypes.get_last_error())
    io = _IO_COUNTERS()
    if not kernel32.GetProcessIoCounters(process_handle, ctypes.byref(io)):
        raise ctypes.WinError(ctypes.get_last_error())
    creation, exit_time, kernel, user = _FILETIME(), _FILETIME(), _FILETIME(), _FILETIME()
    if not kernel32.GetProcessTimes(process_handle, ctypes.byref(creation), ctypes.byref(exit_time),
                                    ctypes.byref(kernel), ctypes.byref(user)):
        raise ctypes.WinError(ctypes.get_last_error())
    return ProcessCounters(
        working_set_bytes=int(memory.WorkingSetSize), peak_working_set_bytes=int(memory.PeakWorkingSetSize),
        private_bytes=int(memory.PrivateUsage), peak_private_bytes=int(memory.PeakPagefileUsage),
        page_fault_count=int(memory.PageFaultCount), read_bytes=int(io.ReadTransferCount),
        write_bytes=int(io.WriteTransferCount), cpu_seconds=_filetime_seconds(kernel) + _filetime_seconds(user),
    )


def native_command(cli: Path, model: Path, prompt: str, *, load_mode: str, threads: int,
                   predict: int, seed: int, context_size: int) -> list[str]:
    return [str(cli), "-m", str(model), "-c", str(context_size), "-p", prompt, "-n", str(predict), "-t", str(threads),
            "--temp", "0", "--seed", str(seed), "--load-mode", load_mode, "--no-warmup",
            "--single-turn", "--simple-io", "--no-display-prompt", "--no-show-timings", "--log-disable",
            "--reasoning-format", "none"]


def _counter_delta(first: ProcessCounters, last: ProcessCounters) -> dict[str, int | float]:
    return {
        "read_bytes": max(0, last.read_bytes - first.read_bytes),
        "write_bytes": max(0, last.write_bytes - first.write_bytes),
        "cpu_seconds": max(0.0, last.cpu_seconds - first.cpu_seconds),
        "page_faults": max(0, last.page_fault_count - first.page_fault_count),
    }


def file_sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def run_native(cli: Path, model: Path, prompt: str, *, load_mode: str, threads: int,
               predict: int, seed: int, context_size: int, sample_interval_s: float = 0.02) -> dict:
    """Run real inference and sample only process-owned counters.

    ``ReadTransferCount`` records I/O requested by this process.  It is not a
    physical SSD counter: Windows can satisfy a mapped-file fault from its file
    cache.  The CLI does not expose logits or a first-token callback, so those
    fields are intentionally recorded as unavailable rather than estimated.
    """
    command = native_command(cli, model, prompt, load_mode=load_mode, threads=threads,
                             predict=predict, seed=seed, context_size=context_size)
    started = time.perf_counter()
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, encoding="utf-8", errors="replace")
    output: list[str] = []
    reader = threading.Thread(target=lambda: output.append(process.stdout.read() if process.stdout else ""), daemon=True)
    reader.start()
    samples: list[ProcessCounters] = []
    while process.poll() is None:
        try:
            samples.append(windows_counters(process._handle))
        except OSError:
            pass
        time.sleep(sample_interval_s)
    reader.join(timeout=5)
    elapsed = time.perf_counter() - started
    if not samples:
        raise RuntimeError("No Windows process samples were captured.")
    final = windows_counters(process._handle)
    samples.append(final)
    first = samples[0]
    stdout = "".join(output)
    return {
        "status": "measured" if process.returncode == 0 else "failed",
        "return_code": process.returncode,
        "load_mode": load_mode,
        "elapsed_seconds": round(elapsed, 6),
        "peak_working_set_bytes": max(item.working_set_bytes for item in samples),
        "peak_private_bytes": max(item.private_bytes for item in samples),
        "peak_private_commit_bytes": max(item.peak_private_bytes for item in samples),
        "page_fault_count": final.page_fault_count,
        "process_counter_delta": _counter_delta(first, final),
        "sample_count": len(samples),
        "stdout_sha256": hashlib.sha256(stdout.encode("utf-8")).hexdigest(),
        "stdout_chars": len(stdout),
        "ttft_ms": None,
        "ttft_status": "unavailable: llama-cli has no first-token callback",
        "logit_integrity": "unavailable: llama-cli does not expose logits",
        "counter_scope": "process-owned; excludes system file-cache working set",
        "io_scope": "logical process I/O; not proof of physical SSD reads",
    }


def build_report(conventional: dict, upstream_comparison: dict | None, *, cli: Path, model: Path,
                 prompt: str, seed: int, threads: int, predict: int, context_size: int) -> dict:
    return {
        "schema": 1,
        "type": "native_llama_windows_comparison",
        "runtime": {"cli": str(cli), "cli_sha256": file_sha256(cli)},
        "model": {"path": str(model), "sha256": file_sha256(model)},
        "conditions": {"prompt_chars": len(prompt), "seed": seed, "threads": threads, "predict": predict,
                       "context_size": context_size,
                       "temperature": 0, "cache_state": "unknown: Windows file cache uncontrolled"},
        "conventional": conventional,
        "upstream_load_mode_comparison": upstream_comparison or {"status": "not_requested"},
        "brain_ssd_experimental": {
            "status": "not_implemented",
            "reason": "No Brain-SSD native loader was invoked; upstream load modes are measured separately only.",
        },
        "integrity": {
            "upstream_token_output_equal": None if upstream_comparison is None else
                conventional.get("stdout_sha256") == upstream_comparison.get("stdout_sha256"),
            "brain_ssd_tokens": "not measured: no Brain-SSD native loader invoked",
            "logits": "unavailable from llama-cli",
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Measure a source-built CPU llama-cli on Windows.")
    parser.add_argument("--cli", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--prompt", default="Quanto e 19 mais 23? Responda somente com o resultado.")
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--predict", type=int, default=16)
    parser.add_argument("--context-size", type=int, default=512)
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--conventional-load-mode", choices=("mmap", "none"), default="mmap")
    parser.add_argument("--comparison-load-mode", choices=("mmap", "none"), default=None)
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "weight_lab" / "native-llama-baseline.json")
    args = parser.parse_args(argv)
    if os.name != "nt":
        parser.exit(2, "This native process benchmark is Windows-only.\n")
    if not args.cli.is_file() or not args.model.is_file():
        parser.exit(2, "--cli and --model must be existing files.\n")
    conventional = run_native(args.cli, args.model, args.prompt, load_mode=args.conventional_load_mode,
                              threads=args.threads, predict=args.predict, seed=args.seed,
                              context_size=args.context_size)
    comparison = None
    if args.comparison_load_mode:
        comparison = run_native(args.cli, args.model, args.prompt, load_mode=args.comparison_load_mode,
                                threads=args.threads, predict=args.predict, seed=args.seed,
                                context_size=args.context_size)
    report = build_report(conventional, comparison, cli=args.cli, model=args.model, prompt=args.prompt,
                          seed=args.seed, threads=args.threads, predict=args.predict, context_size=args.context_size)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": conventional["status"], "output": str(args.output),
                      "comparison": comparison["status"] if comparison else "not_requested"}, ensure_ascii=False))
    return 0 if conventional["status"] == "measured" and (comparison is None or comparison["status"] == "measured") else 1


if __name__ == "__main__":
    raise SystemExit(main())
