from __future__ import annotations

import ctypes
import errno
import mmap
import os
import time
from dataclasses import dataclass, field
from typing import Protocol


_POSIX_RESIDENCY = os.name == "posix"
_LIBC = ctypes.CDLL(None, use_errno=True) if _POSIX_RESIDENCY else None
_PAGE_SIZE = os.sysconf("SC_PAGE_SIZE") if _POSIX_RESIDENCY else mmap.ALLOCATIONGRANULARITY


class _PyBuffer(ctypes.Structure):
    _fields_ = [
        ("buf", ctypes.c_void_p), ("obj", ctypes.py_object),
        ("len", ctypes.c_ssize_t), ("itemsize", ctypes.c_ssize_t),
        ("readonly", ctypes.c_int), ("ndim", ctypes.c_int),
        ("format", ctypes.c_char_p), ("shape", ctypes.POINTER(ctypes.c_ssize_t)),
        ("strides", ctypes.POINTER(ctypes.c_ssize_t)),
        ("suboffsets", ctypes.POINTER(ctypes.c_ssize_t)), ("internal", ctypes.c_void_p),
    ]


if _LIBC is not None:
    _LIBC.PyObject_GetBuffer.argtypes = [ctypes.py_object, ctypes.POINTER(_PyBuffer), ctypes.c_int]
    _LIBC.PyObject_GetBuffer.restype = ctypes.c_int
    _LIBC.PyBuffer_Release.argtypes = [ctypes.POINTER(_PyBuffer)]
    _LIBC.mincore.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_ubyte)]
    _LIBC.mincore.restype = ctypes.c_int
    _LIBC.madvise.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int]
    _LIBC.madvise.restype = ctypes.c_int


def _require_posix_residency() -> ctypes.CDLL:
    if _LIBC is None:
        raise OSError(errno.ENOTSUP, "A medição de residência de páginas requer POSIX.")
    return _LIBC


MADV_DONTNEED = getattr(mmap, "MADV_DONTNEED", 4)
MADV_COLD = getattr(mmap, "MADV_COLD", 20)
MADV_PAGEOUT = getattr(mmap, "MADV_PAGEOUT", 21)


