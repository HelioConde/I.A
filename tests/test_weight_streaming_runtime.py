from __future__ import annotations
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
from brain_ssd.gguf_inspector import GGUFInspector
from brain_ssd.weight_streaming_runtime import build_residency_plan, unsupported_inference_message
from test_gguf_inspector import _fixture


class WeightStreamingRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "fixture.gguf"
        _fixture(self.path)
        self.inspector = GGUFInspector(self.path)

    def test_dense_default_marks_every_tensor_mandatory(self):
        plan = build_residency_plan(self.inspector)
        self.assertTrue(plan.is_dense_baseline)
        self.assertEqual(plan.mandatory_bytes, plan.total_bytes)
        self.assertEqual(len(plan.mandatory), 2)

    def test_experts_require_explicit_exact_declaration(self):
        plan = build_residency_plan(self.inspector, expert_tensor_names=("second",))
        self.assertEqual(plan.expert_bytes, 34)
        self.assertEqual([item.name for item in plan.mandatory], ["first"])
        with self.assertRaises(KeyError):
            build_residency_plan(self.inspector, expert_tensor_names=("guessed.expert",))
        with self.assertRaises(ValueError):
            build_residency_plan(self.inspector, expert_tensor_names=("second", "second"))

    def test_no_inference_is_claimed(self):
        self.assertIn("not implemented", unsupported_inference_message())


if __name__ == "__main__":
    unittest.main()
