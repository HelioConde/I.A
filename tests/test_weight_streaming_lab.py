"""Weight-window laboratory invariants. No real GGUF or LLM is required."""
from __future__ import annotations

import json
import random
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from brain_ssd.weight_streaming_lab import (
    MODES, WindowPager, make_trace, measure,
)
from bench_weight_streaming import main


class WeightStreamingTests(unittest.TestCase):
    def setUp(self):
        working = tempfile.TemporaryDirectory()
        self.addCleanup(working.cleanup)
        self.folder = Path(working.name)
        self.file = self.folder / "weights.gguf"
        rng = random.Random(23)
        with self.file.open("wb") as output:
            for _ in range(8):
                output.write(rng.randbytes(64 * 1024))
        self.before = self.file.read_bytes()
        self.page = 64 * 1024

    def test_every_mode_returns_identical_bytes_on_same_trace(self):
        expected = None
        for mode in MODES:
            with self.subTest(mode=mode):
                report = measure(
                    self.file, mode=mode, pattern="moe",
                    page_bytes=self.page, pages=8, turns=20,
                    budget_bytes=2 * self.page, seed=99,
                )
                expected = report["checksum_sink"] if expected is None else expected
                self.assertEqual(report["checksum_sink"], expected)
                self.assertEqual(report["type"], "weight_window_io_only")
                self.assertLessEqual(report["cache"]["cache_bytes_peak"],
                                     8 * self.page if mode == "full_window" else
                                     2 * self.page)
                self.assertEqual(self.file.read_bytes(), self.before)

    def test_lru_has_real_cache_hits_and_direct_stream_does_not(self):
        args = dict(pattern="moe", page_bytes=self.page, pages=8,
                    turns=24, budget_bytes=2 * self.page, seed=8)
        streamed = measure(self.file, mode="stream", **args)
        cached = measure(self.file, mode="lru", **args)
        self.assertEqual(streamed["cache"]["demand_hits"], 0)
        self.assertEqual(streamed["cache"]["demand_loads"], streamed["total_requests"])
        self.assertGreater(cached["cache"]["demand_hits"], 0)
        self.assertLess(cached["cache"]["bytes_requested_from_file"],
                        streamed["cache"]["bytes_requested_from_file"])
        self.assertLessEqual(cached["cache"]["cache_bytes_peak"], 2 * self.page)

    def test_prefetch_uses_only_previous_transitions(self):
        with WindowPager(self.file, offset=0, page_bytes=self.page, pages=8,
                         budget_bytes=3 * self.page, mode="prefetch") as pager:
            pager.access(0)
            pager.access(1)
            self.assertEqual(pager.stats["prefetch_loads"], 0)
            for _ in range(5):
                for index in (2, 0, 1):
                    pager.access(index)
            self.assertLessEqual(pager.stats["cache_bytes_peak"], 3 * self.page)
            self.assertLessEqual(pager.stats["prefetch_loads"],
                                 pager.stats["demand_loads"] + 15)

    def test_dense_trace_must_touch_every_page_each_turn(self):
        dense = make_trace(8, 3, "dense")
        self.assertEqual(dense, list(range(8)) * 3)
        moe = make_trace(8, 3, "moe")
        self.assertLess(len(moe), len(dense))
        self.assertEqual(moe, make_trace(8, 3, "moe"))

    def test_partial_last_page_is_not_read_past_end(self):
        short = self.folder / "partial.gguf"
        short.write_bytes(self.before + b"extra")
        with WindowPager(short, offset=0, page_bytes=self.page, pages=9,
                         budget_bytes=self.page, mode="stream") as pager:
            self.assertEqual(pager._read(8), b"extra")
            self.assertEqual(pager.access(8),
                             __import__("zlib").crc32(b"extra"))

    def test_reject_excessive_budget_bad_source_and_invalid_page(self):
        with self.assertRaises(ValueError):
            WindowPager(self.file, offset=0, page_bytes=self.page,
                        pages=9, budget_bytes=self.page, mode="stream")
        with self.assertRaises(ValueError):
            WindowPager(self.file, offset=1, page_bytes=self.page,
                        pages=8, budget_bytes=self.page, mode="stream")
        with self.assertRaises(ValueError):
            WindowPager(self.file, offset=0, page_bytes=self.page,
                        pages=8, budget_bytes=300 * 1024 * 1024, mode="stream")
        with self.assertRaises(ValueError):
            make_trace(10, 5, "actual_moe")

    def test_cli_uses_temp_fixture_and_writes_json_without_weights(self):
        report = self.folder / "single.json"
        code = main([
            "--fixture-mib", "1", "--pages", "8", "--page-kib", "128",
            "--turns", "8", "--mode", "lru", "--budget-mib", "1",
            "--output", str(report),
        ])
        self.assertEqual(code, 0)
        result = json.loads(report.read_text(encoding="utf-8"))
        self.assertEqual(result["input"]["kind"], "temporary_fixture")
        self.assertEqual(result["type"], "weight_window_io_only")
        self.assertNotIn(str(self.folder), json.dumps(result))

    def test_cli_matrix_checks_sinks_across_subprocesses(self):
        report = self.folder / "matrix.json"
        status = main([
            "--source", str(self.file),
            "--pages", "8", "--page-kib", "64", "--turns", "8",
            "--budget-mib", "1", "--matrix", "--output", str(report),
        ])
        self.assertEqual(status, 0)
        result = json.loads(report.read_text(encoding="utf-8"))
        self.assertEqual(result["status"], "consistent")
        self.assertEqual([case["mode"] for case in result["runs"]], list(MODES))
        self.assertEqual(self.file.read_bytes(), self.before)


if __name__ == "__main__":
    unittest.main()
