"""Offline validations for manually curated GitHub game-source candidates."""
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parent
REVIEW = ROOT / "LUNA_GAMECODER_SOURCE_REVIEW.json"


class SourceReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.review = json.loads(REVIEW.read_text(encoding="utf-8"))

    def test_no_automatic_ingest_or_training(self):
        self.assertEqual(
            self.review["execution_status"], "CANDIDATES_ONLY_NOT_DOWNLOADED_NOT_TRAINED"
        )
        self.assertTrue(self.review["existing_training_corpus_unchanged"])

    def test_repositories_are_unique_and_pinned(self):
        rows = self.review["candidates"]
        repos = [row["repo"] for row in rows]
        self.assertEqual(len(repos), len(set(repos)))
        for row in rows:
            self.assertRegex(row["repo"], r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
            self.assertRegex(row["commit"], r"^[a-f0-9]{40}$")
            self.assertRegex(row["license_blob_sha"], r"^[a-f0-9]{40}$")
            self.assertEqual(row["license_evidence"], "LICENSE")
            self.assertIn(row["license"], {"MIT", "Apache-2.0"})

    def test_eligible_sources_are_mit_and_code_only(self):
        eligible = [row for row in self.review["candidates"] if row["status"].startswith("eligible_")]
        self.assertGreaterEqual(len(eligible), 2)
        self.assertEqual({row["proposed_split"] for row in eligible}, {"train", "reserved_holdout"})
        for row in eligible:
            self.assertEqual(row["license"], "MIT")
            self.assertTrue(row["code_paths"])
            self.assertTrue(all(p.endswith((".js", ".ts", ".tsx", ".gd")) for p in row["code_paths"]))
            self.assertTrue(all(".." not in p.split("/") for p in row["code_paths"]))

    def test_unlicensed_repositories_remain_quarantined(self):
        blocked = self.review["quarantined_no_detected_license"]
        self.assertGreater(len(blocked), 0)
        approved = {r["repo"] for r in self.review["candidates"]}
        self.assertTrue(approved.isdisjoint(blocked))
        self.assertTrue(set(blocked).isdisjoint(self.review["not_gameplay_training_sources"]))


if __name__ == "__main__":
    unittest.main()
