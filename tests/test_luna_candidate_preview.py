"""Offline unit tests for newest local candidate selection and SHA guard.

Never load arbitrary PyTorch checkpoints; tests use synthetic byte fixtures.
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

LAB=Path(__file__).resolve().parents[1]/"experiments"/"luna-forge-zero"
spec=importlib.util.spec_from_file_location("candidate_preview",LAB/"preview_local_candidate.py")
preview=importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)

def fixture(root:Path,name:str,payload:bytes=b"fake weights")->Path:
    path=root/name
    path.mkdir(parents=True)
    (path/"weights.pt").write_bytes(payload)
    report={
        "status":"experiment_not_promoted","promotion_allowed":False,
        "grandchase_raw_repositories_in_training":0,
        "weights_sha256":hashlib.sha256(payload).hexdigest(),
        "config":{"vocab":128,"block":128,"width":64,"heads":4,"layers":2},
    }
    (path/"report.json").write_text(json.dumps(report),encoding="utf-8")
    return path

class CandidatePreviewTests(unittest.TestCase):
    def test_sorted_latest_and_verified(self):
        with tempfile.TemporaryDirectory() as temp:
            data=Path(temp)
            older=fixture(data,"local-candidate-20261027-000000")
            latest=fixture(data,"local-candidate-20261028-163736")
            self.assertEqual(preview.candidates(data),[latest,older])
            report,_=preview.verify_candidate(latest,data)
            self.assertFalse(report["promotion_allowed"])

    def test_tampered_weights_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            data=Path(temp)
            model=fixture(data,"local-candidate-20261028")
            (model/"weights.pt").write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError,"SHA-256 mismatch"):
                preview.verify_candidate(model,data)

    def test_rejects_outside_and_unapproved_status(self):
        with tempfile.TemporaryDirectory() as temp:
            data=Path(temp)/"data"
            data.mkdir()
            elsewhere=Path(temp)/"elsewhere"
            elsewhere.mkdir()
            foreign=fixture(elsewhere,"local-candidate-elsewhere")
            with self.assertRaisesRegex(ValueError,"under Luna external_data"):
                preview.verify_candidate(foreign,data)
            candidate=fixture(data,"local-candidate-test")
            report=json.loads((candidate/"report.json").read_text())
            report["promotion_allowed"]=True
            (candidate/"report.json").write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError,"promotion"):
                preview.verify_candidate(candidate,data)

    def test_no_models_does_not_load_pytorch(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(preview.candidates(Path(temp)),[])

if __name__=="__main__":
    unittest.main()
