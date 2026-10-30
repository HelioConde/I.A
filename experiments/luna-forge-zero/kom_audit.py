"""Conservative, metadata-only readers for legacy KOG KOM index layouts."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
import os
from pathlib import Path
import re
import stat
import struct
import time
import xml.etree.ElementTree as ET
from typing import BinaryIO, Iterator
import zlib

HEADER_SIZE = 60
V03_HEADER_SIZE = 72
ENTRY_SIZE = 72
MAX_ENTRIES = 200_000
MAX_INDEX_BYTES = 16 * 1024 * 1024
MAX_XML_BYTES = 16 * 1024 * 1024
MAX_FILES = 10_000
MAX_SECONDS = 60.0
READ_CHUNK_ENTRIES = 512
REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
ENTRY = struct.Struct("<60s3I")
V03_HEADER = struct.Struct("<52sIIIII")
V03_SIGNATURE = b"KOG GC TEAM MASSFILE V.0.3."
VERSION_RE = re.compile(
    rb"^KOG GC TEAM MASSFILE V\.0\.([0-9]+)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class KomHeader:
    signature: str
    version: str
    entry_count: int | None


@dataclass
class FileAudit:
    status: str
    version: str
    confidence: str
    declared_entries: int = 0
    valid_entries: int = 0
    invalid_entries: int = 0
    dangerous_names: int = 0
    compressed_bytes: int = 0
    uncompressed_bytes: int = 0
    declared_compressed_bytes: int = 0
    declared_uncompressed_bytes: int = 0
    extensions: Counter[str] = field(default_factory=Counter)
    categories: Counter[str] = field(default_factory=Counter)
    validation_failures: Counter[str] = field(default_factory=Counter)
    offset_interpretation_candidates: Counter[str] = field(default_factory=Counter)
    offset_interpretation_ranges: Counter[str] = field(default_factory=Counter)
    minimum_relative_offset: int | None = None
    maximum_relative_offset: int | None = None
    offsets_within_file_size: int = 0
    offsets_within_data_region: int = 0
    maximum_compressed_size: int = 0
    manifest_invalid: int = 0
    manifest_oversized: int = 0
    entries_outside_file_bounds: int = 0
    unknown_version: int = 0
    unsupported_format: int = 0


def parse_header(data: bytes) -> KomHeader | None:
    """Parse the 26-byte legacy signature and count, not the first entry at 68."""
    if len(data) < HEADER_SIZE:
        return None

    version_field = struct.unpack_from("<26s26x", data, 0)[0].split(b"\0", 1)[0].strip()
    if not version_field.upper().startswith(b"KOG"):
        return None

    match = VERSION_RE.match(version_field)
    version = f"0.{match.group(1).decode('ascii')}" if match else "unknown"
    entry_count = struct.unpack_from("<I", data, 52)[0]
    return KomHeader("KOG", version, entry_count)


def _is_reparse_point(info: os.stat_result) -> bool:
    attributes = getattr(info, "st_file_attributes", 0)
    return bool(attributes & REPARSE_POINT)


def _is_excluded_directory(name: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]", "", name.casefold())
    return (
        normalized in {"git", "venv"}
        or "hshield" in normalized
        or "backup" in normalized
        or "private" in normalized
        or "privado" in normalized
        or "privada" in normalized
    )


def iter_kom_files(root: Path, deadline: float) -> Iterator[Path]:
    """Walk directories without following symlinks or Windows reparse points."""
    if _is_excluded_directory(root.name):
        raise ValueError("Refusing an excluded directory")
    info = root.lstat()
    if stat.S_ISLNK(info.st_mode) or _is_reparse_point(info):
        raise ValueError("Refusing to follow a symlink or reparse point")
    if stat.S_ISREG(info.st_mode):
        yield root
        return
    if not stat.S_ISDIR(info.st_mode):
        raise ValueError("Input must be a regular file or directory")

    pending = [root]
    while pending and time.monotonic() < deadline:
        directory = pending.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                if time.monotonic() >= deadline:
                    return
                try:
                    child_info = entry.stat(follow_symlinks=False)
                except OSError:
                    continue
                if stat.S_ISDIR(child_info.st_mode) and _is_excluded_directory(entry.name):
                    continue
                if entry.is_symlink() or _is_reparse_point(child_info):
                    continue
                if stat.S_ISDIR(child_info.st_mode):
                    pending.append(Path(entry.path))
                elif stat.S_ISREG(child_info.st_mode) and entry.name.casefold().endswith(".kom"):
                    yield Path(entry.path)


def _extension_and_category(raw_name: bytes) -> tuple[str, str, bool]:
    return _extension_and_category_text(raw_name.decode("latin-1"))


def _extension_and_category_text(name: str) -> tuple[str, str, bool]:
    components = re.split(r"[\\/]", name)
    dangerous = (
        name.startswith(("/", "\\"))
        or any(part == ".." for part in components)
        or any(part == "." for part in components)
        or name.endswith(("/", "\\"))
        or ":" in name
        or any(ord(char) < 32 for char in name)
    )
    basename = components[-1].strip()
    suffix = basename.rsplit(".", 1)[-1].casefold() if "." in basename else ""
    extension = f".{suffix}" if suffix and re.fullmatch(r"[a-z0-9_+-]{1,16}", suffix) else "[sem_extensao]"

    category_map = {
        ".lua": "script",
        ".js": "script",
        ".gd": "script",
        ".xml": "dados",
        ".json": "dados",
        ".ini": "dados",
        ".txt": "dados",
        ".dds": "imagem",
        ".png": "imagem",
        ".jpg": "imagem",
        ".jpeg": "imagem",
        ".tga": "imagem",
        ".bmp": "imagem",
        ".p3m": "modelo",
        ".obj": "modelo",
        ".wav": "audio",
        ".ogg": "audio",
        ".mp3": "audio",
    }
    return extension, category_map.get(extension, "outros"), dangerous


def _read_exact(stream: BinaryIO, size: int) -> bytes:
    pieces: list[bytes] = []
    remaining = size
    while remaining:
        piece = stream.read(remaining)
        if not piece:
            break
        pieces.append(piece)
        remaining -= len(piece)
    return b"".join(pieces)


def _invalid_v03(
    result: FileAudit,
    reason: str,
    *,
    invalid_entries: int | None = None,
    oversized: bool = False,
    manifest_error: bool = True,
) -> FileAudit:
    result.status = "invalid"
    result.manifest_invalid = int(manifest_error)
    result.manifest_oversized = int(oversized)
    result.validation_failures[reason] += 1
    if invalid_entries is not None:
        result.invalid_entries = invalid_entries
    return result


def _parse_v03_integer(value: str, maximum: int, *, base: int = 10) -> int:
    if base == 16:
        digits = value[2:] if value.lower().startswith("0x") else value
        valid = re.fullmatch(r"[0-9a-fA-F]+", digits) is not None
    else:
        valid = re.fullmatch(r"[0-9]+", value) is not None
        digits = value
    if not valid:
        raise ValueError("invalid_integer")
    number = int(digits, base)
    if number > maximum:
        raise ValueError("integer_out_of_range")
    return number


def _audit_v03(stream: BinaryIO, file_size: int, first_60_bytes: bytes) -> FileAudit:
    result = FileAudit(
        status="invalid",
        version="0.3",
        confidence="high",
    )
    remaining_header = _read_exact(stream, V03_HEADER_SIZE - len(first_60_bytes))
    if len(remaining_header) != V03_HEADER_SIZE - len(first_60_bytes):
        return _invalid_v03(result, "truncated_v03_header", manifest_error=False)
    header_bytes = first_60_bytes + remaining_header
    signature, count, marker, file_time_sum, checksum, xml_size = V03_HEADER.unpack(
        header_bytes
    )
    result.declared_entries = count
    if signature != V03_SIGNATURE.ljust(52, b"\0"):
        return _invalid_v03(
            result,
            "invalid_v03_signature",
            invalid_entries=count,
            manifest_error=False,
        )
    if marker != 1:
        return _invalid_v03(
            result,
            "invalid_v03_header_marker",
            invalid_entries=count,
            manifest_error=False,
        )
    if count > MAX_ENTRIES:
        return _invalid_v03(
            result,
            "entry_count_exceeds_safety_limit",
            invalid_entries=count,
            manifest_error=False,
        )
    if xml_size > MAX_XML_BYTES:
        return _invalid_v03(
            result,
            "manifest_exceeds_safety_limit",
            invalid_entries=count,
            oversized=True,
        )
    if xml_size > file_size - V03_HEADER_SIZE:
        return _invalid_v03(
            result,
            "manifest_size_exceeds_file_size",
            invalid_entries=count,
        )

    manifest = _read_exact(stream, xml_size)
    if len(manifest) != xml_size:
        return _invalid_v03(result, "manifest_size_mismatch", invalid_entries=count)
    if zlib.adler32(manifest) & 0xFFFFFFFF != checksum:
        return _invalid_v03(result, "manifest_checksum_mismatch", invalid_entries=count)
    try:
        xml_text = manifest.decode("utf-8-sig")
    except UnicodeDecodeError:
        return _invalid_v03(result, "manifest_invalid_encoding", invalid_entries=count)
    upper_xml = xml_text.upper()
    if "<!DOCTYPE" in upper_xml or "<!ENTITY" in upper_xml:
        return _invalid_v03(result, "manifest_dtd_forbidden", invalid_entries=count)
    try:
        root = ET.fromstring(manifest)
    except ET.ParseError:
        return _invalid_v03(result, "manifest_malformed_xml", invalid_entries=count)
    if (
        root.tag != "Files"
        or (root.text is not None and root.text.strip())
        or any(
            child.tag != "File"
            or (child.tail is not None and child.tail.strip())
            for child in root
        )
    ):
        return _invalid_v03(result, "manifest_invalid_structure", invalid_entries=count)
    entries = list(root)
    if len(entries) != count:
        return _invalid_v03(result, "manifest_entry_count_mismatch", invalid_entries=count)

    seen_names: set[str] = set()
    data_start = V03_HEADER_SIZE + xml_size
    current_offset = data_start
    declared_time_sum = 0
    offset_chain_known = True
    result.declared_entries = count
    for element in entries:
        attributes = element.attrib
        required = {"Name", "Size", "CompressedSize", "Checksum", "FileTime", "Algorithm"}
        if (
            not required.issubset(attributes)
            or len(element)
            or (element.text is not None and element.text.strip())
        ):
            result.validation_failures["invalid_entry_metadata"] += 1
            result.invalid_entries += 1
            result.manifest_invalid = 1
            offset_chain_known = False
            continue
        name = attributes["Name"]
        algorithm = attributes["Algorithm"]
        try:
            uncompressed_size = _parse_v03_integer(attributes["Size"], 0xFFFFFFFF)
            compressed_size = _parse_v03_integer(attributes["CompressedSize"], 0xFFFFFFFF)
            _parse_v03_integer(attributes["Checksum"], 0xFFFFFFFF, base=16)
            entry_time = _parse_v03_integer(attributes["FileTime"], 0xFFFFFFFF, base=16)
            _parse_v03_integer(attributes["Algorithm"], 0xFFFFFFFF)
        except ValueError as error:
            result.validation_failures[str(error)] += 1
            result.invalid_entries += 1
            result.manifest_invalid = 1
            offset_chain_known = False
            continue
        declared_time_sum = (declared_time_sum + entry_time) & 0xFFFFFFFF
        result.declared_compressed_bytes += compressed_size
        result.declared_uncompressed_bytes += uncompressed_size
        if not name or not algorithm or len(algorithm) > 64:
            result.validation_failures["invalid_entry_metadata"] += 1
            result.invalid_entries += 1
            result.manifest_invalid = 1
            current_offset += compressed_size
            continue
        extension, category, dangerous = _extension_and_category_text(name)
        result.dangerous_names += int(dangerous)
        canonical_name = name.replace("\\", "/").casefold()
        if dangerous:
            result.validation_failures["dangerous_name"] += 1
            result.invalid_entries += 1
            result.manifest_invalid = 1
            current_offset += compressed_size
            continue
        if canonical_name in seen_names:
            result.validation_failures["duplicate_name"] += 1
            result.invalid_entries += 1
            result.manifest_invalid = 1
            current_offset += compressed_size
            continue
        seen_names.add(canonical_name)
        result.maximum_compressed_size = max(result.maximum_compressed_size, compressed_size)
        if not offset_chain_known:
            result.validation_failures["offset_chain_unverifiable"] += 1
            result.invalid_entries += 1
            current_offset += compressed_size
            continue
        if current_offset > file_size or compressed_size > file_size - current_offset:
            result.validation_failures["compressed_span_exceeds_file_size"] += 1
            result.invalid_entries += 1
            result.entries_outside_file_bounds += 1
            result.manifest_invalid = 1
        else:
            result.valid_entries += 1
            result.compressed_bytes += compressed_size
            result.uncompressed_bytes += uncompressed_size
            result.extensions[extension] += 1
            result.categories[category] += 1
        current_offset += compressed_size

    if declared_time_sum != file_time_sum:
        result.validation_failures["file_time_sum_mismatch"] += 1
        result.manifest_invalid = 1
    if current_offset != file_size:
        result.validation_failures["file_size_mismatch"] += 1
        result.manifest_invalid = 1
    result.status = "invalid" if result.manifest_invalid else "recognized"
    result.manifest_invalid = int(bool(result.manifest_invalid))
    return result


def audit_file(path: Path) -> FileAudit | None:
    """Read the fixed header and bounded index only; payload bytes are never read."""
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or _is_reparse_point(info) or not stat.S_ISREG(info.st_mode):
        raise ValueError("Refusing non-regular KOM input")
    file_size = info.st_size
    with open(path, "rb") as stream:
        header_bytes = stream.read(HEADER_SIZE)
        header = parse_header(header_bytes)
        if header is None:
            if len(header_bytes) < HEADER_SIZE and header_bytes.startswith(b"KOG"):
                return FileAudit("invalid", "unknown", "truncated_header")
            return FileAudit(
                "unknown",
                "unknown",
                "signature_unrecognized",
                unsupported_format=1,
            )
        if header.version not in {"0.2", "0.3"}:
            return FileAudit(
                "unknown",
                "unknown",
                "signature_only",
                unknown_version=int(header.signature == "KOG"),
                unsupported_format=int(header.signature != "KOG"),
            )

        assert header.entry_count is not None
        if header.version == "0.3":
            return _audit_v03(stream, file_size, header_bytes)

        count = header.entry_count
        result = FileAudit(
            status="recognized",
            version="0.2",
            confidence="high",
            declared_entries=count,
        )
        table_bytes = count * ENTRY_SIZE
        if (
            count > MAX_ENTRIES
            or table_bytes > MAX_INDEX_BYTES
            or table_bytes > max(0, file_size - HEADER_SIZE)
        ):
            if count > MAX_ENTRIES or table_bytes > MAX_INDEX_BYTES:
                result.validation_failures["entry_count_exceeds_safety_limit"] += count
            else:
                result.validation_failures["index_exceeds_file_size"] += count
            result.status = "invalid"
            result.invalid_entries = count
            return result

        remaining = count
        while remaining:
            batch_count = min(remaining, READ_CHUNK_ENTRIES)
            batch = _read_exact(stream, batch_count * ENTRY_SIZE)
            if len(batch) != batch_count * ENTRY_SIZE:
                result.invalid_entries += remaining
                result.validation_failures["truncated_index"] += remaining
                result.status = "invalid"
                return result
            for index in range(batch_count):
                name_field, uncompressed_size, compressed_size, relative_offset = ENTRY.unpack_from(
                    batch, index * ENTRY_SIZE
                )
                raw_name = name_field.split(b"\0", 1)[0]
                extension, category, dangerous = _extension_and_category(raw_name)
                result.dangerous_names += int(dangerous)
                result.declared_compressed_bytes += compressed_size
                result.declared_uncompressed_bytes += uncompressed_size
                data_bytes = file_size - HEADER_SIZE - table_bytes
                index_end = HEADER_SIZE + table_bytes
                result.minimum_relative_offset = (
                    relative_offset
                    if result.minimum_relative_offset is None
                    else min(result.minimum_relative_offset, relative_offset)
                )
                result.maximum_relative_offset = max(
                    result.maximum_relative_offset or 0, relative_offset
                )
                result.offsets_within_file_size += int(relative_offset <= file_size)
                result.offsets_within_data_region += int(relative_offset <= data_bytes)
                result.maximum_compressed_size = max(
                    result.maximum_compressed_size, compressed_size
                )
                relative_to_header_fits = (
                    relative_offset <= file_size - HEADER_SIZE
                    and HEADER_SIZE + relative_offset >= index_end
                )
                range_checks = {
                    "relative_to_data_start": relative_offset <= data_bytes,
                    "absolute_from_file_start": index_end <= relative_offset <= file_size,
                    "relative_to_header_start": relative_to_header_fits,
                }
                for interpretation, in_range in range_checks.items():
                    if in_range:
                        result.offset_interpretation_ranges[interpretation] += 1
                if relative_offset <= data_bytes and compressed_size <= data_bytes - relative_offset:
                    result.offset_interpretation_candidates["relative_to_data_start"] += 1
                if (
                    relative_offset >= index_end
                    and relative_offset <= file_size
                    and compressed_size <= file_size - relative_offset
                ):
                    result.offset_interpretation_candidates["absolute_from_file_start"] += 1
                if (
                    relative_to_header_fits
                    and compressed_size <= file_size - (HEADER_SIZE + relative_offset)
                ):
                    result.offset_interpretation_candidates["relative_to_header_start"] += 1
                if not raw_name:
                    result.validation_failures["empty_name"] += 1
                    result.invalid_entries += 1
                    continue
                if relative_offset > data_bytes:
                    result.validation_failures["offset_after_data_region"] += 1
                    result.invalid_entries += 1
                    continue
                if compressed_size > data_bytes - relative_offset:
                    result.validation_failures["compressed_span_exceeds_data_region"] += 1
                    result.invalid_entries += 1
                    continue
                result.valid_entries += 1
                result.compressed_bytes += compressed_size
                result.uncompressed_bytes += uncompressed_size
                result.extensions[extension] += 1
                result.categories[category] += 1
            remaining -= batch_count

        if result.invalid_entries:
            result.status = "invalid"
        return result


def _empty_report() -> dict:
    return {
        "files_examined": 0,
        "kom_files": 0,
        "unknown_signature_files": 0,
        "format_counts": {},
        "version_confidence_counts": {},
        "version_summaries": {},
        "package_status_counts": {
            "recognized": 0,
            "partially_recognized": 0,
            "invalid": 0,
            "unknown": 0,
        },
        "declared_entries": 0,
        "validated_entries": 0,
        "extracted_entries": 0,
        "invalid_entries": 0,
        "entry_validation_failures": {},
        "offset_interpretation_candidates": {},
        "offset_interpretation_ranges": {},
        "offset_value_summary": {},
        "dangerous_entry_names": 0,
        "entries_outside_file_bounds": 0,
        "manifest_invalid": 0,
        "manifest_oversized": 0,
        "unknown_versions": 0,
        "unsupported_formats": 0,
        "extensions": {},
        "categories": {},
        "declared_compressed_bytes": 0,
        "declared_uncompressed_bytes": 0,
        "compression_ratio_compressed_over_uncompressed": None,
        "metadata_file_bytes": 0,
        "errors": 0,
        "skipped_links": "not_followed",
        "partial": False,
    }


def audit_path(root: Path) -> dict:
    root = Path(root)
    report = _empty_report()
    format_counts: Counter[str] = Counter()
    confidence_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    version_statuses: dict[str, Counter[str]] = {}
    version_entries: dict[str, dict[str, int]] = {}
    version_failures: dict[str, Counter[str]] = {}
    version_offset_candidates: dict[str, Counter[str]] = {}
    version_offset_ranges: dict[str, Counter[str]] = {}
    version_offset_values: dict[str, dict[str, int | None]] = {}
    version_extensions: dict[str, Counter[str]] = {}
    version_categories: dict[str, Counter[str]] = {}
    extensions: Counter[str] = Counter()
    categories: Counter[str] = Counter()
    declared_compressed_total = declared_uncompressed_total = 0
    validated_compressed_total = uncompressed_total = 0
    deadline = time.monotonic() + MAX_SECONDS
    try:
        candidates = iter_kom_files(root, deadline)
        for path in candidates:
            if report["files_examined"] >= MAX_FILES or time.monotonic() >= deadline:
                report["partial"] = True
                break
            report["files_examined"] += 1
            try:
                info = path.lstat()
                if stat.S_ISLNK(info.st_mode) or _is_reparse_point(info):
                    report["errors"] += 1
                    continue
                report["metadata_file_bytes"] += info.st_size
                result = audit_file(path)
            except (OSError, ValueError):
                report["errors"] += 1
                continue
            if result is None:
                continue
            report["kom_files"] += 1
            if result.confidence == "signature_unrecognized":
                report["unknown_signature_files"] += 1
            report["entries_outside_file_bounds"] += result.entries_outside_file_bounds
            report["manifest_invalid"] += result.manifest_invalid
            report["manifest_oversized"] += result.manifest_oversized
            report["unknown_versions"] += result.unknown_version
            report["unsupported_formats"] += result.unsupported_format
            format_counts[result.version] += 1
            confidence_counts[result.confidence] += 1
            status_counts[result.status] += 1
            version_statuses.setdefault(result.version, Counter())[result.status] += 1
            entry_totals = version_entries.setdefault(
                result.version,
                {
                    "declared_entries": 0,
                    "validated_entries": 0,
                    "extracted_entries": 0,
                    "invalid_entries": 0,
                    "manifest_invalid": 0,
                    "manifest_oversized": 0,
                    "entries_outside_file_bounds": 0,
                    "declared_compressed_bytes": 0,
                    "declared_uncompressed_bytes": 0,
                },
            )
            entry_totals["declared_entries"] += result.declared_entries
            entry_totals["validated_entries"] += result.valid_entries
            entry_totals["invalid_entries"] += result.invalid_entries
            entry_totals["manifest_invalid"] += result.manifest_invalid
            entry_totals["manifest_oversized"] += result.manifest_oversized
            entry_totals["entries_outside_file_bounds"] += result.entries_outside_file_bounds
            entry_totals["declared_compressed_bytes"] += result.declared_compressed_bytes
            entry_totals["declared_uncompressed_bytes"] += result.declared_uncompressed_bytes
            version_failures.setdefault(result.version, Counter()).update(
                result.validation_failures
            )
            version_extensions.setdefault(result.version, Counter()).update(result.extensions)
            version_categories.setdefault(result.version, Counter()).update(result.categories)
            version_offset_candidates.setdefault(result.version, Counter()).update(
                result.offset_interpretation_candidates
            )
            version_offset_ranges.setdefault(result.version, Counter()).update(
                result.offset_interpretation_ranges
            )
            offsets = version_offset_values.setdefault(
                result.version,
                {
                    "minimum_relative_offset": None,
                    "maximum_relative_offset": None,
                    "offsets_within_file_size": 0,
                    "offsets_within_data_region": 0,
                    "maximum_compressed_size": 0,
                },
            )
            if result.minimum_relative_offset is not None:
                previous_min = offsets["minimum_relative_offset"]
                offsets["minimum_relative_offset"] = (
                    result.minimum_relative_offset
                    if previous_min is None
                    else min(previous_min, result.minimum_relative_offset)
                )
                previous_max = offsets["maximum_relative_offset"]
                offsets["maximum_relative_offset"] = max(
                    result.maximum_relative_offset or 0,
                    previous_max or 0,
                )
            offsets["offsets_within_file_size"] += result.offsets_within_file_size
            offsets["offsets_within_data_region"] += result.offsets_within_data_region
            offsets["maximum_compressed_size"] = max(
                offsets["maximum_compressed_size"] or 0,
                result.maximum_compressed_size,
            )
            report["declared_entries"] += result.declared_entries
            report["validated_entries"] += result.valid_entries
            report["invalid_entries"] += result.invalid_entries
            report["dangerous_entry_names"] += result.dangerous_names
            extensions.update(result.extensions)
            categories.update(result.categories)
            declared_compressed_total += result.declared_compressed_bytes
            declared_uncompressed_total += result.declared_uncompressed_bytes
            validated_compressed_total += result.compressed_bytes
            uncompressed_total += result.uncompressed_bytes
    except (OSError, ValueError):
        report["errors"] += 1
        report["partial"] = True

    report["format_counts"] = dict(sorted(format_counts.items()))
    report["version_confidence_counts"] = dict(sorted(confidence_counts.items()))
    report["version_summaries"] = {
        version: {
            "packages_by_status": dict(sorted(version_statuses[version].items())),
            **version_entries[version],
            "entry_validation_failures": dict(sorted(version_failures[version].items())),
            "extensions": dict(sorted(version_extensions[version].items())),
            "categories": dict(sorted(version_categories[version].items())),
            "offset_interpretation_candidates": dict(
                sorted(version_offset_candidates[version].items())
            ),
            "offset_interpretation_ranges": dict(
                sorted(version_offset_ranges[version].items())
            ),
            "offset_value_summary": version_offset_values[version],
        }
        for version in sorted(version_entries)
    }
    all_failures: Counter[str] = Counter()
    for failures in version_failures.values():
        all_failures.update(failures)
    report["entry_validation_failures"] = dict(sorted(all_failures.items()))
    all_offset_candidates: Counter[str] = Counter()
    for candidates in version_offset_candidates.values():
        all_offset_candidates.update(candidates)
    report["offset_interpretation_candidates"] = dict(sorted(all_offset_candidates.items()))
    all_offset_ranges: Counter[str] = Counter()
    for ranges in version_offset_ranges.values():
        all_offset_ranges.update(ranges)
    report["offset_interpretation_ranges"] = dict(sorted(all_offset_ranges.items()))
    report["offset_value_summary"] = {
        version: version_offset_values[version]
        for version in sorted(version_offset_values)
    }
    report["package_status_counts"].update(status_counts)
    report["extensions"] = dict(sorted(extensions.items()))
    report["categories"] = dict(sorted(categories.items()))
    report["declared_compressed_bytes"] = declared_compressed_total
    report["declared_uncompressed_bytes"] = declared_uncompressed_total
    if uncompressed_total:
        report["compression_ratio_compressed_over_uncompressed"] = (
            validated_compressed_total / uncompressed_total
        )
    return report
