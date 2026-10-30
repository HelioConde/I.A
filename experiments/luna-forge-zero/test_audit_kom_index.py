"""Synthetic-only tests for safe, bounded KOM header and index analysis."""
from __future__ import annotations

import builtins
import html
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock
import zlib

import audit_kom_headers
import audit_kom_index
from kom_audit import ENTRY_SIZE, HEADER_SIZE, audit_file, audit_path, parse_header


def make_header(version: str, count: int) -> bytes:
    header = bytearray(HEADER_SIZE)
    encoded = f"KOG GC TEAM MASSFILE V.{version}".encode("ascii")
    header[: len(encoded)] = encoded
    struct.pack_into("<I4x", header, 52, count)
    return bytes(header)


def make_entry(name: str, uncompressed: int, compressed: int, offset: int) -> bytes:
    encoded = name.encode("latin-1")
    return struct.pack("<60s3I", encoded, uncompressed, compressed, offset)


def make_archive(version: str, entries: list[bytes], payload: bytes = b"") -> bytes:
    header = make_header(version, len(entries))
    index = b"".join(entries)
    return header + index + payload


def make_v03_archive(
    entries: list[tuple[str, int, int, int, int, str]],
    payload: bytes = b"",
    *,
    declared_count: int | None = None,
    xml_size_adjustment: int = 0,
    checksum_adjustment: int = 0,
    signature: bytes = b"KOG GC TEAM MASSFILE V.0.3.",
) -> bytes:
    file_elements = []
    for name, size, compressed_size, checksum, file_time, algorithm in entries:
        file_elements.append(
            '<File Name="{}" Size="{}" CompressedSize="{}" Checksum="{}" '
            'FileTime="{}" Algorithm="{}"/>'.format(
                html.escape(name, quote=True),
                size,
                compressed_size,
                f"{checksum:08x}",
                f"{file_time:08x}",
                html.escape(algorithm, quote=True),
            )
        )
    manifest = f"<Files>{''.join(file_elements)}</Files>".encode("utf-8")
    count = len(entries) if declared_count is None else declared_count
    header = struct.pack(
        "<52sIIIII",
        signature,
        count,
        1,
        sum(entry[4] for entry in entries),
        (zlib.adler32(manifest) + checksum_adjustment) & 0xFFFFFFFF,
        len(manifest) + xml_size_adjustment,
    )
    return header + manifest + payload


