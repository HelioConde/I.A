from __future__ import annotations
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from bench_qwen_runtime import build_report


class QwenRuntimeBenchTests(unittest.TestCase):
    def test_report_never_includes_answer_and_marks_experiment_unavailable(self):
        report = build_report({"answer": "private generated text", "generation_limit": 96,
                               "metrics": {"ttft_ms": 1.0}, "core_mode": "subprocess"},
                              profile="economia", prompt="fixed prompt", elapsed_s=1.5)
        self.assertEqual(report["status"], "baseline_measured")
        self.assertNotIn("private generated text", str(report))
        self.assertEqual(report["conditions"]["brain_ssd_weight_streaming"]["status"], "not_implemented")


if __name__ == "__main__":
    unittest.main()
