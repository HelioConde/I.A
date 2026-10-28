"""Synthetic-only KOM header audit regression tests."""
from __future__ import annotations
from pathlib import Path
import json
import struct
import sys
import tempfile
import unittest
from unittest import mock

LAB=Path(__file__).resolve().parents[1]/"experiments"/"luna-forge-zero"
sys.path.insert(0,str(LAB))
from audit_kom_headers import scan, classify_header

def header(version,items,table_size=4):
    payload=bytearray(72)
    magic=f"KOG GC TEAM MASSFILE V.{version}.".encode("ascii")
    payload[:len(magic)]=magic
    struct.pack_into("<I",payload,52,items)
    struct.pack_into("<I",payload,68,table_size)
    return bytes(payload)

class KomMetadataTests(unittest.TestCase):
    def test_recognizes_known_format_without_parsing_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            (folder/"game.kom").write_bytes(header("0.2",9)+b"HIDDEN_SOURCE_NOT_TO_READ")
            (folder/"other.kom").write_bytes(header("0.3",4)+b"SCRIPT_TEXT_NOT_TO_READ")
            (folder/"new.kom").write_bytes(b"Unknown"+bytes(80))
            (folder/"not_archive.lua").write_bytes(b"return 1")
            hshield=folder/"HShield"
            hshield.mkdir()
            (hshield/"shield.kom").write_bytes(header("0.2",1000))
            backups=folder/"backup"
            backups.mkdir()
            (backups/"private.kom").write_bytes(header("0.2",1000))
            original_open=Path.open
            def limited_open(path,*args,**kwargs):
                if str(path).lower().endswith(".kom"):
                    stream=original_open(path,*args,**kwargs)
                    return RestrictedFile(stream)
                return original_open(path,*args,**kwargs)
            with mock.patch.object(Path,"open",autospec=True,side_effect=limited_open):
                report=scan(folder)
            self.assertEqual(report["kom_files_sampled"],3)
            self.assertEqual(report["declared_internal_item_count_sum_unverified"],13)
            self.assertEqual(report["archives_with_plausible_declared_item_counts"],2)
            self.assertEqual(report["format_counts"]["kog_kom_v0_2"],1)
            self.assertEqual(report["format_counts"]["kog_kom_v0_3"],1)
            self.assertEqual(report["format_counts"]["unknown_signature"],1)
            self.assertEqual(report["protected_subdirectories_skipped"],2)
            self.assertEqual(report["header_bytes_read"],72*3)
            self.assertEqual(report["declared_internal_lua_file_count"],"UNKNOWN_NOT_INSPECTED")
            self.assertEqual(report["files_extracted"],0)
            self.assertFalse(report["weights_changed"])
            text=json.dumps(report)
            for item in ("game.kom","HShield","HIDDEN_SOURCE_NOT_TO_READ",str(folder)):
                self.assertNotIn(item,text)

    def test_broken_header_is_not_interpreted_as_count(self):
        self.assertEqual(classify_header(header("0.2",3,999999),72),
                         ("kog_kom_v0_2_unverified_layout",None))
        self.assertEqual(classify_header(header("0.4",7),80),
                         ("kog_kom_other_version",None))
        self.assertEqual(classify_header(b"SHORT",5),
                         ("unknown_or_too_short",None))
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                scan(Path(tmp),max_entries=0)

    def test_elsword_root_is_permitted_but_hshield_is_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"Elsword"
            root.mkdir()
            (root/"assets.kom").write_bytes(header("0.2",1)+b"x"*50)
            report=scan(root)
            self.assertEqual(report["kom_files_sampled"],1)

class RestrictedFile:
    def __init__(self, wrapped):
        self.wrapped=wrapped
    def __enter__(self):
        return self
    def __exit__(self,*args):
        self.wrapped.close()
    def read(self,amount=-1):
        if amount>72 or amount<0:
            raise AssertionError("Attempted to read beyond 72-byte header")
        return self.wrapped.read(amount)

if __name__=="__main__":
    unittest.main()
