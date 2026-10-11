from __future__ import annotations

import mmap
import os
import tempfile
import unittest
from pathlib import Path

from brain_ssd.cold_hint import CognitiveColdHintResidencyController, LRUColdHintResidencyController
from brain_ssd.residency import MappedRegion
from brain_ssd.resource_pressure import (
    classify_container_result, classify_pressure, detect_environment, parse_flat_key_values,
    parse_limit, parse_psi,
)


class PressureTests(unittest.TestCase):
    def test_limit_stat_events_and_psi_parsing(self):
        self.assertIsNone(parse_limit("max\n")); self.assertEqual(parse_limit("536870912"), 536870912)
        values = parse_flat_key_values("file 42\noom 0\nbad nope\n")
        self.assertEqual(values, {"file": 42, "oom": 0})
        psi = parse_psi("some avg10=0.25 avg60=0.10 total=9\nfull avg10=0.00 total=1\n")
        self.assertEqual(psi["some"]["avg10"], .25); self.assertEqual(psi["full"]["total"], 1)

    def test_pressure_classification_uses_capacity_and_reclaim(self):
        self.assertEqual(classify_pressure(10, 100, {}, {}), "LOW")
        self.assertEqual(classify_pressure(70, 100, {}, {}), "MODERATE")
        self.assertEqual(classify_pressure(92, 100, {"pgscan": 1}, {}), "HIGH")
        self.assertEqual(classify_pressure(99, 100, {"pgscan": 1}, {"full":{"avg10":.1}}), "CRITICAL")

    def test_environment_label_and_oom_handling(self):
        self.assertIn(detect_environment(), {"CODESPACE_CONTAINER_LIMITED", "CODESPACE_UNCONSTRAINED", "PHYSICAL_NATIVE"})
        self.assertEqual(classify_container_result(137, True, None), "OOM_INVALID")
        self.assertEqual(classify_container_result(1, False, None), "FAILED")
        self.assertEqual(classify_container_result(0, False, {"cgroup_events_delta":{"oom":0}}), "VALID")
        self.assertEqual(classify_container_result(0, False, {"cgroup_events_delta":{"oom":1}}), "OOM_INVALID")

    @unittest.skipUnless(os.name == "posix", "madvise de páginas é específico de POSIX")
    def test_cold_hint_is_aligned_one_shot_and_never_pageout(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"data"; path.write_bytes(b"\0"*(2*1024**2))
            with path.open("rb") as stream:
                mapping=mmap.mmap(stream.fileno(),0,access=mmap.ACCESS_READ); region=MappedRegion.borrow(mapping,stream.fileno())
                try:
                    for cls in (CognitiveColdHintResidencyController, LRUColdHintResidencyController):
                        controller=cls(region,1024**2)
                        self.assertEqual(controller.mode,"madv_cold")
                        self.assertTrue(controller.evict(0)); self.assertFalse(controller.evict(0))
                        controller.keep(0); self.assertTrue(controller.evict(0))
                        self.assertFalse(hasattr(controller,"data_cache"))
                finally: region.release(); mapping.close()

    def test_portable_runner_and_profiles_exist(self):
        root=Path(__file__).resolve().parents[1]
        source=(root/"tools/run_memory_pressure_validation.py").read_text()
        self.assertIn("TARGET_8GB",source); self.assertIn("LOW_4GB",source)
        self.assertIn("hard-limit-proof.json",source); self.assertNotIn("MADV_PAGEOUT",source)


if __name__=="__main__": unittest.main()