@dataclass(frozen=True)
class MappedRegion:
    """Borrowed address of a file-backed mmap; owns no page data."""

    mapping: mmap.mmap
    address: int
    length: int
    file_descriptor: int
    buffer: _PyBuffer = field(repr=False, compare=False)

    @classmethod
    def borrow(cls, mapping: mmap.mmap, file_descriptor: int) -> "MappedRegion":
        libc = _require_posix_residency()
        buffer = _PyBuffer()
        if libc.PyObject_GetBuffer(mapping, ctypes.byref(buffer), 0) != 0:
            raise BufferError("unable to borrow mmap address")
        return cls(mapping, int(buffer.buf), int(buffer.len), file_descriptor, buffer)

    def release(self) -> None:
        _require_posix_residency().PyBuffer_Release(ctypes.byref(self.buffer))

    def aligned(self, offset: int, length: int) -> tuple[int, int]:
        if offset < 0 or length <= 0 or offset + length > self.length:
            raise ValueError("range outside mapping")
        start = (offset // _PAGE_SIZE) * _PAGE_SIZE
        end = ((offset + length + _PAGE_SIZE - 1) // _PAGE_SIZE) * _PAGE_SIZE
        return start, min(end, self.length) - start


def _raise_errno(operation: str) -> None:
    code = ctypes.get_errno()
    raise OSError(code, f"{operation}: {os.strerror(code)}")


def resident_vector(region: MappedRegion, offset: int, length: int) -> tuple[bool, ...]:
    libc = _require_posix_residency()
    start, aligned_length = region.aligned(offset, length)
    count = (aligned_length + _PAGE_SIZE - 1) // _PAGE_SIZE
    vector = (ctypes.c_ubyte * count)()
    if libc.mincore(ctypes.c_void_p(region.address + start), aligned_length, vector) != 0:
        _raise_errno("mincore")
    return tuple(bool(value & 1) for value in vector)


def resident_bytes(region: MappedRegion, offset: int = 0, length: int | None = None) -> int:
    length = region.length - offset if length is None else length
    return sum(resident_vector(region, offset, length)) * _PAGE_SIZE


class ResidencyController(Protocol):
    name: str
    def observe_access(self, page_id: int) -> bool: ...
    def keep(self, page_id: int) -> None: ...
    def demote(self, page_id: int) -> bool: ...
    def evict(self, page_id: int) -> bool: ...
    def resident(self, page_id: int) -> bool: ...
    def resident_bytes(self) -> int: ...
    def stats(self) -> dict: ...


class KernelOnlyResidencyController:
    name = "kernel_only"

    def __init__(self, region: MappedRegion, page_size: int):
        if page_size <= 0 or page_size % _PAGE_SIZE:
            raise ValueError("logical page size must align to base page size")
        self.region = region
        self.page_size = page_size
        self.calls = 0
        self.latencies_us: list[float] = []

    def _range(self, page_id: int) -> tuple[int, int]:
        offset = page_id * self.page_size
        if page_id < 0 or offset + self.page_size > self.region.length:
            raise IndexError(page_id)
        return offset, self.page_size

    def observe_access(self, page_id: int) -> bool:
        return self.resident(page_id)

    def keep(self, page_id: int) -> None:
        self._range(page_id)

    def demote(self, page_id: int) -> bool:
        self._range(page_id)
        return False

    def evict(self, page_id: int) -> bool:
        self._range(page_id)
        return False

    def resident(self, page_id: int) -> bool:
        offset, length = self._range(page_id)
        return all(resident_vector(self.region, offset, length))

    def resident_bytes(self) -> int:
        return resident_bytes(self.region)

    def stats(self) -> dict:
        ordered = sorted(self.latencies_us)
        def percentile(fraction: float) -> float:
            if not ordered:
                return 0.0
            return ordered[round((len(ordered) - 1) * fraction)]
        return {"controller": self.name, "interventions": self.calls,
                "intervention_us": {"p50": percentile(.5), "p95": percentile(.95), "p99": percentile(.99)}}


class AdvisoryResidencyController(KernelOnlyResidencyController):
    def __init__(self, region: MappedRegion, page_size: int, mode: str):
        super().__init__(region, page_size)
        if mode not in {"madv_cold", "madv_dontneed", "fadv_dontneed", "madv_pageout"}:
            raise ValueError(mode)
        self.mode = mode
        self.name = mode
        self.failures = 0

    def _advise(self, page_id: int) -> bool:
        offset, length = self._range(page_id)
        started = time.perf_counter_ns()
        try:
            if self.mode == "fadv_dontneed":
                if not hasattr(os, "posix_fadvise") or not hasattr(os, "POSIX_FADV_DONTNEED"):
                    return False
                os.posix_fadvise(self.region.file_descriptor, offset, length, os.POSIX_FADV_DONTNEED)
            else:
                advice = {"madv_cold": MADV_COLD, "madv_dontneed": MADV_DONTNEED,
                          "madv_pageout": MADV_PAGEOUT}[self.mode]
                if _require_posix_residency().madvise(ctypes.c_void_p(self.region.address + offset), length, advice) != 0:
                    _raise_errno(self.mode)
            return True
        except (OSError, AttributeError):
            self.failures += 1
            return False
        finally:
            self.calls += 1
            self.latencies_us.append((time.perf_counter_ns() - started) / 1000)

    def demote(self, page_id: int) -> bool:
        return self._advise(page_id)

    def evict(self, page_id: int) -> bool:
        return self._advise(page_id)

    def stats(self) -> dict:
        result = super().stats()
        result["failures"] = self.failures
        return result


def controller_for(mode: str, region: MappedRegion, page_size: int) -> ResidencyController:
    return KernelOnlyResidencyController(region, page_size) if mode == "kernel_only" else AdvisoryResidencyController(region, page_size, mode)

