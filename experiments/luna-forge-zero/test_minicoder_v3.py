from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import torch

from gameplay_contracts import evaluate as evaluate_gameplay
import evaluate_github_codegen
from luna_minicoder_v3 import (
    EOS_ID,
    PAD_ID,
    LunaMiniCoderV3,
    V3Config,
    collate_completions,
    make_prompt,
)
from train_minicoder_v3 import DEFAULT_CURRICULUM, load_curriculum, train


class MiniCoderV3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document, cls.groups = load_curriculum()

    def test_curriculum_is_original_and_split_by_project_and_family(self):
        self.assertEqual(
            {name: len(tasks) for name, tasks in self.groups.items()},
            {"train": 9, "validation": 2, "test": 2},
        )
        self.assertFalse(
            {task["project"] for task in self.groups["train"]}
            & {task["project"] for task in self.groups["validation"]}
        )
        self.assertFalse(
            {task["family"] for task in self.groups["train"]}
            & {task["family"] for task in self.groups["test"]}
        )
        self.assertTrue(all(task["solution"] is None for task in self.groups["test"]))
        self.assertEqual(self.document["provenance"].find("No external") >= 0, True)

    def test_external_curriculum_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="v3-untrusted-data-") as directory:
            copy = Path(directory) / "curriculum.json"
            copy.write_bytes(DEFAULT_CURRICULUM.read_bytes())
            with self.assertRaisesRegex(ValueError, "checked-in original curriculum"):
                load_curriculum(copy)

    def test_masked_completion_loss_ignores_prompt_and_padding(self):
        batch = collate_completions(self.groups["train"][:2], V3Config())
        inputs, labels = batch
        self.assertEqual(inputs.shape, labels.shape)
        self.assertLess(inputs.shape[1], 512)
        self.assertTrue(bool((labels == -100).any()))
        self.assertTrue(bool((labels == EOS_ID).any()))
        self.assertFalse(bool((labels == PAD_ID).any()))
        for row, task in enumerate(self.groups["train"][:2]):
            prompt_length = len(make_prompt(task))
            self.assertTrue(bool((labels[row, :prompt_length - 1] == -100).all()))
            self.assertNotEqual(int(labels[row, prompt_length - 1]), -100)

    def test_model_has_512_context_and_finite_supervised_gradient(self):
        config = V3Config()
        self.assertGreaterEqual(config.block, 512)
        model = LunaMiniCoderV3(config)
        inputs, labels = collate_completions(self.groups["train"][:2], config)
        _, loss = model(inputs, labels)
        self.assertTrue(bool(torch.isfinite(loss)))
        loss.backward()
        self.assertTrue(all(
            parameter.grad is None or bool(torch.isfinite(parameter.grad).all())
            for parameter in model.parameters()
        ))

    def test_generation_stops_when_eos_is_selected(self):
        model = LunaMiniCoderV3()
        logits = torch.zeros(1, 1, model.cfg.vocab)
        logits[0, 0, EOS_ID] = 100
        with patch.object(model, "forward", return_value=(logits, None)):
            text, terminated = model.generate("TASK:\n", max_new_tokens=8)
        self.assertEqual(text, "")
        self.assertTrue(terminated)

    def test_one_step_training_checkpoint_and_syntax_only_gameplay_evaluation(self):
        with tempfile.TemporaryDirectory(prefix="luna-v3-candidate-") as directory:
            checkpoint = Path(directory) / "candidate"
            report = train(
                checkpoint,
                curriculum=DEFAULT_CURRICULUM,
                steps=1,
                batch_size=2,
                threads=1,
                seed=81,
            )
            self.assertEqual(report["status"], "candidate_not_promoted")
            self.assertEqual(report["selected_checkpoint_step"], 1)
            self.assertEqual(report["test_reference_solutions_in_training"], 0)
            self.assertEqual(report["examples_by_split"], {
                "train": 9, "validation": 2, "test": 2
            })
            self.assertTrue((checkpoint / "weights.pt").is_file())
            saved = json.loads((checkpoint / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["weights_sha256"], report["weights_sha256"])
            result = evaluate_gameplay(checkpoint, chars=16, behavior=False)
            self.assertEqual(result["model"], "MiniCoder V3 supervised completion")
            self.assertEqual(result["tasks"], 5)
            self.assertEqual(result["seen_diagnostic_tasks"], 3)
            self.assertEqual(result["reserved_test_tasks"], 2)
            self.assertFalse(result["behavior_enabled"])
            self.assertTrue(all(row["behavior"]["status"] == "NOT_TESTED"
                                for row in result["results"]))
            self.assertTrue(all(len(row["generated_sha256"]) == 64
                                for row in result["results"]))
            benchmark = evaluate_github_codegen.evaluate(checkpoint)
            self.assertEqual(benchmark["model_type"], "luna_minicoder_v3_sft")
            self.assertEqual(benchmark["model_code_samples"], len(evaluate_github_codegen.PROMPTS))
            self.assertEqual(
                [row["prompt"] for row in benchmark["results"]],
                list(evaluate_github_codegen.PROMPTS),
            )
            self.assertIn("training_loss", benchmark)
            with self.assertRaises(FileExistsError):
                train(checkpoint, steps=1, batch_size=1, threads=1)


if __name__ == "__main__":
    unittest.main()
