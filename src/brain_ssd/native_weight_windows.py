"""Windows-native GGUF tensor window mapping experiment.

The wrapper uses the OS mapping and working-set APIs, but is intentionally not
a llama.cpp backend.  It proves the residency of only pages touched through
this mapping; it cannot measure or reduce residency held by another process.
"""
from __future__ import annotations
import ctypes
import mmap
import os
from dataclasses import dataclass
from pathlib import Path

from brain_ssd.gguf_inspector import GGUFInspector


def mapped_range(file_offset: int, length: int, granularity: int) -> tuple[int, int, int]:
    if file_offset < 0 or length < 1 or granularity < 1:
        raise ValueError("Invalid native mapping range.")
    base = file_offset // granularity * granularity
    return base, file_offset - base, file_offset - base + length


@dataclass(frozen=True)
class NativeWindowStats:
    mapped_bytes: int
    requested_bytes: int
    resident_pages_before: int | None
    resident_pages_after: int | None
    page_size: int


class NativeTensorWindow:
    """A copy-on-write mapping that is read-only by contract and never written."""

    def __init__(self, inspector: GGUFInspector, name: str, *, offset: int, length: int) -> None:
        if os.name != "nt":
            raise OSError("Native tensor window probe requires Windows.")
        tensor = inspector.tensor(name)
        if offset < 0 or length < 1 or offset + length > tensor.size_bytes:
            raise ValueError("Tensor window is out of bounds.")
        self.inspector, self.tensor = inspector, tensor
        self.offset, self.length = offset, length
        self._file = None
        self._mapping = None
        self._delta = 0

    def __enter__(self) -> "NativeTensorWindow":
        absolute = self.inspector.data_offset + self.tensor.offset + self.offset
        base, self._delta, mapped_length = mapped_range(absolute, self.length, mmap.ALLOCATIONGRANULARITY)
        self._file = self.inspector.path.open("rb")
        # ACCESS_COPY supplies a writable buffer address for QueryWorkingSetEx;
        # this class never writes, so the original GGUF cannot be modified.
        self._mapping = mmap.mmap(self._file.fileno(), mapped_length,
                                  access=mmap.ACCESS_COPY, offset=base)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._mapping is not None:
            self._mapping.close()
        if self._file is not None:
            self._file.close()

    def _address(self) -> int:
        if self._mapping is None:
            raise RuntimeError("Native tensor window is not open.")
        return ctypes.addressof(ctypes.c_char.from_buffer(self._mapping)) + self._delta

    def _resident_pages(self) -> int | None:
        if self._mapping is None:
            raise RuntimeError("Native tensor window is not open.")
        page = mmap.PAGESIZE
        count = (self.length + page - 1) // page

        class Entry(ctypes.Structure):
            _fields_ = [("VirtualAddress", ctypes.c_void_p), ("VirtualAttributes", ctypes.c_size_t)]
        entries = (Entry * count)()
        start = self._address()
        for index in range(count):
            entries[index].VirtualAddress = start + index * page
        try:
            from ctypes import wintypes
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            psapi = ctypes.WinDLL("psapi", use_last_error=True)
            kernel32.GetCurrentProcess.restype = wintypes.HANDLE
            psapi.QueryWorkingSetEx.argtypes = (wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t)
            psapi.QueryWorkingSetEx.restype = wintypes.BOOL
            ok = psapi.QueryWorkingSetEx(kernel32.GetCurrentProcess(), ctypes.byref(entries), ctypes.sizeof(entries))
            if not ok:
                return None
            return sum(1 for item in entries if int(item.VirtualAttributes) & 1)
        except AttributeError:
            return None

    def touch(self) -> NativeWindowStats:
        before = self._resident_pages()
        # One byte per OS page: avoids materializing a Python copy of the window.
        page = mmap.PAGESIZE
        checksum = 0
        for position in range(0, self.length, page):
            checksum ^= self._mapping[self._delta + position]
        checksum ^= self._mapping[self._delta + self.length - 1]
        _ = checksum  # retain the touches without reporting data or weights
        after = self._resident_pages()
        return NativeWindowStats(len(self._mapping), self.length, before, after, page)
