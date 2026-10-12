from __future__ import annotations
import mmap
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from brain_ssd.native_weight_windows import mapped_range


class NativeWeightWindowTests(unittest.TestCase):
    def test_mapping_rounds_down_to_allocation_granularity(self):
        base, delta, length = mapped_range(65_537, 8_192, 65_536)
        self.assertEqual((base, delta, length), (65_536, 1, 8_193))

    def test_mapping_rejects_invalid_values(self):
        for args in ((-1, 1, 1), (0, 0, 1), (0, 1, 0)):
            with self.subTest(args=args):
                with self.assertRaises(ValueError):
                    mapped_range(*args)


if __name__ == "__main__":
    unittest.main()
