"""Consistency checks for the user-supplied, non-recomputed audit baseline."""
from __future__ import annotations

import json
from pathlib import Path
import unittest


BASELINE = Path(__file__).with_name("KOM_AUDIT_BASELINE_2026-10-29.json")


class KomAuditBaselineTests(unittest.TestCase):
    def test_user_inventory_totals_are_explicit_and_non_extractive(self):
        baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
        packages = baseline["packages"]
        self.assertEqual(
            packages["v0_2_structurally_validated"]
            + packages["v0_3_structurally_validated"]
            + packages["v0_3_manifest_checksum_mismatch_packages"]
            + packages["unknown_or_unsupported_packages"],
            baseline["scope"]["kom_packages_found"],
        )
        self.assertEqual(
            packages["v0_2_entries_structurally_validated"]
            + packages["v0_3_entries_structurally_validated"]
            + packages["v0_3_entries_rejected_due_to_manifest_checksum_mismatch"],
            106245,
        )
        self.assertFalse(baseline["recomputed_by_agent"])
        self.assertFalse(baseline["security_and_integrity"]["archive_payloads_extracted"])
        self.assertFalse(baseline["security_and_integrity"]["commercial_code_used_for_training"])
        self.assertEqual(baseline["internal_entry_name_extensions"]["lua"], 3993)
        self.assertEqual(baseline["external_visible_lua_tree"]["files_observed_in_prior_audit"], 5880)


if __name__ == "__main__":
    unittest.main()
