from __future__ import annotations

from contextlib import nullcontext
from unittest.mock import patch
import unittest

import torch

import brain_ssd_bridge as bridge


class BrainSsdDeterministicGenerationTests(unittest.TestCase):
    def test_infer_forwards_greedy_option_without_seeding_rng(self):
        calls = []

        class FakeCoder:
            def __init__(self, _config):
                pass

            def load_state_dict(self, _state, assign=False):
                self.assign = assign

            def eval(self):
                return self

            def generate(self, request, chars, temperature, deterministic=False):
                calls.append((request, chars, temperature, deterministic))
                return "synthetic output"

            def parameters(self):
                return iter(())

        with (
            patch.object(torch, "set_num_threads"),
            patch.object(bridge, "_load", return_value=({}, {"config": {}})),
            patch.object(bridge, "skill_pages", return_value=nullcontext({
                "skills": [], "page_reads": 0, "logical_bytes": 0, "storage": "none"
            })),
            patch.object(bridge, "_rss", return_value=0),
            patch("luna_codegen_model.LunaMiniCoder", FakeCoder),
            patch("torch.manual_seed") as seed_rng,
        ):
            result = bridge.infer(
                "write code",
                "unused-checkpoints",
                mode="code",
                deterministic=True,
                max_chars=12,
            )

        self.assertEqual(result["inference"]["raw_generated_text"], "synthetic output")
        self.assertEqual(calls, [("write code", 12, 0.6, True)])
        seed_rng.assert_not_called()


if __name__ == "__main__":
    unittest.main()