class KomIndexAuditTests(unittest.TestCase):
    def test_exact_legacy_26_byte_signatures(self):
        for version in ("0.2", "0.3"):
            with self.subTest(version=version):
                header = parse_header(make_header(version, 7))
                self.assertIsNotNone(header)
                self.assertEqual(header.signature, "KOG")
                self.assertEqual(header.version, version)
                self.assertEqual(header.entry_count, 7)
                self.assertEqual(len(f"KOG GC TEAM MASSFILE V.{version}".encode("ascii")), 26)

    def test_v02_uses_reference_offsets_and_counts_index_not_offset_68(self):
        entry = make_entry("scripts\\sample.lua", 40, 20, 0)
        report = audit_path(self._write_archive(make_archive("0.2", [entry], b"x" * 20)))
        self.assertEqual(report["format_counts"], {"0.2": 1})
        self.assertEqual(report["version_confidence_counts"], {"high": 1})
        self.assertEqual(report["package_status_counts"]["recognized"], 1)
        self.assertEqual(report["declared_entries"], 1)
        self.assertEqual(report["validated_entries"], 1)
        self.assertEqual(report["extensions"], {".lua": 1})
        self.assertEqual(report["declared_compressed_bytes"], 20)
        self.assertEqual(report["invalid_entries"], 0)

    def test_v03_xml_manifest_is_validated_and_aggregated(self):
        data = make_v03_archive(
            [
                ("scripts\\stage.lua", 80, 4, 0xABCD, 0x1A2, "1"),
                ("data\\stage.xml", 20, 3, 0xDEAD, 0xF00, "0"),
            ],
            b"x" * 7,
        )
        report = audit_path(self._write_archive(data))
        self.assertEqual(report["format_counts"], {"0.3": 1})
        self.assertEqual(report["version_confidence_counts"], {"high": 1})
        self.assertEqual(report["package_status_counts"]["recognized"], 1)
        self.assertEqual(report["validated_entries"], 2)
        self.assertEqual(report["extensions"], {".lua": 1, ".xml": 1})
        self.assertEqual(report["declared_compressed_bytes"], 7)
        self.assertEqual(
            report["version_summaries"]["0.3"]["extensions"],
            {".lua": 1, ".xml": 1},
        )
        self.assertEqual(
            report["version_summaries"]["0.3"]["declared_compressed_bytes"],
            7,
        )
        self.assertNotIn("stage.lua", json.dumps(report))

    def test_v03_rejects_malformed_xml(self):
        manifest = b"<Files><File></Files>"
        data = struct.pack(
            "<52sIIIII",
            b"KOG GC TEAM MASSFILE V.0.3.",
            1,
            1,
            0,
            zlib.adler32(manifest),
            len(manifest),
        ) + manifest
        report = audit_path(self._write_archive(data))
        self.assertEqual(report["package_status_counts"]["invalid"], 1)
        self.assertEqual(report["manifest_invalid"], 1)
        self.assertEqual(report["validated_entries"], 0)

    def test_v03_rejects_inconsistent_manifest_size(self):
        data = make_v03_archive([], xml_size_adjustment=1)
        report = audit_path(self._write_archive(data))
        self.assertEqual(report["package_status_counts"]["invalid"], 1)
        self.assertEqual(report["manifest_invalid"], 1)

    def test_v03_rejects_incorrect_adler32(self):
        data = make_v03_archive([], checksum_adjustment=1)
        report = audit_path(self._write_archive(data))
        self.assertEqual(report["package_status_counts"]["invalid"], 1)
        self.assertEqual(report["entry_validation_failures"], {"manifest_checksum_mismatch": 1})

    def test_checksum_mismatch_rejects_manifest_with_170_declared_entries(self):
        data = make_v03_archive(
            [
                (f"synthetic/mechanic_{index:03d}.lua", 16, 1, index, 0, "0")
                for index in range(170)
            ],
            b"x" * 170,
            checksum_adjustment=1,
        )
        report = audit_path(self._write_archive(data))
        self.assertEqual(report["manifest_invalid"], 1)
        self.assertEqual(report["package_status_counts"]["invalid"], 1)
        self.assertEqual(report["declared_entries"], 170)
        self.assertEqual(report["validated_entries"], 0)
        self.assertEqual(report["extracted_entries"], 0)
        self.assertEqual(report["invalid_entries"], 170)
        self.assertEqual(report["extensions"], {})
        self.assertEqual(
            report["version_summaries"]["0.3"]["entry_validation_failures"],
            {"manifest_checksum_mismatch": 1},
        )
        self.assertNotIn("mechanic_000.lua", json.dumps(report))

    def test_v03_checksum_failure_rejects_all_170_declared_entries(self):
        data = make_v03_archive(
            [
                (f"original/mechanic_{index:03d}.lua", 8, 1, index, 0, "0")
                for index in range(170)
            ],
            b"x" * 170,
            checksum_adjustment=1,
        )
        report = audit_path(self._write_archive(data))
        self.assertEqual(report["package_status_counts"]["invalid"], 1)
        self.assertEqual(report["manifest_invalid"], 1)
        self.assertEqual(report["declared_entries"], 170)
        self.assertEqual(report["validated_entries"], 0)
        self.assertEqual(report["invalid_entries"], 170)
        self.assertEqual(report["extensions"], {})
        self.assertEqual(report["entry_validation_failures"], {"manifest_checksum_mismatch": 1})
        self.assertNotIn("mechanic_000.lua", json.dumps(report))

    def test_v03_rejects_duplicate_names_without_reporting_them(self):
        data = make_v03_archive(
            [
                ("same.lua", 4, 2, 0, 0, "1"),
                ("same.lua", 4, 2, 0, 0, "1"),
            ],
            b"data",
        )
        report = audit_path(self._write_archive(data))
        self.assertEqual(report["package_status_counts"]["invalid"], 1)
        self.assertEqual(report["invalid_entries"], 1)
        self.assertEqual(report["entry_validation_failures"], {"duplicate_name": 1})
        self.assertNotIn("same.lua", json.dumps(report))

    def test_v03_rejects_declared_entry_count_mismatch(self):
        data = make_v03_archive(
            [("one.lua", 4, 1, 0, 0, "1")],
            b"x",
            declared_count=2,
        )
        report = audit_path(self._write_archive(data))
        self.assertEqual(report["package_status_counts"]["invalid"], 1)
        self.assertEqual(report["manifest_invalid"], 1)
        self.assertEqual(report["declared_entries"], 2)
        self.assertEqual(report["validated_entries"], 0)

    def test_v03_does_not_validate_spans_after_unreadable_metadata(self):
        manifest = (
            b'<Files><File Name="first.lua" Size="1" Checksum="00000000" '
            b'FileTime="00000000" Algorithm="0"/>'
            b'<File Name="second.lua" Size="3" CompressedSize="3" '
            b'Checksum="00000000" FileTime="00000000" Algorithm="0"/>'
            b"</Files>"
        )
        data = struct.pack(
            "<52sIIIII",
            b"KOG GC TEAM MASSFILE V.0.3.",
            2,
            1,
            0,
            zlib.adler32(manifest),
            len(manifest),
        ) + manifest + b"123"
        report = audit_path(self._write_archive(data))
        self.assertEqual(report["package_status_counts"]["invalid"], 1)
        self.assertEqual(report["validated_entries"], 0)
        self.assertEqual(
            report["entry_validation_failures"],
            {"invalid_entry_metadata": 1, "offset_chain_unverifiable": 1},
        )

    def test_v03_reports_compressed_spans_outside_package(self):
        data = make_v03_archive(
            [("first.lua", 4, 4, 0, 0, "1"), ("past-end.lua", 8, 8, 0, 0, "1")],
            b"12345678",
        )
        report = audit_path(self._write_archive(data))
        self.assertEqual(report["package_status_counts"]["invalid"], 1)
        self.assertEqual(report["entries_outside_file_bounds"], 1)
        self.assertEqual(report["validated_entries"], 1)
        self.assertEqual(report["extensions"], {".lua": 1})

    def test_v03_rejects_dtd_and_entities(self):
        data = make_v03_archive([("../private.lua", 1, 1, 0, 0, "0")], b"x")
        manifest_start = 72
        manifest_end = data.find(b"</Files>") + len(b"</Files>")
        manifest = b'<!DOCTYPE Files [<!ENTITY x "x">]>' + data[manifest_start:manifest_end]
        data = struct.pack(
            "<52sIIIII",
            b"KOG GC TEAM MASSFILE V.0.3.",
            1,
            1,
            0,
            zlib.adler32(manifest),
            len(manifest),
        ) + manifest + b"x"
        report = audit_path(self._write_archive(data))
        self.assertEqual(report["package_status_counts"]["invalid"], 1)
        self.assertEqual(report["manifest_invalid"], 1)
        self.assertEqual(report["dangerous_entry_names"], 0)
        self.assertNotIn("private.lua", json.dumps(report))

    def test_v03_rejects_dangerous_names_without_reporting_them(self):
        data = make_v03_archive([("../private.lua", 1, 1, 0, 0, "0")], b"x")
        report = audit_path(self._write_archive(data))
        self.assertEqual(report["package_status_counts"]["invalid"], 1)
        self.assertEqual(report["dangerous_entry_names"], 1)
        self.assertEqual(report["validated_entries"], 0)
        self.assertEqual(report["extensions"], {})
        self.assertNotIn("private.lua", json.dumps(report))

    def test_v03_rejects_oversized_manifest_before_reading_it(self):
        with mock.patch("kom_audit.MAX_XML_BYTES", 8):
            data = make_v03_archive([])
            report = audit_path(self._write_archive(data))
        self.assertEqual(report["package_status_counts"]["invalid"], 1)
        self.assertEqual(report["manifest_oversized"], 1)
        self.assertEqual(report["validated_entries"], 0)

    def test_v03_requires_exact_signature_and_exact_file_size(self):
        wrong_signature = make_v03_archive([], signature=b"KOG GC TEAM MASSFILE V.0.3.X")
        signature_report = audit_path(self._write_archive(wrong_signature))
        self.assertEqual(signature_report["package_status_counts"]["invalid"], 1)
        self.assertEqual(signature_report["manifest_invalid"], 0)

        trailing_bytes = make_v03_archive([], b"unexpected")
        size_report = audit_path(self._write_archive(trailing_bytes))
        self.assertEqual(size_report["package_status_counts"]["invalid"], 1)
        self.assertEqual(size_report["entry_validation_failures"], {"file_size_mismatch": 1})

    def test_v03_reads_only_header_and_manifest(self):
        payload = b"payload must not be read"
        data = make_v03_archive([("metadata.lua", 7, len(payload), 0, 0, "0")], payload)
        path = self._write_archive(data)
        manifest_end = len(data) - len(payload)
        real_open = builtins.open
        read_ranges: list[tuple[int, int]] = []

        class ReadMonitor:
            def __init__(self, stream):
                self.stream = stream

            def __enter__(self):
                return self

            def __exit__(self, *args):
                self.stream.close()

            def read(self, size=-1):
                start = self.stream.tell()
                content = self.stream.read(size)
                read_ranges.append((start, len(content)))
                return content

        with mock.patch(
            "builtins.open",
            side_effect=lambda *args, **kwargs: ReadMonitor(real_open(*args, **kwargs)),
        ):
            result = audit_file(path)
        self.assertEqual(result.status, "recognized")
        self.assertTrue(all(start + size <= manifest_end for start, size in read_ranges))
        self.assertEqual(sum(size for _, size in read_ranges), manifest_end)

    def test_unknown_version_is_not_parsed_as_an_index(self):
        path = self._write_archive(make_archive("0.9", [make_entry("a.lua", 1, 1, 0)], b"x"))
        real_open = builtins.open
        read_sizes: list[int] = []

        class HeaderMonitor:
            def __init__(self, stream):
                self.stream = stream

            def __enter__(self):
                return self

            def __exit__(self, *args):
                self.stream.close()

            def read(self, size=-1):
                read_sizes.append(size)
                return self.stream.read(size)

        with mock.patch(
            "builtins.open",
            side_effect=lambda *a, **k: HeaderMonitor(real_open(*a, **k)),
        ):
            report = audit_path(path)
        self.assertEqual(report["format_counts"], {"unknown": 1})
        self.assertEqual(report["package_status_counts"]["unknown"], 1)
        self.assertEqual(report["validated_entries"], 0)
        self.assertEqual(report["unknown_versions"], 1)
        self.assertEqual(read_sizes, [HEADER_SIZE])

    def test_unknown_legacy_signature_version_remains_conservative(self):
        path = self._write_archive(make_archive("0.1", [make_entry("a.lua", 1, 1, 0)], b"x"))
        report = audit_path(path)
        self.assertEqual(report["format_counts"], {"unknown": 1})
        self.assertEqual(report["package_status_counts"]["unknown"], 1)
        self.assertEqual(report["validated_entries"], 0)
        self.assertEqual(report["unknown_versions"], 1)

    def test_unknown_signature_is_reported_without_reading_index(self):
        path = self._write_archive(b"NOT A KOG KOM" + b"\0" * 100)
        report = audit_path(path)
        self.assertEqual(report["unknown_signature_files"], 1)
        self.assertEqual(report["package_status_counts"]["unknown"], 1)
        self.assertEqual(report["validated_entries"], 0)
        self.assertEqual(report["unsupported_formats"], 1)

    def test_truncated_header_is_invalid_without_crashing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "short.kom"
            path.write_bytes(b"KOG GC TEAM MASSFILE V.0.2")
            self.assertIsNone(parse_header(path.read_bytes()))
            report = audit_path(path)
        self.assertEqual(report["kom_files"], 1)
        self.assertEqual(report["package_status_counts"]["invalid"], 1)
        self.assertEqual(report["errors"], 0)

    def test_impossible_count_and_truncated_table_are_invalid(self):
        cases = (
            make_header("0.2", 1),
            make_header("0.2", 200_001),
        )
        for index, data in enumerate(cases):
            with self.subTest(index=index):
                report = audit_path(self._write_archive(data))
                self.assertEqual(report["package_status_counts"]["invalid"], 1)
                self.assertEqual(report["validated_entries"], 0)

    def test_out_of_bounds_offset_is_not_counted_as_valid_entry(self):
        entry = make_entry("outside.png", 99, 50, 10_000)
        report = audit_path(self._write_archive(make_archive("0.2", [entry])))
        self.assertEqual(report["package_status_counts"]["invalid"], 1)
        self.assertEqual(report["invalid_entries"], 1)
        self.assertEqual(report["extensions"], {})
        self.assertEqual(
            report["entry_validation_failures"],
            {"offset_after_data_region": 1},
        )

    def test_candidate_offset_bases_are_reported_but_not_validated(self):
        table_size = ENTRY_SIZE
        absolute_payload_offset = HEADER_SIZE + table_size
        archive_absolute = make_archive(
            "0.2",
            [make_entry("candidate.lua", 4, 4, absolute_payload_offset)],
            b"data",
        )
        report = audit_path(self._write_archive(archive_absolute))
        version_report = report["version_summaries"]["0.2"]
        self.assertEqual(version_report["validated_entries"], 0)
        self.assertEqual(
            version_report["offset_interpretation_candidates"],
            {"absolute_from_file_start": 1},
        )
        self.assertEqual(
            version_report["offset_interpretation_ranges"],
            {"absolute_from_file_start": 1},
        )

    def test_numeric_offset_summary_distinguishes_outside_file_offsets(self):
        data = make_archive(
            "0.2",
            [
                make_entry("within.lua", 4, 4, 0),
                make_entry("beyond.lua", 4, 4, 5000),
            ],
            b"data",
        )
        report = audit_path(self._write_archive(data))
        self.assertEqual(
            report["version_summaries"]["0.2"]["offset_value_summary"],
            {
                "minimum_relative_offset": 0,
                "maximum_relative_offset": 5000,
                "offsets_within_file_size": 1,
                "offsets_within_data_region": 1,
                "maximum_compressed_size": 4,
            },
        )

    def test_validation_diagnostics_are_aggregated_separately_by_version(self):
        with tempfile.TemporaryDirectory() as directory:
            v02 = make_archive(
                "0.2",
                [make_entry("valid.lua", 4, 4, 0), make_entry("outside.png", 5, 1, 200)],
                b"1234",
            )
            v03 = make_v03_archive(
                [("valid.xml", 4, 4, 0, 0, "1"), ("past-end.dds", 5, 2, 0, 0, "1")],
                b"1234",
            )
            (Path(directory) / "a.kom").write_bytes(v02)
            (Path(directory) / "b.kom").write_bytes(v03)
            report = audit_path(Path(directory))
        self.assertEqual(
            report["version_summaries"]["0.2"],
            {
                "packages_by_status": {"invalid": 1},
                "declared_entries": 2,
                "validated_entries": 1,
                "extracted_entries": 0,
                "invalid_entries": 1,
                "manifest_invalid": 0,
                "manifest_oversized": 0,
                "entries_outside_file_bounds": 0,
                "declared_compressed_bytes": 5,
                "declared_uncompressed_bytes": 9,
                "entry_validation_failures": {"offset_after_data_region": 1},
                "extensions": {".lua": 1},
                "categories": {"script": 1},
                "offset_interpretation_candidates": {"relative_to_data_start": 1},
                "offset_interpretation_ranges": {"relative_to_data_start": 1},
                "offset_value_summary": {
                    "minimum_relative_offset": 0,
                    "maximum_relative_offset": 200,
                    "offsets_within_file_size": 2,
                    "offsets_within_data_region": 1,
                    "maximum_compressed_size": 4,
                },
            },
        )
        self.assertEqual(
            report["version_summaries"]["0.3"]["entry_validation_failures"],
            {
                "compressed_span_exceeds_file_size": 1,
                "file_size_mismatch": 1,
            },
        )
        self.assertEqual(
            report["version_summaries"]["0.3"]["offset_interpretation_candidates"],
            {},
        )
        self.assertEqual(
            report["version_summaries"]["0.3"]["offset_interpretation_ranges"],
            {},
        )
        self.assertEqual(
            report["entry_validation_failures"],
            {
                "compressed_span_exceeds_file_size": 1,
                "file_size_mismatch": 1,
                "offset_after_data_region": 1,
            },
        )
        self.assertNotIn("valid.lua", json.dumps(report))

    def test_empty_recognized_package_is_valid(self):
        report = audit_path(self._write_archive(make_archive("0.2", [])))
        self.assertEqual(report["package_status_counts"]["recognized"], 1)
        self.assertEqual(report["declared_entries"], 0)

    def test_extensions_categories_and_dangerous_names_are_aggregated_only(self):
        entries = [
            make_entry("../../private.lua", 10, 5, 0),
            make_entry("textures\\ui.dds", 20, 10, 0),
            make_entry("mesh\\stage.p3m", 30, 15, 0),
        ]
        report = audit_path(self._write_archive(make_archive("0.2", entries, b"x" * 30)))
        serialized = json.dumps(report)
        self.assertEqual(report["dangerous_entry_names"], 1)
        self.assertEqual(report["extensions"], {".dds": 1, ".lua": 1, ".p3m": 1})
        self.assertEqual(report["categories"], {"imagem": 1, "modelo": 1, "script": 1})
        self.assertNotIn("private.lua", serialized)
        self.assertNotIn("textures", serialized)

    def test_large_sparse_package_reads_only_bounded_metadata(self):
        entry = make_entry("large.lua", 1_000_000_000, 10, 0)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "large.kom"
            with path.open("wb") as stream:
                stream.write(make_header("0.2", 1) + entry)
                stream.seek(512 * 1024 * 1024 - 1)
                stream.write(b"\0")

            real_open = builtins.open
            reads: list[tuple[int, int]] = []

            class ReadMonitor:
                def __init__(self, stream):
                    self.stream = stream

                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    self.stream.close()

                def read(self, size=-1):
                    before = self.stream.tell()
                    data = self.stream.read(size)
                    reads.append((before, len(data)))
                    return data

            def monitored_open(*args, **kwargs):
                return ReadMonitor(real_open(*args, **kwargs))

            with mock.patch("builtins.open", side_effect=monitored_open):
                report = audit_file(path)
            self.assertEqual(report.valid_entries, 1)
            self.assertTrue(all(start + size <= HEADER_SIZE + ENTRY_SIZE for start, size in reads))
            self.assertLess(sum(size for _, size in reads), path.stat().st_size)

    def test_cli_prints_json_and_refuses_overwriting_output(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self._write_archive(make_archive("0.2", []), directory)
            output = Path(directory) / "report.json"
            with mock.patch("sys.argv", ["audit_kom_index.py", str(source), "--json-out", str(output)]):
                self.assertEqual(audit_kom_index.main(), 0)
            self.assertIn('"package_status_counts"', output.read_text(encoding="utf-8"))
            with mock.patch("sys.argv", ["audit_kom_index.py", str(source), "--json-out", str(output)]):
                with self.assertRaises(FileExistsError):
                    audit_kom_index.main()

    def test_header_audit_stops_at_fixed_header(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self._write_archive(make_archive("0.2", []), directory)
            real_open = builtins.open
            read_sizes: list[int] = []

            class HeaderMonitor:
                def __init__(self, stream):
                    self.stream = stream

                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    self.stream.close()

                def read(self, size=-1):
                    read_sizes.append(size)
                    return self.stream.read(size)

            with mock.patch("builtins.open", side_effect=lambda *a, **k: HeaderMonitor(real_open(*a, **k))):
                report = audit_kom_headers.audit_headers(path)
            self.assertEqual(report["kom_files_by_version"], {"0.2": 1})
            self.assertEqual(read_sizes, [60])

    def test_header_audit_classifies_both_legacy_versions(self):
        with tempfile.TemporaryDirectory() as directory:
            for version in ("0.2", "0.3"):
                (Path(directory) / f"synthetic-{version}.kom").write_bytes(
                    make_header(version, 0)
                )
            report = audit_kom_headers.audit_headers(Path(directory))
        self.assertEqual(report["kom_files_by_version"], {"0.2": 1, "0.3": 1})
        self.assertEqual(report["version_confidence_counts"], {"high": 1, "provisional": 1})

    def test_audit_excludes_hshield_backup_and_private_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "packages").mkdir()
            (root / "HShield-data").mkdir()
            (root / "backups").mkdir()
            (root / "dados_privados").mkdir()
            archive = make_v03_archive([])
            (root / "packages" / "included.kom").write_bytes(archive)
            (root / "HShield-data" / "excluded.kom").write_bytes(archive)
            (root / "backups" / "excluded.kom").write_bytes(archive)
            (root / "dados_privados" / "excluded.kom").write_bytes(archive)
            report = audit_path(root)
        self.assertEqual(report["files_examined"], 1)
        self.assertEqual(report["format_counts"], {"0.3": 1})
        self.assertEqual(report["manifest_invalid"], 0)

    def _write_archive(self, data: bytes, directory: str | None = None) -> Path:
        temp_directory = directory or self._temp_directory.name
        path = Path(temp_directory) / f"fixture-{len(list(Path(temp_directory).glob('fixture-*.kom')))}.kom"
        path.write_bytes(data)
        return path

    def setUp(self):
        self._temp_directory = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._temp_directory.cleanup()


if __name__ == "__main__":
    unittest.main()
