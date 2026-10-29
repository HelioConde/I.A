"""Synthetic provenance and integrity tests; never fetches external sources."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import github_corpus


def fixture_sources():
    return (
        {
            "repo": "luna-fixtures/original-game",
            "commit": "a" * 40,
            "evidence": "LICENSE",
            "evidence_phrase": "MIT License",
            "license": "MIT",
            "split": "train",
            "category": "original-js",
            "files": ("move.js", "jump.js"),
        },
        {
            "repo": "luna-fixtures/heldout-game",
            "commit": "b" * 40,
            "evidence": "LICENSE",
            "evidence_phrase": "MIT License",
            "license": "MIT",
            "split": "holdout",
            "category": "original-js",
            "files": ("combat.js",),
        },
    )


class GithubCorpusIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.out = Path(self.temporary.name) / "corpus"
        self.sources = fixture_sources()
        payloads = {}
        for source in self.sources:
            payloads[github_corpus.raw_url(
                source["repo"], source["commit"], source["evidence"]
            )] = b"MIT License\nSynthetic fixture only.\n"
            for path in source["files"]:
                payloads[github_corpus.raw_url(source["repo"], source["commit"], path)] = (
                    f"function {Path(path).stem}() {{\r\n  return true;\r\n}}\r\n".encode()
                )

        def fake_fetch(url):
            return payloads[url]

        self.fake_fetch = fake_fetch
        self.patches = (mock.patch.object(github_corpus, "SOURCES", self.sources),)
        for patcher in self.patches:
            patcher.start()
        github_corpus.collect(self.out, fetch=self.fake_fetch)

    def tearDown(self):
        for patcher in reversed(self.patches):
            patcher.stop()
        self.temporary.cleanup()

    def test_synthetic_pinned_project_splits_verify_without_network(self):
        result = github_corpus.verify(self.out)
        self.assertEqual(result, {"verified": True, "files": 3, "repos": 2, "train": 2, "holdout": 1})
        rows = [
            json.loads(line)
            for line in (self.out / "corpus.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        self.assertTrue(all("\r" not in row["code"] for row in rows))
        self.assertTrue(all(row["normalized_sha256"] for row in rows))

    def test_code_checksum_is_rechecked_even_if_outer_manifest_is_refreshed(self):
        corpus_path = self.out / "corpus.jsonl"
        manifest_path = self.out / "manifest.json"
        rows = [json.loads(line) for line in corpus_path.read_text(encoding="utf-8").splitlines()]
        rows[0]["code"] += "// tampered\n"
        corpus_path.write_text(
            "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
            encoding="utf-8",
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["corpus_sha256"] = hashlib.sha256(corpus_path.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Normalized source checksum mismatch"):
            github_corpus.verify(self.out)

    def test_license_evidence_is_rechecked_even_if_outer_hash_is_refreshed(self):
        notices_path = self.out / "LICENSE_NOTICES.json"
        manifest_path = self.out / "manifest.json"
        notices = json.loads(notices_path.read_text(encoding="utf-8"))
        notices[0]["license_text"] = "Terms are not MIT."
        notices_path.write_text(json.dumps(notices), encoding="utf-8")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["licenses_sha256"] = hashlib.sha256(notices_path.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "License evidence mismatch"):
            github_corpus.verify(self.out)


if __name__ == "__main__":
    unittest.main()
