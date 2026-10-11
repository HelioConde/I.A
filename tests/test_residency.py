from __future__ import annotations

import mmap
import os
import tempfile
import unittest
from pathlib import Path

from brain_ssd.residency import (
    AdvisoryResidencyController, KernelOnlyResidencyController, MappedRegion,
    controller_for, resident_vector,
)
from brain_ssd.cache_policy import CacheEvent
from brain_ssd.physical_replay import expand_trace


@unittest.skipUnless(os.name == "posix", "residência de páginas via mincore é específica de POSIX")
class ResidencyTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "pages.dat"
        with self.path.open("wb") as stream:
            stream.truncate(4 * 1024 * 1024)
        self.file = self.path.open("rb")
        self.mapping = mmap.mmap(self.file.fileno(), 0, access=mmap.ACCESS_READ)
        self.region = MappedRegion.borrow(self.mapping, self.file.fileno())

    def tearDown(self):
        self.region.release()
        self.mapping.close()
        self.file.close()
        self.directory.cleanup()

    def test_interface_alignment_budget_and_invalid_range(self):
        controller = KernelOnlyResidencyController(self.region, 1024 * 1024)
        self.assertFalse(controller.evict(0))
        self.assertEqual(controller.stats()["interventions"], 0)
        with self.assertRaises(IndexError):
            controller.resident(4)
        with self.assertRaises(ValueError):
            KernelOnlyResidencyController(self.region, 1000)

    def test_mincore_detects_touched_page_without_copy(self):
        before = resident_vector(self.region, 0, 4096)
        sink = self.mapping[0]
        after = resident_vector(self.region, 0, 4096)
        self.assertIsInstance(sink, int)
        self.assertEqual(len(before), 1)
        self.assertTrue(after[0])
        self.assertFalse(hasattr(KernelOnlyResidencyController(self.region, 1024 * 1024), "data_cache"))

    def test_supported_and_unsupported_advice_is_safe(self):
        self.mapping[0]
        for mode in ("madv_cold", "madv_dontneed", "fadv_dontneed", "madv_pageout"):
            controller = controller_for(mode, self.region, 1024 * 1024)
            result = controller.evict(0)
            self.assertIsInstance(result, bool)
            self.assertEqual(controller.stats()["interventions"], 1)
        with self.assertRaises(ValueError):
            AdvisoryResidencyController(self.region, 1024 * 1024, "willneed")

    def test_shadow_kernel_only_never_intervenes(self):
        controller = controller_for("kernel_only", self.region, 1024 * 1024)
        for page in range(4):
            controller.keep(page)
            controller.demote(page)
        self.assertEqual(controller.stats()["interventions"], 0)

    def test_cardinality_expansion_is_deterministic_and_does_not_copy_payload(self):
        event = CacheEvent(8, "q", 7, 0, "linux", ("files",), ("CURRENT_QUERY",), None, None,
                           .9, {"topics": ["files"]}, 1024**2, 1024**2)
        left = expand_trace([event], "realistic_mix", 512)
        right = expand_trace([event], "realistic_mix", 512)
        self.assertEqual(left, right)
        self.assertLess(left[0].page_id, 512)
        self.assertFalse(any(hasattr(item, "data") for item in left))


if __name__ == "__main__":
    unittest.main()
