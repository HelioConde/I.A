from __future__ import annotations
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
from brain_ssd.gguf_inspector import GGUFInspector
from brain_ssd.weight_cache import TensorWindowCache
from test_gguf_inspector import _fixture


class TensorWindowCacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        path = Path(self.tmp.name) / "fixture.gguf"
        _fixture(path)
        self.inspector = GGUFInspector(path)

    def test_exact_windows_hit_and_match_source(self):
        cache = TensorWindowCache(self.inspector, budget_bytes=16)
        self.assertEqual(cache.read("first", offset=2, length=8), b"A" * 8)
        self.assertEqual(cache.read("first", offset=2, length=8), b"A" * 8)
        self.assertEqual((cache.stats.hits, cache.stats.misses), (1, 1))
        self.assertEqual(cache.stats.cached_bytes, 8)

    def test_lru_eviction_never_exceeds_budget(self):
        cache = TensorWindowCache(self.inspector, budget_bytes=8)
        cache.read("first", offset=0, length=8)
        cache.read("first", offset=8, length=8)
        self.assertEqual(cache.stats.cached_bytes, 8)
        self.assertEqual(cache.stats.evictions, 1)
        cache.read("second")  # 34 bytes: correct but too large to cache.
        self.assertEqual(cache.stats.cached_bytes, 8)
        self.assertEqual(cache.stats.peak_cached_bytes, 8)

    def test_rejects_invalid_budget_and_range(self):
        with self.assertRaises(ValueError):
            TensorWindowCache(self.inspector, budget_bytes=0)
        cache = TensorWindowCache(self.inspector, budget_bytes=8)
        with self.assertRaises(ValueError):
            cache.read("first", offset=15, length=2)


if __name__ == "__main__":
    unittest.main()
