"""Synthetic GGUF v3 fixtures for the read-only tensor directory inspector."""
from __future__ import annotations
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from brain_ssd.gguf_inspector import GGUFError, GGUFInspector


def _string(value: str) -> bytes:
    raw = value.encode("utf-8")
    return struct.pack("<Q", len(raw)) + raw


def _fixture(path: Path, *, second_type: int = 8, second_offset: int = 64) -> bytes:
    metadata = _string("general.alignment") + struct.pack("<I", 4) + struct.pack("<I", 64)
    tensors = b"".join((
        _string("first") + struct.pack("<IQQI Q", 2, 2, 2, 0, 0),
        _string("second") + struct.pack("<IQI Q", 1, 32, second_type, second_offset),
    ))
    # Header + directory are padded to the declared data alignment.
    head = b"GGUF" + struct.pack("<IQQ", 3, 2, 1) + metadata + tensors
    data_start = (len(head) + 63) // 64 * 64
    payload = head + b"\0" * (data_start - len(head)) + b"A" * 16
    payload += b"\0" * (second_offset - 16) + b"B" * 34
    path.write_bytes(payload)
    return payload


class GGUFInspectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "synthetic.gguf"
        self.before = _fixture(self.path)

    def test_locates_quantized_and_dense_tensor_ranges_without_mutation(self):
        inspected = GGUFInspector(self.path)
        self.assertEqual(inspected.version, 3)
        self.assertEqual(inspected.alignment, 64)
        first, second = inspected.tensors
        self.assertEqual((first.type_name, first.size_bytes), ("F32", 16))
        self.assertEqual((second.type_name, second.size_bytes), ("Q8_0", 34))
        self.assertEqual(inspected.read_tensor_window("first"), b"A" * 16)
        self.assertEqual(inspected.read_tensor_window("second", offset=4, length=5), b"B" * 5)
        self.assertEqual(self.path.read_bytes(), self.before)

    def test_rejects_unsupported_type_offset_and_window(self):
        unsupported = Path(self.tmp.name) / "unsupported.gguf"
        _fixture(unsupported, second_type=99)
        with self.assertRaises(GGUFError):
            GGUFInspector(unsupported)
        unaligned = Path(self.tmp.name) / "unaligned.gguf"
        _fixture(unaligned, second_offset=1)
        with self.assertRaises(GGUFError):
            GGUFInspector(unaligned)
        overlapping = Path(self.tmp.name) / "overlapping.gguf"
        _fixture(overlapping, second_offset=0)
        with self.assertRaises(GGUFError):
            GGUFInspector(overlapping)
        inspected = GGUFInspector(self.path)
        with self.assertRaises(ValueError):
            inspected.read_tensor_window("first", offset=17)
        with self.assertRaises(KeyError):
            inspected.tensor("missing")

    def test_rejects_truncated_or_wrong_magic(self):
        self.path.write_bytes(b"NOPE" + b"\0" * 64)
        with self.assertRaises(GGUFError):
            GGUFInspector(self.path)
        self.path.write_bytes(b"GGUF" + struct.pack("<IQQ", 3, 1, 0))
        with self.assertRaises(GGUFError):
            GGUFInspector(self.path)


if __name__ == "__main__":
    unittest.main()
