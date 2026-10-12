#!/usr/bin/env python3
"""Build (opt-in) and compare direct llama.cpp C API logits + tokens on Windows.

Isolated from the installed Brain-SSD chat and original llama.cpp binaries.
Not an SSD streaming loader. No model or source files are modified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from prepare_native_llama_windows import DEFAULT_REVISION, default_source_dir, inspect, valid_revision
from bench_native_llama_windows import windows_counters

PROBE = ROOT / "tools" / "native_llama_probe"
MODES = ("mmap", "none")


def build_commands(source: Path, output: Path) -> tuple[list[str], list[str]]:
    return (
        ["cmake", "-S", str(PROBE), "-B", str(output),
         "-DLLAMA_SOURCE_DIR=" + str(source)],
        ["cmake", "--build", str(output), "--config", "Release",
         "--target", "brainssd-native-logits", "-j", "4"],
    )


def binary_path(output: Path) -> Path:
    for item in (output / "bin" / "Release" / "brainssd-native-logits.exe",
                 output / "bin" / "brainssd-native-logits.exe"):
        if item.is_file():
            return item
    raise FileNotFoundError(
        "Native logits executable missing. Use --build from VS Developer Prompt.")


def probe_command(binary: Path, model: Path, *, mode: str, prompt: str,
                  context: int, threads: int, predict: int, lazy_mode: str = "off") -> list[str]:
    if mode not in MODES or lazy_mode not in ("off", "auto", "on") or not 32 <= context <= 8192 or not 1 <= threads <= 32 \
            or not 1 <= predict <= 128 or not 0 < len(prompt.encode("utf-8")) <= 2048:
        raise ValueError("Invalid isolated probe parameters.")
    return [str(binary), "--model", str(model), "--load-mode", mode,
            "--lazy-mode", lazy_mode,
            "--prompt", prompt, "--context", str(context),
            "--threads", str(threads), "--predict", str(predict)]


def compare(first: dict, second: dict, *, atol: float = 1e-5) -> dict[str, Any]:
    """Same model/build/params only. Compare first-step top8 and greedy IDs."""
    if (first.get("status") != "measured" or second.get("status") != "measured"
            or first.get("type") != "native_llama_logits_probe"
            or second.get("type") != "native_llama_logits_probe"):
        raise ValueError("Only real native probe measurements can be compared.")
    settings = ("context", "threads", "predict_limit", "sampling", "vocab_count", "lazy_mode")
    if any(first.get(k) != second.get(k) for k in settings):
        raise ValueError("Probe settings differ; comparisons prohibited.")
    a, b = first.get("prompt_top8_logits"), second.get("prompt_top8_logits")
    if not isinstance(a, list) or not isinstance(b, list) or len(a) != len(b) or not a:
        raise ValueError("Top logits are absent.")
    top_tokens_equal = True
    max_abs_difference = 0.0
    for lhs, rhs in zip(a, b):
        x, y = float(lhs["value"]), float(rhs["value"])
        if not math.isfinite(x) or not math.isfinite(y):
            raise ValueError("Non-finite logits cannot be compared.")
        top_tokens_equal &= lhs["token"] == rhs["token"]
        max_abs_difference = max(max_abs_difference, abs(x - y))
    tokens_equal = first["tokens"] == second["tokens"]
    exact_logits_checksum = (
        first.get("prompt_logits_fnv64") == second.get("prompt_logits_fnv64")
    )
    top8_close = top_tokens_equal and max_abs_difference <= atol
    return {
        "status": "consistent" if tokens_equal and top8_close else "diverged",
        "greedy_token_ids_equal": tokens_equal,
        "top8_token_indices_equal": top_tokens_equal,
        "top8_logits_within_absolute_tolerance": top8_close,
        "max_top8_abs_difference": max_abs_difference,
        "first_prompt_logits_bitwise_checksum_equal": exact_logits_checksum,
        "scope": (
            "Checks greedy token IDs and first-step top8 logits, and hashes the "
            "full first-step logit float32 vector. Does not measure all later-step "
            "logits; cannot by itself prove mathematical equivalence of all outputs."
        ),
    }


def run_one(binary: Path, model: Path, *, mode: str,
            prompt: str, context: int, threads: int, predict: int, lazy_mode: str) -> dict:
    cmd = probe_command(binary, model, mode=mode, prompt=prompt,
                        context=context, threads=threads, predict=predict, lazy_mode=lazy_mode)
    started = time.monotonic()
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                          text=True, encoding="utf-8", errors="replace") as process:
        samples = []
        while process.poll() is None:
            try:
                samples.append(windows_counters(process._handle))
            except OSError:
                pass
            if time.monotonic() - started > 180:
                process.kill()
                process.wait()
                raise TimeoutError("Native inference exceeded 180 seconds.")
            time.sleep(.02)
        output, _ = process.communicate(timeout=10)
        if process.returncode != 0:
            raise RuntimeError("Native probe failed; ensure compiled source and GGUF match.")
    if not samples:
        raise RuntimeError("No native-process Windows counters were available.")
    try:
        report = json.loads(output.strip())
    except json.JSONDecodeError:
        raise RuntimeError("Native probe returned invalid JSON.") from None
    if report.get("type") != "native_llama_logits_probe" or report.get("status") != "measured":
        raise RuntimeError("Native probe reported no valid inference.")
    return {
        "native": report,
        "process": {
            "peak_working_set_bytes": max(
                max(s.working_set_bytes, s.peak_working_set_bytes) for s in samples),
            "peak_private_bytes_observed": max(s.private_bytes for s in samples),
            "peak_private_commit_bytes": max(s.peak_private_bytes for s in samples),
            "read_bytes_logical_max": max(s.read_bytes for s in samples),
            "samples": len(samples),
        },
        "wall_seconds": round(time.monotonic() - started, 6),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", default=DEFAULT_REVISION)
    parser.add_argument("--source-dir", type=Path, default=None)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--build", action="store_true",
                        help="Explicitly compile the isolated native probe (no network download)")
    parser.add_argument("--mode", choices=MODES + ("both",), default="both")
    parser.add_argument("--prompt", default="Quanto e 19 mais 23? Responda somente com o resultado.")
    parser.add_argument("--context", type=int, default=512)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--predict", type=int, default=16)
    parser.add_argument("--lazy-mode", choices=("off", "auto", "on"), default="off",
                        help="Upstream tensor lazy mode; this is not a Brain-SSD loader.")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "results" / "weight_lab" / "native-logits-comparison.json")
    args = parser.parse_args(argv)
    try:
        if os.name != "nt":
            raise OSError("Use Windows with Visual Studio C++ and CMake.")
        revision = valid_revision(args.revision)
        source = (args.source_dir or default_source_dir(revision)).resolve()
        if not inspect(source, revision)["verified"]:
            raise ValueError("Pinned llama.cpp source is missing; use prepare --fetch first.")
        model = args.model.expanduser().resolve(strict=True)
        if not model.is_file() or model.suffix.casefold() != ".gguf":
            raise ValueError("Provide the existing GGUF model; it will not be modified.")
        output_dir = source / "build-brainssd-logits"
        if args.build:
            import shutil
            if shutil.which("cmake") is None:
                raise RuntimeError("CMake not installed.")
            for command in build_commands(source, output_dir):
                subprocess.run(command, check=True, shell=False, timeout=1800)
        binary = binary_path(output_dir)
        # Hash only the executable and GGUF used by both modes; never include raw weights.
        with model.open("rb") as f:
            model_sha = hashlib.file_digest(f, "sha256").hexdigest()
        with binary.open("rb") as f:
            binary_sha = hashlib.file_digest(f, "sha256").hexdigest()
        modes = MODES if args.mode == "both" else (args.mode,)
        runs = {
            mode: run_one(binary, model, mode=mode,
                          prompt=args.prompt, context=args.context,
                          threads=args.threads, predict=args.predict,
                          lazy_mode=args.lazy_mode)
            for mode in modes
        }
        comparison = (
            compare(runs["mmap"]["native"], runs["none"]["native"])
            if len(runs) == 2 else None
        )
        report = {
            "schema": 1, "type": "native_llama_logits_comparison",
            "revision": revision, "model_sha256": model_sha,
            "binary_sha256": binary_sha, "conditions": {
                "context": args.context, "threads": args.threads,
                "predict": args.predict, "sampling": "greedy",
                "lazy_mode": args.lazy_mode,
                "cache_state": "unknown (OS page cache not reset)",
            },
            "runs": runs, "comparison": comparison,
            "notice": (
                "This uses UNMODIFIED upstream llama.cpp source. It measures "
                "native logits and first-token latency. It DOES NOT implement "
                "Brain-SSD weight streaming or demonstrate additional RAM savings."
            ),
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                               encoding="utf-8")
        print(json.dumps({"output": str(args.output),
                          "comparison": comparison}, ensure_ascii=False))
        return 0 if comparison is None or comparison["status"] == "consistent" else 3
    except (ValueError, OSError, RuntimeError, subprocess.CalledProcessError,
            subprocess.TimeoutExpired, TimeoutError) as exc:
        print("Native logits benchmark failed: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
