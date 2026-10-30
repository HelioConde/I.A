from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import evaluate_github_codegen as evaluator


class DeterministicEvaluatorTests(unittest.TestCase):
    def test_evaluator_requests_greedy_output_for_each_prompt(self):
        calls = []

        class FakeCoder:
            def __init__(self, _config):
                pass

            def load_state_dict(self, _state, assign=False):
                self.assert_assign = assign

            def eval(self):
                return self

            def generate(self, prompt, chars, temperature, deterministic=False):
                calls.append((prompt, chars, temperature, deterministic))
                return prompt + "x) { return; }\nFIM"

        with tempfile.TemporaryDirectory(prefix="luna-evaluator-test-") as directory:
            checkpoint = Path(directory)
            weights = checkpoint / "weights.pt"
            weights.write_bytes(b"synthetic-checkpoint")
            (checkpoint / "report.json").write_text(
                json.dumps({
                    "config": {},
                    "weights_sha256": hashlib.sha256(weights.read_bytes()).hexdigest(),
                }),
                encoding="utf-8",
            )
            with patch.object(evaluator, "LunaMiniCoder", FakeCoder), patch.object(
                evaluator.torch, "load", return_value={}
            ):
                first = evaluator.evaluate(checkpoint)
                calls.clear()
                second = evaluator.evaluate(checkpoint)

        self.assertEqual(len(calls), len(evaluator.PROMPTS))
        self.assertTrue(all(call[3] is True for call in calls))
        self.assertEqual(first["results"], second["results"])
        self.assertEqual([item["id"] for item in first["results"]], list(range(5)))
        self.assertEqual(
            first["syntax_pass"],
            5 if evaluator.shutil.which("node") else 0,
            first["results"],
        )


if __name__ == "__main__":
    unittest.main()
