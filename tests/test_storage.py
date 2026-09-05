from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brain_ssd.corpus import create_data_file, create_layout_manifest, create_manifest, ensure_corpus
from brain_ssd.storage import MMapStorageBackend, StorageIntegrityError, touch_view
from brain_ssd.workloads import Workload, access_sequence


class CorpusTests(unittest.TestCase):
    def test_seed_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first, second = root / "first", root / "second"
            ensure_corpus(first, 64 * 1024, 42, [4096, 8192])
            ensure_corpus(second, 64 * 1024, 42, [4096, 8192])
            self.assertEqual((first / "brain.dat").read_bytes(), (second / "brain.dat").read_bytes())
            self.assertEqual(
                json.loads((first / "manifest-4096.json").read_text()),
                json.loads((second / "manifest-4096.json").read_text()),
            )

    def test_existing_corpus_is_reused_and_mismatch_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = create_data_file(root, 64 * 1024, 10)
            modified = path.stat().st_mtime_ns
            self.assertEqual(create_data_file(root, 64 * 1024, 10), path)
            self.assertEqual(path.stat().st_mtime_ns, modified)
            with self.assertRaises(RuntimeError):
                create_data_file(root, 64 * 1024, 11)

    def test_manifest_offsets_and_sizes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            create_data_file(root, 64 * 1024, 7)
            manifest = json.loads(create_manifest(root, 8192).read_text())
            self.assertEqual(manifest["page_count"], 8)
            for index, page in enumerate(manifest["pages"]):
                self.assertEqual(page["page_id"], index)
                self.assertEqual(page["offset"], index * 8192)
                self.assertEqual(page["size"], 8192)
                self.assertEqual(len(page["checksum"]), 64)

    def test_mismatched_existing_manifest_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest_path = ensure_corpus(root, 64 * 1024, 7, [4096])[0]
            manifest = json.loads(manifest_path.read_text())
            manifest["seed"] = 8
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaises(RuntimeError):
                ensure_corpus(root, 64 * 1024, 7, [4096])


class StorageTests(unittest.TestCase):
    def make_brain(self, root: Path, page_size: int = 4096) -> Path:
        return ensure_corpus(root, 64 * 1024, 99, [page_size])[0]

    def test_open_read_checksum_release_close_and_reopen(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manifest = self.make_brain(Path(temporary))
            backend = MMapStorageBackend(manifest)
            for _ in range(2):
                backend.open_brain()
                page = backend.get_page(3)
                self.assertEqual(page.metadata.offset, 3 * 4096)
                self.assertEqual(len(page.data), 4096)
                backend.release_page(page)
                self.assertEqual(backend.stats()["checksum_errors"], 0)
                backend.close_brain()

    def test_invalid_page(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            backend = MMapStorageBackend(self.make_brain(Path(temporary)))
            with backend:
                with self.assertRaises(IndexError):
                    backend.get_page(-1)
                with self.assertRaises(IndexError):
                    backend.get_page(1000)

    def test_truncated_file_rejected_on_open(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = self.make_brain(root)
            with (root / "brain.dat").open("r+b") as data:
                data.truncate(4096)
            with self.assertRaises(StorageIntegrityError):
                MMapStorageBackend(manifest).open_brain()

    def test_corruption_detected_on_read(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = self.make_brain(root)
            with (root / "brain.dat").open("r+b") as data:
                data.seek(4096)
                original = data.read(1)
                data.seek(4096)
                data.write(bytes([original[0] ^ 0xFF]))
            backend = MMapStorageBackend(manifest)
            with backend:
                with self.assertRaises(StorageIntegrityError):
                    backend.get_page(1)
                self.assertEqual(backend.stats()["checksum_errors"], 1)

    def test_different_page_sizes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifests = ensure_corpus(root, 64 * 1024, 9, [4096, 8192, 16384, 32768])
            self.assertEqual([json.loads(path.read_text())["page_count"] for path in manifests], [16, 8, 4, 2])

    def test_first_activation_validation_is_cached(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            backend = MMapStorageBackend(self.make_brain(Path(temporary)))
            with backend:
                for _ in range(2):
                    page = backend.get_page(2, validate="first")
                    backend.release_page(page)
                self.assertEqual(backend.stats()["verified_pages"], 1)

    def test_performance_touch_reads_each_base_page(self) -> None:
        payload = bytearray(8192)
        payload[0] = 3
        payload[4096] = 7
        payload[-1] = 11
        first = touch_view(memoryview(payload))
        payload[4096] ^= 1
        second = touch_view(memoryview(payload))
        self.assertNotEqual(first, second)

    def test_random_layout_and_extent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            base = ensure_corpus(root, 64 * 1024, 99, [4096])[0]
            random_manifest = create_layout_manifest(base, 16384, "random")
            manifest = json.loads(random_manifest.read_text())
            self.assertNotEqual([page["offset"] for page in manifest["pages"]], list(range(0, 64 * 1024, 4096)))
            backend = MMapStorageBackend(random_manifest)
            with backend:
                page = backend.get_page(0)
                backend.release_page(page)
                extent = backend.get_extent(0, 16384)
                self.assertEqual(len(extent), 16384)
                extent.release()


class WorkloadTests(unittest.TestCase):
    def test_all_workloads_are_reproducible_and_valid(self) -> None:
        pages = list(range(16))
        related = {page: ((page + 1) % 16, (page - 1) % 16) for page in pages}
        for workload in Workload:
            first = access_sequence(workload, pages, 50, 123, related)
            second = access_sequence(workload, pages, 50, 123, related)
            self.assertEqual(first, second)
            self.assertEqual(len(first), 50)
            self.assertTrue(set(first) <= set(pages))


if __name__ == "__main__":
    unittest.main()
