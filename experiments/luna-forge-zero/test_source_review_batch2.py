"""Offline provenance guard for the second Luna game-source selection."""
from pathlib import Path
import json
import re
import unittest

DATA = Path(__file__).resolve().parent / "LUNA_GAMECODER_SOURCE_REVIEW_BATCH2.json"

class SourceReviewBatch2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(DATA.read_text(encoding="utf-8"))

    def test_no_automatic_training(self):
        d = self.data
        self.assertEqual(d["status"], "METADATA_CURATED_NO_CODE_COLLECTED_NO_TRAINING")
        self.assertEqual(d["training_runs_started"], 0)
        self.assertFalse(d["new_model_checkpoint"])
        self.assertEqual(d["policy"]["currently_imported_projects"], 0)
        self.assertTrue(d["policy"]["existing_collector_remains_unchanged"])

    def test_pinned_source_licenses_and_unique_repos(self):
        rows = self.data["pin_verified_license_sources"]
        self.assertGreaterEqual(len(rows), 8)
        names = [r["repo"] for r in rows]
        self.assertEqual(len(set(names)), len(names))
        for row in rows:
            self.assertRegex(row["repo"], r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
            self.assertRegex(row["commit"], r"^[a-f0-9]{40}$")
            self.assertRegex(row["license_blob_sha"], r"^[a-f0-9]{40}$")
            self.assertIn(row["license"], ("MIT", "Apache-2.0"))
            self.assertIn(row["license_evidence"], ("LICENSE", "LICENSE.md"))
            self.assertFalse(row["allowed_for_training_now"])

    def test_no_license_metadata_treated_as_grant(self):
        unlicensed = {r["repo"] for r in self.data["metadata_triage"] if not r["spdx"] or r["spdx"] == "NOASSERTION"}
        self.assertIn("serenity-valley/game", unlicensed)
        self.assertIn("momentum-mod/game", unlicensed)
        self.assertIn("MonoGame/MonoGame", unlicensed)

    def test_repo_lists_do_not_duplicate_approved_candidates(self):
        approved = {r["repo"] for r in self.data["pin_verified_license_sources"]}
        unapproved = self.data["other_provided_links_not_approved_for_training"]
        self.assertEqual(len(unapproved), len(set(unapproved)))
        self.assertFalse(approved.intersection(unapproved))

if __name__ == "__main__":
    unittest.main()
