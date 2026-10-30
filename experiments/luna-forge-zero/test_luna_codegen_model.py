"""Focused tests for safe tokenizer boundaries and deterministic decoding."""
from __future__ import annotations

import unittest

import torch

from luna_codegen_model import Config, LunaMiniCoder


class MiniCoderGenerationTests(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(17)
        self.model = LunaMiniCoder(Config())

    def test_greedy_decoding_is_independent_of_global_rng_state(self):
        first = self.model.generate(
            "TASK: move player\nCODE:\n",
            chars=20,
            deterministic=True,
        )
        torch.manual_seed(999)
        torch.rand(100)
        second = self.model.generate(
            "TASK: move player\nCODE:\n",
            chars=20,
            deterministic=True,
        )
        self.assertEqual(first, second)

    def test_sampling_remains_seed_reproducible_for_legacy_callers(self):
        torch.manual_seed(71)
        first = self.model.generate("TASK:\n", chars=12)
        torch.manual_seed(71)
        second = self.model.generate("TASK:\n", chars=12)
        self.assertEqual(first, second)

    def test_non_ascii_prompt_is_mapped_to_ascii_unknown_token(self):
        generated = self.model.generate("Tarefa: ação\n", chars=8, deterministic=True)
        self.assertTrue(generated.startswith("Tarefa: a??o\n"))

    def test_generation_arguments_are_validated(self):
        with self.assertRaisesRegex(ValueError, "chars"):
            self.model.generate("x", chars=-1)
        with self.assertRaisesRegex(ValueError, "temperature"):
            self.model.generate("x", temperature=-0.1)
        with self.assertRaisesRegex(ValueError, "temperature"):
            self.model.generate("x", temperature=float("nan"))
        with self.assertRaisesRegex(ValueError, "prompt"):
            self.model.generate("", chars=1)
        with self.assertRaisesRegex(ValueError,"chars must be between 1 and 2048"):
            self.model.generate("x",chars=2049)

    def test_zero_temperature_remains_greedy_and_seed_independent(self):
        torch.manual_seed(17)
        first=self.model.generate("TASK:\n",chars=8,temperature=0)
        torch.manual_seed(999)
        second=self.model.generate("TASK:\n",chars=8,temperature=0)
        self.assertEqual(first,second)


if __name__ == "__main__":
    unittest.main()
