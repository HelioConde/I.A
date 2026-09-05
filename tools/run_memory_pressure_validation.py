#!/usr/bin/env python3
"""Portable Phase 4C runner for Docker-limited Codespaces or native Debian hosts."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import random
import shutil
import subprocess
import time
from pathlib import Path

sys_path = str(Path(__file__).resolve().parents[1] / "src")
if sys_path not in __import__("sys").path: __import__("sys").path.insert(0, sys_path)
from brain_ssd.resource_pressure import classify_container_result


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results/phase4c"
IMAGE = "python:3.12-slim"
PROFILES = {
    "PRESSURE_512": {"memory": "512m", "memory_bytes": 512 * 1024**2, "cpus": "2"},
    "PRESSURE_1024": {"memory": "1g", "memory_bytes": 1024**3, "cpus": "2"},
    "PRESSURE_2048": {"memory": "2g", "memory_bytes": 2 * 1024**3, "cpus": "2"},
    "LOW_4GB": {"memory": "4g", "memory_bytes": 4 * 1024**3, "cpus": "2", "physical_only": True},
    "TARGET_8GB": {"memory": "8g", "memory_bytes": 8 * 1024**3, "cpus": "4", "physical_only": True},
}
WORKLOADS = ("realistic_mix", "stable_topic", "long_gap_return", "a_b_a", "random_topics", "zipf_topic_popularity")
STRATEGIES = ("kernel_only", "cognitive_shadow", "lru_cold", "cognitive_cold")


def command_output(command):
    completed = subprocess.run(command, capture_output=True, text=True)
    return {"command": command, "returncode": completed.returncode,
            "stdout": completed.stdout.strip(), "stderr": completed.stderr.strip()}


def audit() -> dict:
    return {"platform": platform.platform(), "machine": platform.machine(), "python": platform.python_version(),
            "cpu_count": os.cpu_count(), "docker": shutil.which("docker"), "podman": shutil.which("podman"),
            "filesystem": command_output(["stat", "-f", "-c", "%T", str(ROOT)]),
            "block_devices": command_output(["lsblk", "-J", "-o", "NAME,TYPE,SIZE,ROTA,FSTYPE,MOUNTPOINTS"]),
            "cgroup": Path("/proc/self/cgroup").read_text().strip(),
            "environment_type": "PHYSICAL_NATIVE" if os.environ.get("BRAIN_SSD_PHYSICAL_NATIVE") == "1" else "CODESPACE_UNCONSTRAINED"}


def docker_base(name: str, profile: dict) -> list[str]:
    return ["docker", "run", "--name", name, "--memory", profile["memory"], "--memory-swap", profile["memory"],
            "--cpus", profile["cpus"], "--network", "none", "--security-opt", "no-new-privileges",
            "--mount", f"type=bind,src={ROOT},dst=/brain,readonly", "-e", "PYTHONPATH=/brain/src", IMAGE]


def run_container(name: str, profile: dict, inner: list[str]) -> dict:
    subprocess.run(["docker", "rm", "-f", name], capture_output=True)
    started = time.time(); run = subprocess.run(docker_base(name, profile) + inner, capture_output=True, text=True)
    inspection = subprocess.run(["docker", "inspect", name], capture_output=True, text=True)
    state = {}
    if inspection.returncode == 0:
        state = json.loads(inspection.stdout)[0].get("State", {})
    subprocess.run(["docker", "rm", "-f", name], capture_output=True)
    payload = None
    if run.stdout.strip():
        try: payload = json.loads(run.stdout.strip().splitlines()[-1])
        except json.JSONDecodeError: pass
    return {"returncode": run.returncode, "stdout": run.stdout, "stderr": run.stderr,
            "payload": payload, "container_state": state, "oom_killed": bool(state.get("OOMKilled")),
            "wall_seconds": time.time() - started}


def checksums(directory: Path) -> dict[str, str]:
    return {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(directory.glob("*.json"))}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe-only", action="store_true")
    parser.add_argument("--profiles", nargs="*", default=["PRESSURE_512", "PRESSURE_1024", "PRESSURE_2048"])
    parser.add_argument("--repetitions", type=int, default=2)
    parser.add_argument("--strategies", nargs="*", default=list(STRATEGIES))
    parser.add_argument("--workloads", nargs="*", default=list(WORKLOADS))
    parser.add_argument("--include-pageout-negative", action="store_true")
    parser.add_argument("--physical-profile", action="store_true", help="allow LOW_4GB/TARGET_8GB on an explicitly native host")
    args = parser.parse_args(); RESULTS.mkdir(parents=True, exist_ok=True)
    environment = audit(); (RESULTS / "environment.json").write_text(json.dumps(environment, indent=2, sort_keys=True) + "\n")
    if not environment["docker"]:
        result = {"status": "NO_HARD_LIMIT_RUNTIME", "environment": environment}
        (RESULTS / "runner-status.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n"); return
    probe_profile = PROFILES["PRESSURE_512"]
    probe = run_container("brain-ssd-phase4c-probe", probe_profile,
                          ["python", "/brain/benchmarks/phase4c_charge_probe.py"])
    proof = probe.get("payload") or {}
    hard = proof.get("before", {}).get("memory_max") == probe_profile["memory_bytes"]
    file_delta = proof.get("stat_delta_during", {}).get("file", 0)
    charge = file_delta >= 128 * 1024**2
    proof_result = {"container": probe, "hard_limit_requested": probe_profile["memory_bytes"],
                    "hard_limit_valid": hard, "page_cache_charge_valid": charge,
                    "classification": "HARD_LIMIT" if hard and charge else "UNCONTROLLED"}
    (RESULTS / "hard-limit-proof.json").write_text(json.dumps(proof_result, indent=2, sort_keys=True) + "\n")
    if args.probe_only or not (hard and charge):
        status = {"status": "PROBE_COMPLETE" if hard and charge else "INVALID_PRESSURE_ENVIRONMENT",
                  "checksums": checksums(RESULTS)}
        (RESULTS / "runner-status.json").write_text(json.dumps(status, indent=2, sort_keys=True) + "\n"); return
    profiles = []
    for name in args.profiles:
        profile = PROFILES[name]
        if profile.get("physical_only") and not args.physical_profile:
            continue
        profiles.append((name, profile))
    configs = []
    for repetition in range(args.repetitions):
        for profile_name, profile in profiles:
            for workload in args.workloads:
                for strategy in args.strategies:
                    configs.append({"profile": profile_name, "profile_data": profile, "workload": workload,
                                    "strategy": strategy, "repetition": repetition})
    # PAGEOUT remains an explicitly requested single negative control, never a normal strategy.
    if args.include_pageout_negative:
        configs.append({"profile": "PRESSURE_512", "profile_data": PROFILES["PRESSURE_512"],
                        "workload": "realistic_mix", "strategy": "pageout_negative", "repetition": 0})
    rng = random.Random(20260807); rng.shuffle(configs)
    runs = []
    for index, config in enumerate(configs):
        trace_split = "development"; turns = 1000
        trace = f"/brain/results/phase4a/traces/{trace_split}/{config['workload']}-{turns}.jsonl.gz"
        inner = ["python", "/brain/benchmarks/phase4c_worker.py", "--trace", trace,
                 "--workload", config["workload"], "--strategy", config["strategy"], "--budget-mib", "64"]
        name = f"brain-ssd-4c-{index}"
        run = run_container(name, config["profile_data"], inner)
        run["classification"] = classify_container_result(run["returncode"], run["oom_killed"], run["payload"])
        runs.append({**{key: value for key, value in config.items() if key != "profile_data"},
                     "order_index": index, "result": run})
        print(f"completed {index + 1}/{len(configs)}", flush=True)
    output_name = "pressure-aware-runs.json" if args.strategies == ["cognitive_pressure_aware"] else "runs.json"
    (RESULTS / output_name).write_text(json.dumps(runs, indent=2, sort_keys=True) + "\n")
    status = {"status": "MATRIX_COMPLETE", "run_count": len(runs), "order_seed": 20260807,
              "checksums": checksums(RESULTS)}
    (RESULTS / "runner-status.json").write_text(json.dumps(status, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__": main()
