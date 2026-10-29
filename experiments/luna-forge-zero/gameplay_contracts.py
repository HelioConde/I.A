"""Original JS gameplay contracts for the experimental Luna MiniCoder.

Ordinary mode parses generated code ONLY (node --check). Behavioral execution
is opt-in and only occurs inside an isolated, offline Docker container; never
run untrusted model output on the host. No game archives or commercial data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile


TASKS = (
    {
        "id": "movement_dt",
        "name": "movePlayer",
        "brief": "Return x + direction * speed * dt. All inputs are numbers.",
        "cases": [([10, 1, 100, 0.5], 60), ([10, -1, 100, 0.25], -15), ([10, 0, 100, 2], 10)],
    },
    {
        "id": "grounded_jump",
        "name": "jumpVelocity",
        "brief": "Return -power only if grounded AND pressed, else return vy.",
        "cases": [([3, True, True, 12], -12), ([3, False, True, 12], 3), ([3, True, False, 12], 3)],
    },
    {
        "id": "aabb_collision",
        "name": "rectsOverlap",
        "brief": "Return true for two overlapping {x,y,w,h} rectangles; touching edges is false.",
        "cases": [
            ([{"x": 0, "y": 0, "w": 10, "h": 10}, {"x": 5, "y": 5, "w": 10, "h": 10}], True),
            ([{"x": 0, "y": 0, "w": 10, "h": 10}, {"x": 10, "y": 0, "w": 3, "h": 3}], False),
            ([{"x": 0, "y": 0, "w": 10, "h": 10}, {"x": -20, "y": 0, "w": 3, "h": 3}], False),
        ],
    },
    {
        "id": "damage_clamp",
        "name": "applyDamage",
        "brief": "Return remaining HP after damage, clamped to the range 0..maxHp.",
        "cases": [([75, 20, 100], 55), ([12, 99, 100], 0), ([120, 0, 100], 100)],
    },
    {
        "id": "enemy_patrol",
        "name": "patrolStep",
        "brief": "Return {x,direction}. Move x by direction*speed*dt, clamp to minX..maxX, and reverse direction upon reaching a bound.",
        "cases": [
            ([9, 1, 4, 1, 0, 10], {"x": 10, "direction": -1}),
            ([1, -1, 4, 1, 0, 10], {"x": 0, "direction": 1}),
            ([5, 1, 3, 1, 0, 10], {"x": 8, "direction": 1}),
        ],
    },
)

# The candidate is evaluated by Node's VM INSIDE Docker only. VM is NOT a
# security boundary; Docker isolation, no network, and resource limits matter.
RUNNER = r'''"use strict";
const fs = require("node:fs");
const vm = require("node:vm");
const spec = JSON.parse(fs.readFileSync("/work/spec.json", "utf8"));
const candidate = fs.readFileSync("/work/candidate.js", "utf8");
if (candidate.length > 16384 || !/^[A-Za-z_$][A-Za-z0-9_$]*$/.test(spec.name)) process.exit(2);
const failed = [];
for (let i = 0; i < spec.cases.length; i++) {
  const [args, expected] = spec.cases[i];
  try {
    const sandbox = Object.create(null);
    const expression = '"use strict";\n' + candidate + '\n;globalThis.__result = ' + spec.name + '.apply(null, ' + JSON.stringify(args) + ');';
    vm.runInNewContext(expression, sandbox, {timeout: 150});
    const actual = JSON.parse(JSON.stringify(sandbox.__result));
    if (JSON.stringify(actual) !== JSON.stringify(expected)) failed.push(i);
  } catch (_) { failed.push(i); }
}
process.stdout.write(JSON.stringify({passed: spec.cases.length - failed.length, total: spec.cases.length, failed_case_ids: failed}));
'''


def prompt_for(task: dict) -> str:
    return f"// Original game task: {task['brief']}\nfunction {task['name']}("


def candidate_from_output(task: dict, raw_output: str) -> str:
    prompt = prompt_for(task)
    if not isinstance(raw_output, str) or not raw_output.startswith(prompt):
        raise ValueError("Model output did not preserve the original prompt")
    continuation = raw_output[len(prompt):].split("\nFIM", 1)[0].split("\nEND\n", 1)[0]
    return "function " + task["name"] + "(" + continuation


def syntax_check(candidate: str) -> str:
    """Node --check parses candidate, but never evaluates it."""
    if not candidate.strip() or len(candidate.encode("utf-8")) > 16384:
        return "FAIL_LENGTH"
    node = shutil.which("node")
    if node is None:
        return "UNAVAILABLE_NODE"
    with tempfile.TemporaryDirectory(prefix="luna_game_syntax_") as directory:
        path = Path(directory) / "candidate.js"
        path.write_text(candidate, encoding="utf-8")
        try:
            result = subprocess.run([node, "--check", str(path)], capture_output=True,
                                    check=False, text=True, timeout=5)
        except subprocess.TimeoutExpired:
            return "TIMEOUT"
    return "PASS" if result.returncode == 0 else "FAIL"


def docker_behavior(candidate: str, task: dict) -> dict:
    """Execute candidate only in a preinstalled image, offline and read-only."""
    if len(candidate.encode("utf-8")) > 16384:
        return {"status": "REJECTED_LENGTH"}
    docker = shutil.which("docker")
    if docker is None:
        return {"status": "UNAVAILABLE_DOCKER"}
    with tempfile.TemporaryDirectory(prefix="luna_game_sandbox_") as directory:
        root = Path(directory).resolve()
        (root / "candidate.js").write_text(candidate, encoding="utf-8")
        (root / "runner.js").write_text(RUNNER, encoding="utf-8")
        (root / "spec.json").write_text(
            json.dumps({"name": task["name"], "cases": task["cases"]}), encoding="utf-8")
        command = [
            docker, "run", "--rm", "--pull=never", "--network=none", "--read-only",
            "--cap-drop=ALL", "--security-opt=no-new-privileges",
            "--pids-limit=64", "--memory=128m", "--cpus=1", "--user=65534:65534",
            "--tmpfs=/tmp:rw,nosuid,noexec,size=16m",
            "--mount", f"type=bind,source={root},target=/work,readonly",
            "--workdir=/work", "--entrypoint=node", "node:22-alpine", "/work/runner.js",
        ]
        try:
            response = subprocess.run(command, capture_output=True, check=False,
                                      text=True, timeout=20)
        except subprocess.TimeoutExpired:
            return {"status": "TIMEOUT"}
        if response.returncode != 0:
            return {"status": "UNAVAILABLE_OR_FAILED_CONTAINER"}
        try:
            result = json.loads(response.stdout)
            if (not isinstance(result.get("passed"), int) or
                    not isinstance(result.get("total"), int) or
                    result["total"] != len(task["cases"]) or
                    not 0 <= result["passed"] <= result["total"]):
                raise ValueError("Invalid sandbox results")
            return {"status": "PASS" if result["passed"] == result["total"] else "FAIL",
                    "passed": result["passed"], "total": result["total"]}
        except (ValueError, KeyError, TypeError):
            return {"status": "INVALID_SANDBOX_RESULT"}


def evaluate(checkpoint: Path, *, chars: int = 360, behavior: bool = False) -> dict:
    """Evaluate own MiniCoder checkpoint. No training, no imported game code."""
    if not 1 <= chars <= 960:
        raise ValueError("chars must be 1..960")
    checkpoint = Path(checkpoint)
    report = json.loads((checkpoint / "report.json").read_text(encoding="utf-8"))
    weights = checkpoint / "weights.pt"
    if weights.stat().st_size > 64 * 1024 * 1024:
        raise ValueError("Checkpoint exceeds maximum size")
    h = hashlib.sha256()
    with weights.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            h.update(chunk)
    if h.hexdigest() != report.get("weights_sha256"):
        raise ValueError("Checkpoint SHA256 mismatch")
    from luna_codegen_model import Config, LunaMiniCoder
    import torch
    model = LunaMiniCoder(Config(**report["config"]))
    model.load_state_dict(torch.load(weights, map_location="cpu", weights_only=True, mmap=True), assign=True)
    model.eval()
    scores = []
    for task in TASKS:
        prompt = prompt_for(task)
        raw = model.generate(prompt, chars=chars, temperature=0, deterministic=True)
        code = candidate_from_output(task, raw)
        syntax = syntax_check(code)
        outcome = docker_behavior(code, task) if behavior and syntax == "PASS" else {
            "status": "SKIPPED_SYNTAX_FAILURE" if behavior else "NOT_TESTED"}
        scores.append({"id": task["id"], "generated_sha256": hashlib.sha256(code.encode()).hexdigest(),
                       "generated_characters": len(code), "syntax": syntax, "behavior": outcome})
    return {"schema": "luna-gameplay-contracts-v1", "model": "MiniCoder scratch",
            "checkpoint_sha256": h.hexdigest(), "deterministic": True,
            "generated_code_executed_on_host": False,
            "behavior_enabled": behavior,
            "behavior_passed": sum(row["behavior"]["status"] == "PASS" for row in scores),
            "syntax_passed": sum(row["syntax"] == "PASS" for row in scores),
            "tasks": len(TASKS), "results": scores,
            "warning": "Only generated candidates count; authored fixture tests do not prove model skill."}


def main() -> None:
    p = argparse.ArgumentParser(description="Benchmark original JS game mechanics for Luna MiniCoder")
    p.add_argument("--checkpoint", type=Path, help="Local authorized MiniCoder checkpoint folder")
    p.add_argument("--chars", type=int, default=360)
    p.add_argument("--behavior", action="store_true", help="Opt-in: execute syntax-valid candidates in offline Docker")
    p.add_argument("--list-tasks", action="store_true", help="Only show challenge descriptions, no model or code execution")
    p.add_argument("--out", type=Path, help="Write a NEW JSON summary (no generated source included)")
    args = p.parse_args()
    if args.list_tasks:
        data = [{"id": x["id"], "brief": x["brief"], "test_cases": len(x["cases"])} for x in TASKS]
    else:
        if args.checkpoint is None:
            p.error("--checkpoint required unless --list-tasks is used")
        data = evaluate(args.checkpoint, chars=args.chars, behavior=args.behavior)
    text = json.dumps(data, indent=2, ensure_ascii=False)
    if args.out:
        with args.out.open("x", encoding="utf-8") as file:
            file.write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
