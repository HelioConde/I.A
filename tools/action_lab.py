#!/usr/bin/env python3
"""Action Lab: reproducible, model-free Brain-SSD regression runner.

Only repository-defined test modules run. No GGUF, personal SQLite, or
download is needed; real Qwen inference lives in an opt-in Windows CI job.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
SMOKE = (
    "test_chat_windows.py",
    "test_code_studio.py",
    "test_game_coding_trial.py",
    "test_game_agent_v2.py",
    "test_game_coder_model_install.py",
    "test_chat_local_actions.py",
    "test_memory_safety.py",
    "test_chat_completion_quality.py",
    "test_chat_stream.py",
    "test_storage.py",
    "test_router_gating.py",
)
EXTENDED = SMOKE + (
    "test_chat_history.py",
    "test_chat_episodic.py",
    "test_episodic_integrity.py",
    "test_chat_web_search.py",
    "test_chat_doctor.py",
    "test_chat_performance.py",
    "test_semantic_bridge.py",
    "test_cache_policy.py",
    "test_hybrid.py",
)
SUITES = {"smoke": SMOKE, "extended": EXTENDED}
WINDOWS_ONLY = ("test_chat_runtime.py",)

RAN_PATTERN = re.compile(r"Ran\s+(\d+)\s+tests?\s+in\s+", re.IGNORECASE)


def execute(module: str, *, timeout: int) -> dict[str, object]:
    """Isolate each module so a stuck case cannot block the full job."""
    command = [
        sys.executable, "-m", "unittest", "discover", "-s", "tests",
        "-p", module, "-v",
    ]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "src")
    environment["PYTHONUNBUFFERED"] = "1"
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command, cwd=ROOT, env=environment, capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=timeout,
            check=False,
        )
        combined = completed.stdout + "\n" + completed.stderr
        count = RAN_PATTERN.search(combined)
        passed = completed.returncode == 0 and count is not None and int(count.group(1)) > 0
        outcome = {
            "module": module,
            "status": "PASS" if passed else "FAIL",
            "tests": int(count.group(1)) if count else 0,
            "duration_s": round(time.monotonic() - started, 3),
            "exit_code": completed.returncode,
        }
        if not passed:
            # CI uses synthetic tests only. Print a bounded excerpt for diagnosis.
            tail = "\n".join(combined.splitlines()[-35:])[-6000:]
            print("Diagnostic excerpt for " + module + ":\n" + tail, flush=True)
        return outcome
    except subprocess.TimeoutExpired:
        return {
            "module": module, "status": "TIMEOUT", "tests": 0,
            "duration_s": round(time.monotonic() - started, 3),
            "exit_code": None,
        }


def write_summary(report: dict[str, object]) -> None:
    location = os.environ.get("GITHUB_STEP_SUMMARY")
    if not location:
        return
    lines = [
        "## Luna Action Lab — " + str(report["status"]),
        "",
        "Suite: **" + str(report["suite"]) + "** · Simulated/model-free tests; no real Qwen or SSD RAM claim.",
        "",
        "| Test module | Result | Tests | Seconds |",
        "|---|---|---:|---:|",
    ]
    for item in report["results"]:
        lines.append(
            "| " + str(item["module"]) + " | " + str(item["status"]) +
            " | " + str(item["tests"]) + " | " + str(item["duration_s"]) + " |"
        )
    lines.append("")
    lines.append("Total: **" + str(report["test_count"]) + "** tests; " +
                 str(report["failures"]) + " failing modules.")
    with Path(location).open("a", encoding="utf-8") as output:
        output.write("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Brain-SSD CI regression laboratory")
    parser.add_argument("--suite", choices=tuple(SUITES), default="smoke")
    parser.add_argument("--report", type=Path, default=Path("results/action_lab/report.json"))
    parser.add_argument("--timeout", type=int, default=180, help="Seconds per test module")
    args = parser.parse_args()
    if not 5 <= args.timeout <= 600:
        parser.error("--timeout must be between 5 and 600 seconds")
    started = time.monotonic()
    results = []
    modules = SUITES[args.suite] + (WINDOWS_ONLY if os.name == "nt" else ())
    for module in modules:
        print("Running " + module + " ...", flush=True)
        item = execute(module, timeout=args.timeout)
        results.append(item)
        print("Result " + module + ": " + str(item["status"]) +
              " (" + str(item["tests"]) + " tests)", flush=True)
    failures = sum(item["status"] != "PASS" for item in results)
    report = {
        "schema_version": 1,
        "validation_track": "GITHUB_ACTIONS_SYNTHETIC",
        "inference_verified": False,
        "ssd_physical_ram_savings_verified": False,
        "suite": args.suite,
        "status": "PASS" if failures == 0 else "FAIL",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version.split()[0],
        "elapsed_s": round(time.monotonic() - started, 3),
        "test_count": sum(int(item["tests"]) for item in results),
        "failures": failures,
        "results": results,
    }
    target = args.report if args.report.is_absolute() else ROOT / args.report
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_summary(report)
    print("Report: " + str(target.relative_to(ROOT) if target.is_relative_to(ROOT) else target))
    print("LAB_STATUS=" + str(report["status"]), flush=True)
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
