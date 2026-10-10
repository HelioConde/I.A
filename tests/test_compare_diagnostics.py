"""Safe offline before/after comparison: no inference claims from mock telemetry."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from compare_diagnostics import compare, load_summary, MAX_SUMMARY_BYTES


class TestCompare(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def package(self, data, name="data.zip"):
        dest=self.path/name
        with zipfile.ZipFile(dest,"w") as zipped:
            zipped.writestr("summary.json", json.dumps(data))
        return dest

    @staticmethod
    def base():
        return {
            "schema_version":1, "category":"SANITIZED_DIAGNOSTIC_ONLY",
            "events_retained":15, "platforms":{"Windows":1},
            "revisions":["0"*40],
            "chat_latency_ms":{"p50":2000,"sample_count":5},
            "inference_latency_ms":{"p50":1700,"sample_count":5},
            "native_peak_working_set_bytes":{"maximum":8000000,"sample_count":5},
        }

    def test_comparison_explicitly_not_proof(self):
        baseline=self.base()
        candidate=self.base()
        candidate["chat_latency_ms"]={"p50":1600,"sample_count":5}
        outcome=compare(baseline,candidate)
        self.assertEqual(outcome["evidence_level"],"DESCRIPTIVE_METADATA_ONLY")
        self.assertEqual(outcome["metrics"]["chat_latency_ms"]["relative_delta_pct"],-20)
        self.assertEqual(outcome["metrics"]["time_to_first_token_ms"]["status"],"NOT_COMPARABLE")
        self.assertTrue(any("qualidade" in item for item in outcome["warnings"]))
        self.assertNotIn("real_inference_verified",outcome)

    def test_empty_ci_packages_cannot_claim_improvement(self):
        base={"schema_version":1,"category":"SANITIZED_DIAGNOSTIC_ONLY","events_retained":0}
        output=compare(base,base)
        self.assertTrue(all(x["status"]=="NOT_COMPARABLE" for x in output["metrics"].values()))
        self.assertIn("não tem geração", " ".join(output["warnings"]))

    def test_invalid_zip_and_oversized_summary_rejected(self):
        for bad in ({}, {"schema_version":1,"category":"PRIVATE_RAW_DATA"}):
            with self.assertRaises(ValueError):
                load_summary(self.package(bad))
        with zipfile.ZipFile(self.path/"large.zip","w") as package:
            package.writestr("summary.json","X" * (MAX_SUMMARY_BYTES+1))
        with self.assertRaises(ValueError):
            load_summary(self.path/"large.zip")

    def test_safe_roundtrip(self):
        self.assertEqual(load_summary(self.package(self.base()))["schema_version"],1)


if __name__=="__main__":
    unittest.main()
