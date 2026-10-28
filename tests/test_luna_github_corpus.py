"""Offline regression tests: license gate, verified provenance, no train/holdout leakage."""
from __future__ import annotations
import importlib.util
import json
import sys
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]/"experiments"/"luna-forge-zero"
sys.path.insert(0,str(ROOT))
import github_corpus as corpus

class GitHubCorpusTests(unittest.TestCase):
    def fake_download(self, url):
        # Simulate pinned MIT notices and UTF-8 sources. No network in unit tests.
        if url.endswith("/LICENSE.md") or url.endswith("/LICENSE"):
            return b"MIT License\nCopyright (c) contributors\n"
        if url.endswith("/README.md"):
            return b"All source code in this repo is released under the MIT license. Assets are not."
        return b"extends CharacterBody2D\nfunc _physics_process(delta):\n    velocity.x = 200 * delta\n    move_and_slide()\n"

    def test_pinned_urls_and_code_only(self):
        self.assertEqual(len(corpus.SOURCES),4)
        self.assertEqual(len({s["repo"] for s in corpus.SOURCES}),4)
        for s in corpus.SOURCES:
            self.assertRegex(s["commit"],r"^[0-9a-f]{40}$")
            self.assertEqual(s["license"],"MIT")
            self.assertTrue(all(p.endswith((".gd",".js",".ts",".tsx")) for p in s["files"]))
        with self.assertRaises(AssertionError):
            corpus.raw_url("repo/name","0"*40,"../secret")

    def test_collect_and_verify_and_provenance(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            result=corpus.collect(root,fetch=self.fake_download)
            self.assertEqual(result["source_repositories"],4)
            self.assertGreater(result["train_files"],result["holdout_files"])
            self.assertEqual(result["holdout_repositories"],["stm1978/retro-platformer"])
            self.assertTrue(corpus.verify(root)["verified"])
            lines=(root/"corpus.jsonl").read_text().splitlines()
            self.assertTrue(all(json.loads(line)["license"]=="MIT" for line in lines))
            self.assertEqual(len(lines),result["files"])
            self.assertTrue((root/"LICENSE_NOTICES.json").is_file())

    def test_fails_closed_on_unverified_license(self):
        def download(url):
            if url.endswith(("/LICENSE.md","/LICENSE","/README.md")):
                return b"source available but license unspecified"
            return b"some code"
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError,"License evidence missing"):
                corpus.collect(Path(temp),fetch=download)

    def test_corruption_blocks_training(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            corpus.collect(root,fetch=self.fake_download)
            with (root/"corpus.jsonl").open("a",encoding="utf-8") as stream:
                stream.write('{"untrusted":true}\n')
            with self.assertRaisesRegex(ValueError,"checksum"):
                corpus.verify(root)

    def test_no_owner_projects_in_first_external_dataset(self):
        self.assertTrue(all(not s["repo"].lower().startswith("helioconde/") for s in corpus.SOURCES))
        train={s["repo"] for s in corpus.SOURCES if s["split"]=="train"}
        holdout={s["repo"] for s in corpus.SOURCES if s["split"]=="holdout"}
        self.assertFalse(train & holdout)

if __name__=="__main__":
    unittest.main()
