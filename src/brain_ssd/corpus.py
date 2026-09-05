from __future__ import annotations

import hashlib
import json
import os
import random
import struct
from pathlib import Path

SCHEMA_VERSION = 1
CONTENT_VERSION = 1
GENERATION_UNIT = 1024 * 1024


def _unit(seed: int, unit_index: int, size: int) -> bytes:
    digest = hashlib.sha256(struct.pack("<QQ", seed, unit_index)).digest()
    return (digest * ((size + len(digest) - 1) // len(digest)))[:size]


def _atomic_json(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def create_data_file(directory: Path, size_bytes: int, seed: int) -> Path:
    if size_bytes <= 0 or size_bytes % 4096:
        raise ValueError("corpus size must be a positive multiple of 4096 bytes")
    directory.mkdir(parents=True, exist_ok=True)
    data_path = directory / "brain.dat"
    descriptor_path = directory / "corpus.json"
    descriptor = {
        "schema_version": SCHEMA_VERSION,
        "content_version": CONTENT_VERSION,
        "size_bytes": size_bytes,
        "seed": seed,
        "data_file": data_path.name,
        "generation": "sha256(seed, 1MiB-unit-index) repeated within each unit",
    }
    if data_path.exists() or descriptor_path.exists():
        if not (data_path.exists() and descriptor_path.exists()):
            raise RuntimeError("incomplete existing corpus")
        existing = json.loads(descriptor_path.read_text())
        if existing != descriptor or data_path.stat().st_size != size_bytes:
            raise RuntimeError("existing corpus does not match requested size/seed/version")
        return data_path

    temporary = directory / "brain.dat.tmp"
    with temporary.open("xb", buffering=0) as output:
        remaining = size_bytes
        unit_index = 0
        while remaining:
            length = min(GENERATION_UNIT, remaining)
            output.write(_unit(seed, unit_index, length))
            remaining -= length
            unit_index += 1
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, data_path)
    _atomic_json(descriptor_path, descriptor)
    return data_path


def create_manifest(directory: Path, page_size_bytes: int) -> Path:
    descriptor = json.loads((directory / "corpus.json").read_text())
    data_path = directory / descriptor["data_file"]
    corpus_size = descriptor["size_bytes"]
    if page_size_bytes <= 0 or page_size_bytes % 4096:
        raise ValueError("page size must be a positive multiple of 4096 bytes")
    if corpus_size % page_size_bytes:
        raise ValueError("page size must divide corpus size exactly")
    page_count = corpus_size // page_size_bytes
    manifest_path = directory / f"manifest-{page_size_bytes}.json"
    pages = []
    with data_path.open("rb") as data:
        for page_id in range(page_count):
            offset = page_id * page_size_bytes
            payload = data.read(page_size_bytes)
            if len(payload) != page_size_bytes:
                raise RuntimeError("truncated corpus while creating manifest")
            rng = random.Random((descriptor["seed"] << 32) ^ page_size_bytes ^ page_id)
            candidates = {((page_id - 1) % page_count), ((page_id + 1) % page_count)}
            while len(candidates) < min(4, page_count):
                candidates.add(rng.randrange(page_count))
            pages.append(
                {
                    "page_id": page_id,
                    "version": CONTENT_VERSION,
                    "offset": offset,
                    "size": page_size_bytes,
                    "checksum": hashlib.sha256(payload).hexdigest(),
                    "related_pages": sorted(candidates - {page_id}),
                }
            )
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "content_version": CONTENT_VERSION,
        "seed": descriptor["seed"],
        "data_file": data_path.name,
        "corpus_size_bytes": corpus_size,
        "page_size_bytes": page_size_bytes,
        "page_count": page_count,
        "checksum_algorithm": "sha256",
        "pages": pages,
    }
    _atomic_json(manifest_path, manifest)
    return manifest_path


def ensure_corpus(directory: Path, size_bytes: int, seed: int, page_sizes: list[int]) -> list[Path]:
    create_data_file(directory, size_bytes, seed)
    manifests = []
    for page_size in page_sizes:
        path = directory / f"manifest-{page_size}.json"
        if not path.exists():
            create_manifest(directory, page_size)
        else:
            manifest = json.loads(path.read_text())
            expected = {
                "schema_version": SCHEMA_VERSION,
                "content_version": CONTENT_VERSION,
                "seed": seed,
                "corpus_size_bytes": size_bytes,
                "page_size_bytes": page_size,
                "page_count": size_bytes // page_size,
            }
            if any(manifest.get(key) != value for key, value in expected.items()):
                raise RuntimeError(f"existing manifest does not match request: {path}")
        manifests.append(path)
    return manifests


def create_layout_manifest(base_manifest_path: Path, extent_size_bytes: int, layout: str) -> Path:
    if layout not in ("colocated", "random"):
        raise ValueError("layout must be colocated or random")
    base = json.loads(base_manifest_path.read_text())
    page_size = base["page_size_bytes"]
    if extent_size_bytes < page_size or extent_size_bytes % page_size:
        raise ValueError("extent must be a multiple of logical page size")
    slots = list(range(base["page_count"]))
    if layout == "random":
        random.Random(base["seed"] ^ page_size ^ extent_size_bytes ^ 0xA55A).shuffle(slots)
    data_path = base_manifest_path.parent / base["data_file"]
    pages = []
    with data_path.open("rb") as data:
        for page in base["pages"]:
            physical_slot = slots[page["page_id"]]
            offset = physical_slot * page_size
            data.seek(offset)
            payload = data.read(page_size)
            item = dict(page)
            item["offset"] = offset
            item["checksum"] = hashlib.sha256(payload).hexdigest()
            item["extent_id"] = offset // extent_size_bytes
            pages.append(item)
    manifest = dict(base)
    manifest.update({
        "layout": layout,
        "logical_page_size_bytes": page_size,
        "storage_extent_size_bytes": extent_size_bytes,
        "pages": pages,
    })
    path = base_manifest_path.parent / f"layout-l{page_size}-e{extent_size_bytes}-{layout}.json"
    _atomic_json(path, manifest)
    return path
