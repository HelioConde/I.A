"""Only original, controlled fixtures are executed on the host in tests."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from gameplay_contracts import TASKS, RUNNER, candidate_from_output, docker_behavior, prompt_for, syntax_check


REFERENCE = {
    "movePlayer": "function movePlayer(x,direction,speed,dt){return x+direction*speed*dt;}",
    "jumpVelocity": "function jumpVelocity(vy,grounded,pressed,power){return grounded&&pressed?-power:vy;}",
    "rectsOverlap": "function rectsOverlap(a,b){return a.x<b.x+b.w&&a.x+a.w>b.x&&a.y<b.y+b.h&&a.y+a.h>b.y;}",
    "applyDamage": "function applyDamage(hp,damage,maxHp){return Math.max(0,Math.min(maxHp,hp-damage));}",
    "patrolStep": "function patrolStep(x,direction,speed,dt,minX,maxX){x+=direction*speed*dt; if(x<=minX)return {x:minX,direction:1}; if(x>=maxX)return {x:maxX,direction:-1}; return {x,direction};}",
}


class GameplayContractTests(unittest.TestCase):
    def test_unique_original_tasks_and_cases(self):
        self.assertEqual(len(TASKS), 5)
        self.assertEqual(len({task["id"] for task in TASKS}), 5)
        self.assertEqual(len({task["name"] for task in TASKS}), 5)
        self.assertTrue(all(len(task["cases"]) >= 3 for task in TASKS))

    def test_extracts_only_continuation(self):
        task = TASKS[0]
        prompt = prompt_for(task)
        self.assertEqual(candidate_from_output(task, prompt + "x){return x;}\nFIM\nprivate"),
                         "function movePlayer(x){return x;}")
        with self.assertRaises(ValueError):
            candidate_from_output(task, "unrelated text")

    def test_author_written_reference_cases_detect_real_results(self):
        """Only controlled fixtures; generated code is NEVER run by CI."""
        node = shutil.which("node")
        if not node:
            self.skipTest("Node unavailable for trusted fixture self-test")
        for task in TASKS:
            with self.subTest(task=task["id"]), tempfile.TemporaryDirectory() as temp:
                p = Path(temp)
                (p / "candidate.js").write_text(REFERENCE[task["name"]], encoding="utf-8")
                (p / "spec.json").write_text(json.dumps({"name": task["name"], "cases": task["cases"]}), encoding="utf-8")
                (p / "runner.js").write_text(RUNNER.replace('"/work/', '"' + p.as_posix() + '/'), encoding="utf-8")
                result = subprocess.run([node, str(p / "runner.js")], capture_output=True,
                                        text=True, timeout=5, check=False)
                self.assertEqual(result.returncode, 0, result.stderr)
                outcome = json.loads(result.stdout)
                self.assertEqual(outcome["passed"], len(task["cases"]))
                self.assertEqual(outcome["failed_case_ids"], [])

    def test_incorrect_reference_does_not_fake_pass(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node unavailable for trusted fixture self-test")
        task = TASKS[0]
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)
            (p / "candidate.js").write_text("function movePlayer(){return 0;}", encoding="utf-8")
            (p / "spec.json").write_text(json.dumps({"name": task["name"], "cases": task["cases"]}), encoding="utf-8")
            (p / "runner.js").write_text(RUNNER.replace('"/work/', '"' + p.as_posix() + '/'), encoding="utf-8")
            result = subprocess.run([node, str(p / "runner.js")], capture_output=True,
                                    text=True, timeout=5, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["passed"], 0)

    def test_syntax_check_only_parses_candidate(self):
        self.assertEqual(syntax_check("function add(a,b){return a+b;}"),
                         "PASS" if shutil.which("node") else "UNAVAILABLE_NODE")
        self.assertEqual(syntax_check(""), "FAIL_LENGTH")

    def test_docker_is_not_required_for_syntax_only(self):
        with patch("gameplay_contracts.shutil.which", return_value=None):
            self.assertEqual(syntax_check("function f(){return 1;}"), "UNAVAILABLE_NODE")
            self.assertEqual(docker_behavior("function f(){}", TASKS[0]), {"status": "UNAVAILABLE_DOCKER"})

    def test_offline_docker_flags_for_untrusted_execution(self):
        with patch("gameplay_contracts.shutil.which", return_value="docker"), patch(
            "gameplay_contracts.subprocess.run"
        ) as run:
            run.return_value.returncode = 0
            run.return_value.stdout = json.dumps({"passed": 2, "total": 3})
            result = docker_behavior("function movePlayer(){return 0;}", TASKS[0])
            self.assertEqual(result["status"], "FAIL")
            command = run.call_args.args[0]
            for flag in ("--pull=never", "--network=none", "--read-only", "--cap-drop=ALL",
                         "--security-opt=no-new-privileges", "--pids-limit=64", "--user=65534:65534"):
                self.assertIn(flag, command)
            self.assertEqual(command[-2:], ["node:22-alpine", "/work/runner.js"])


if __name__ == "__main__":
    unittest.main()
