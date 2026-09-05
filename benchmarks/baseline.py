#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brain_ssd.backend import GenerationRequest, LlamaCppBackend
from brain_ssd.hardware import collect_hardware
from brain_ssd.telemetry import run_measured

DEFAULT_PROMPT = "Responda somente com a palavra AZUL. Qual é a cor do céu em um dia limpo? /no_think"


def evict_model_pages(path: Path) -> None:
    """Request eviction of this model only; never drops the host's global page cache."""
    if not hasattr(os, "posix_fadvise") or not hasattr(os, "POSIX_FADV_DONTNEED"):
        raise RuntimeError("POSIX_FADV_DONTNEED is unavailable on this platform")
    with path.open("rb") as model_file:
        os.posix_fadvise(model_file.fileno(), 0, 0, os.POSIX_FADV_DONTNEED)


def main() -> int:
    parser = argparse.ArgumentParser(description="Brain-SSD Phase 1 CPU-only baseline")
    parser.add_argument("--llama-cli", required=True, type=Path, help="path to llama-completion/llama-cli")
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--max-tokens", type=int, default=24)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--ctx-size", type=int, default=512)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--cache-mode", choices=("current", "cold"), default="current")
    parser.add_argument("--expected-substring", default="AZUL")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.repeat < 1:
        parser.error("--repeat must be >= 1")

    backend = LlamaCppBackend(args.llama_cli, args.model, args.threads, args.ctx_size)
    request = GenerationRequest(args.prompt, args.max_tokens, 0.0)
    runs = []
    for _ in range(args.repeat):
        if args.cache_mode == "cold":
            evict_model_pages(args.model)
        run = run_measured(backend.command(request))
        run["quality"] = {
            "check": "expected substring",
            "expected": args.expected_substring,
            "passed": args.expected_substring.casefold() in run["stdout"].casefold(),
        }
        runs.append(run)
    digest = hashlib.sha256()
    with args.model.open("rb") as model_file:
        for chunk in iter(lambda: model_file.read(1024 * 1024), b""):
            digest.update(chunk)
    model_hash = digest.hexdigest()
    payload = {
        "schema_version": 1,
        "experiment": "phase1-cpu-only-proof-of-life",
        "hypothesis": "A sub-1B GGUF core completes local CPU-only generation within the 4-5 GB RSS target.",
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "backend": backend.name,
        "model": {"path": str(args.model), "size_bytes": args.model.stat().st_size, "sha256": model_hash},
        "request": {"prompt": args.prompt, "max_tokens": args.max_tokens, "temperature": 0.0},
        "cache_mode": args.cache_mode,
        "hardware": collect_hardware(),
        "runs": runs,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": str(args.output), "return_codes": [run["return_code"] for run in runs]}))
    return 0 if all(run["return_code"] == 0 and run["quality"]["passed"] for run in runs) else 1


if __name__ == "__main__":
    raise SystemExit(main())
