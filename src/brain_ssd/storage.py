from __future__ import annotations

import hashlib
import json
import mmap
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class StorageIntegrityError(RuntimeError):
    pass


@dataclass(frozen=True)
class PageMetadata:
    page_id: int
    version: int
    offset: int
    size: int
    checksum: str
    related_pages: tuple[int, ...]
    extent_id: int | None = None


@dataclass
class CorticalPage:
    metadata: PageMetadata
    data: memoryview


class StorageBackend(Protocol):
    def open_brain(self) -> None: ...
    def close_brain(self) -> None: ...
    def get_page(self, page_id: int, validate: bool = True) -> CorticalPage: ...
    def release_page(self, page: CorticalPage) -> None: ...
    def stats(self) -> dict: ...


class MMapStorageBackend:
    def __init__(self, manifest_path: Path):
        self.manifest_path = Path(manifest_path)
        self._manifest: dict | None = None
        self._pages: tuple[PageMetadata, ...] = ()
        self._file = None
        self._mapping: mmap.mmap | None = None
        self._logical_bytes = 0
        self._accesses = 0
        self._checksum_errors = 0
        self._verified_pages: set[int] = set()

    @property
    def manifest(self) -> dict:
        if self._manifest is None:
            raise RuntimeError("brain is not open")
        return self._manifest

    @property
    def data_path(self) -> Path:
        return self.manifest_path.parent / self.manifest["data_file"]

    def advise_drop_cache(self) -> bool:
        manifest = json.loads(self.manifest_path.read_text())
        path = self.manifest_path.parent / manifest["data_file"]
        if not hasattr(os, "posix_fadvise") or not hasattr(os, "POSIX_FADV_DONTNEED"):
            return False
        with path.open("rb") as data:
            os.posix_fadvise(data.fileno(), 0, 0, os.POSIX_FADV_DONTNEED)
        return True

    def open_brain(self) -> None:
        if self._mapping is not None:
            raise RuntimeError("brain is already open")
        manifest = json.loads(self.manifest_path.read_text())
        required = {"schema_version", "data_file", "corpus_size_bytes", "page_size_bytes", "page_count", "pages"}
        if not required <= manifest.keys() or manifest["schema_version"] != 1:
            raise StorageIntegrityError("unsupported or incomplete manifest")
        path = self.manifest_path.parent / manifest["data_file"]
        if path.stat().st_size != manifest["corpus_size_bytes"]:
            raise StorageIntegrityError("data file size does not match manifest")
        pages = tuple(
            PageMetadata(
                page_id=item["page_id"], version=item["version"], offset=item["offset"],
                size=item["size"], checksum=item["checksum"], related_pages=tuple(item.get("related_pages", ())),
                extent_id=item.get("extent_id"),
            )
            for item in manifest["pages"]
        )
        offsets = set()
        for expected, page in enumerate(pages):
            if page.page_id != expected or page.offset % manifest["page_size_bytes"]:
                raise StorageIntegrityError("invalid page id or unaligned offset")
            if page.size != manifest["page_size_bytes"] or page.offset + page.size > manifest["corpus_size_bytes"]:
                raise StorageIntegrityError("page lies outside corpus")
            if page.offset in offsets:
                raise StorageIntegrityError("duplicate physical page offset")
            offsets.add(page.offset)
        if len(pages) != manifest["page_count"]:
            raise StorageIntegrityError("page count mismatch")
        self._file = path.open("rb")
        self._mapping = mmap.mmap(self._file.fileno(), 0, access=mmap.ACCESS_READ)
        self._manifest = manifest
        self._pages = pages
        self._verified_pages.clear()

    def close_brain(self) -> None:
        if self._mapping is not None:
            self._mapping.close()
            self._mapping = None
        if self._file is not None:
            self._file.close()
            self._file = None
        self._manifest = None
        self._pages = ()

    def get_page(self, page_id: int, validate: bool | str = True) -> CorticalPage:
        if self._mapping is None:
            raise RuntimeError("brain is not open")
        if page_id < 0 or page_id >= len(self._pages):
            raise IndexError(f"invalid page_id: {page_id}")
        metadata = self._pages[page_id]
        view = memoryview(self._mapping)[metadata.offset:metadata.offset + metadata.size]
        self._accesses += 1
        self._logical_bytes += metadata.size
        policy = "always" if validate is True else "never" if validate is False else validate
        if policy not in ("always", "first", "never"):
            view.release()
            raise ValueError(f"unknown validation policy: {policy}")
        should_verify = policy == "always" or (policy == "first" and page_id not in self._verified_pages)
        if should_verify:
            if hashlib.sha256(view).hexdigest() != metadata.checksum:
                self._checksum_errors += 1
                view.release()
                raise StorageIntegrityError(f"checksum mismatch for page {page_id}")
            self._verified_pages.add(page_id)
        return CorticalPage(metadata, view)

    def get_extent(self, page_id: int, extent_size_bytes: int) -> memoryview:
        if self._mapping is None:
            raise RuntimeError("brain is not open")
        if page_id < 0 or page_id >= len(self._pages):
            raise IndexError(f"invalid page_id: {page_id}")
        page = self._pages[page_id]
        if extent_size_bytes < page.size or extent_size_bytes % page.size:
            raise ValueError("extent must be a multiple of logical page size")
        start = (page.offset // extent_size_bytes) * extent_size_bytes
        end = min(start + extent_size_bytes, self.manifest["corpus_size_bytes"])
        return memoryview(self._mapping)[start:end]

    def page_metadata(self, page_id: int) -> PageMetadata:
        if self._mapping is None:
            raise RuntimeError("brain is not open")
        if page_id < 0 or page_id >= len(self._pages):
            raise IndexError(f"invalid page_id: {page_id}")
        return self._pages[page_id]

    def release_page(self, page: CorticalPage) -> None:
        page.data.release()

    def stats(self) -> dict:
        return {
            "backend": "mmap",
            "accesses": self._accesses,
            "logical_bytes_requested": self._logical_bytes,
            "checksum_errors": self._checksum_errors,
            "verified_pages": len(self._verified_pages),
        }

    def __enter__(self) -> "MMapStorageBackend":
        self.open_brain()
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close_brain()


def touch_view(view: memoryview, stride_bytes: int = 4096) -> int:
    """Read one byte per base page plus the final byte; return a deterministic sink."""
    if stride_bytes < 1:
        raise ValueError("stride_bytes must be positive")
    accumulator = 0
    for offset in range(0, len(view), stride_bytes):
        accumulator = ((accumulator << 5) - accumulator) ^ view[offset]
        accumulator &= 0xFFFFFFFFFFFFFFFF
    if len(view) and (len(view) - 1) % stride_bytes:
        accumulator ^= view[-1]
    return accumulator
