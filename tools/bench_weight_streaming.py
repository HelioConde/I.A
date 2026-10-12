#!/usr/bin/env python3
"""Standalone benchmark of SSD->RAM weight-window paging, not LLM inference."""
from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from brain_ssd.weight_streaming_lab import MODES, PATTERNS, measure


def _fixture(path: Path, mib: int, seed: int) -> None:
    if not 1 <= mib <= 256:
        raise ValueError("Fixture limited to 1-256 MiB.")
    rng = random.Random(seed)
    with path.open("xb") as stream:
        for _ in range(mib):
            stream.write(rng.randbytes(1024 * 1024))


def _options() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="I/O-only SSD weight-window laboratory; no Qwen execution.")
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument("--source", type=Path,
                        help="Read-only existing file (GGUF accepted as opaque bytes).")
    inputs.add_argument("--fixture-mib", type=int, default=16,
                        help="Create deterministic temporary byte file (1-256 MiB).")
    parser.add_argument("--mode", choices=MODES, default="lru")
    parser.add_argument("--matrix", action="store_true",
                        help="Run each strategy in a separate subprocess.")
    parser.add_argument("--pattern", choices=PATTERNS, default="moe")
    parser.add_argument("--page-kib", type=int, default=256)
    parser.add_argument("--pages", type=int, default=64)
    parser.add_argument("--turns", type=int, default=32)
    parser.add_argument("--budget-mib", type=int, default=4)
    parser.add_argument("--offset-mib", type=int, default=0,
                        help="Aligned byte window within source; defaults to start of file.")
    parser.add_argument("--seed", type=int, default=20261012)
    parser.add_argument("--output", type=Path, help="Optional JSON result path.")
    return parser


def _run(options: argparse.Namespace, source: Path) -> dict:
    page_bytes = options.page_kib * 1024
    if (not 4 <= options.page_kib <= 16 * 1024
            or not 1 <= options.pages <= 1024
            or not 1 <= options.turns <= 1000
            or not 0 <= options.budget_mib <= 256
            or options.offset_mib < 0):
        raise ValueError("Parameters out of safe bounds.")
    if options.pattern == "dense" and options.pages * options.turns > 20000:
        raise ValueError("Dense trace exceeds 20,000 accesses.")
    if (options.offset_mib * 1024 * 1024) % page_bytes:
        raise ValueError("Offset must align with page size.")
    if (options.mode == "full_window"
            and page_bytes * options.pages > 256 * 1024 * 1024):
        raise ValueError("Full-window baseline is limited to 256 MiB.")
    result = measure(
        source, mode=options.mode, pattern=options.pattern,
        page_bytes=page_bytes, pages=options.pages,
        turns=options.turns, budget_bytes=options.budget_mib * 1024 * 1024,
        offset=options.offset_mib * 1024 * 1024, seed=options.seed,
    )
    result["input"] = {
        "kind": "supplied_read_only_file" if options.source else "temporary_fixture",
        "size_bytes": source.stat().st_size,
        "offset_bytes": options.offset_mib * 1024 * 1024,
        "note": "File path, contents and GGUF weights are not included in the report.",
    }
    return result


def _matrix(options: argparse.Namespace, source: Path) -> dict:
    # Modes run in separate child processes to avoid retaining user-space
    # memory from prior baselines. OS page cache may still carry across runs.
    with tempfile.TemporaryDirectory(prefix="brainssd-weight-cases-") as folder:
        runs = []
        for mode in MODES:
            destination = Path(folder) / (mode + ".json")
            command = [
                sys.executable, str(Path(__file__).resolve()),
                "--source", str(source), "--mode", mode,
                "--pattern", options.pattern, "--page-kib", str(options.page_kib),
                "--pages", str(options.pages), "--turns", str(options.turns),
                "--budget-mib", str(options.budget_mib),
                "--offset-mib", str(options.offset_mib),
                "--seed", str(options.seed),
                "--output", str(destination),
            ]
            result = subprocess.run(command, check=False, shell=False,
                                    capture_output=True, text=True, timeout=180)
            if result.returncode:
                raise RuntimeError(
                    "A subprocess benchmark failed for " + mode + ": " +
                    result.stderr[-500:])
            case = json.loads(destination.read_text(encoding="utf-8"))
            if options.source is None:
                case["input"]["kind"] = "temporary_fixture"
            runs.append(case)
    sinks = {case["checksum_sink"] for case in runs}
    return {
        "schema": 1,
        "type": "weight_window_io_matrix",
        "status": "consistent" if len(sinks) == 1 else "checksum_mismatch",
        "pattern": options.pattern,
        "runs": runs,
        "notice": (
            "Comparison is NOT cold-cache controlled. OS filesystem page cache "
            "persists between child processes. No model inference or tensor "
            "execution. Differences are illustrative I/O-window behaviour only."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = _options()
    args = parser.parse_args(argv)
    try:
        if args.source is None:
            with tempfile.TemporaryDirectory(prefix="brainssd-weight-fixture-") as folder:
                source = Path(folder) / "fixture.bin"
                _fixture(source, args.fixture_mib, args.seed)
                report = _matrix(args, source) if args.matrix else _run(args, source)
        else:
            source = args.source.expanduser().resolve(strict=True)
            if not source.is_file():
                raise ValueError("Source must be a regular file.")
            report = _matrix(args, source) if args.matrix else _run(args, source)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        print(json.dumps(
            {"status": report["status"], "type": report["type"],
             "output": str(args.output) if args.output else None,
             "checksum_sink": report.get("checksum_sink"),
             "modes": [r["mode"] for r in report.get("runs", [])]},
            ensure_ascii=False,
        ))
        if args.matrix and report["status"] != "consistent":
            return 2
        return 0
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
        parser.exit(2, "Weight lab error: " + str(exc) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
