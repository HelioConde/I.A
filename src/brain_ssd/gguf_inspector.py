"""Bounded, read-only inspection of GGUF tensor directories.

This module deliberately stops before execution: it locates byte ranges in a
GGUF file but does not decode quantized values, mmap a whole model, or call
llama.cpp.  Offsets are checked against the file before any tensor bytes are
returned.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import struct
from pathlib import Path
from typing import Any, BinaryIO

_MAGIC = b"GGUF"
_SUPPORTED_VERSIONS = frozenset({2, 3})
_DEFAULT_ALIGNMENT = 32
_MAX_METADATA = 100_000
_MAX_METADATA_ARRAY = 2_000_000
_MAX_TENSORS = 1_000_000
_MAX_DIMS = 4
_MAX_STRING = 16 * 1024 * 1024

# ggml type -> (human name, elements per block, physical bytes per block).
# The values are the serialized ggml block layouts, not nominal bit rates.
_TYPES: dict[int, tuple[str, int, int]] = {
    0: ("F32", 1, 4), 1: ("F16", 1, 2),
    2: ("Q4_0", 32, 18), 3: ("Q4_1", 32, 20),
    6: ("Q5_0", 32, 22), 7: ("Q5_1", 32, 24),
    8: ("Q8_0", 32, 34), 9: ("Q8_1", 32, 36),
    10: ("Q2_K", 256, 84), 11: ("Q3_K", 256, 110),
    12: ("Q4_K", 256, 144), 13: ("Q5_K", 256, 176),
    14: ("Q6_K", 256, 210), 15: ("Q8_K", 256, 292),
}
_FIXED_METADATA_WIDTH = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4,
                         6: 4, 7: 1, 10: 8, 11: 8, 12: 8}


class GGUFError(ValueError):
    """A malformed or intentionally unsupported GGUF structure."""


@dataclass(frozen=True)
class TensorInfo:
    name: str
    shape: tuple[int, ...]
    type_id: int
    type_name: str
    offset: int
    size_bytes: int

    @property
    def elements(self) -> int:
        return math.prod(self.shape)


def _align(value: int, alignment: int) -> int:
    return (value + alignment - 1) // alignment * alignment


class _Reader:
    def __init__(self, stream: BinaryIO, size: int) -> None:
        self.stream, self.size = stream, size

    def read(self, size: int) -> bytes:
        if size < 0 or self.stream.tell() + size > self.size:
            raise GGUFError("GGUF truncated while reading directory.")
        value = self.stream.read(size)
        if len(value) != size:
            raise GGUFError("GGUF short read.")
        return value

    def u32(self) -> int:
        return struct.unpack("<I", self.read(4))[0]

    def u64(self) -> int:
        return struct.unpack("<Q", self.read(8))[0]

    def string(self) -> str:
        length = self.u64()
        if length > _MAX_STRING:
            raise GGUFError("GGUF string exceeds safety limit.")
        try:
            return self.read(length).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise GGUFError("GGUF string is not UTF-8.") from exc

    def skip_value(self, kind: int) -> Any:
        if kind in _FIXED_METADATA_WIDTH:
            raw = self.read(_FIXED_METADATA_WIDTH[kind])
            if kind in (4, 5):
                return struct.unpack("<I", raw)[0]
            if kind in (10, 11):
                return struct.unpack("<Q", raw)[0]
            return None
        if kind == 8:
            return self.string()
        if kind == 9:
            element_kind, count = self.u32(), self.u64()
            # Tokenizer vocabularies are legitimately much larger than the
            # number of metadata *keys*.  Keep a separate finite limit.
            if count > _MAX_METADATA_ARRAY:
                raise GGUFError("GGUF metadata array exceeds safety limit.")
            width = _FIXED_METADATA_WIDTH.get(element_kind)
            if width is not None:
                self.read(width * count)
            elif element_kind == 8:
                for _ in range(count):
                    self.string()
            else:
                raise GGUFError("Unsupported nested GGUF metadata array type.")
            return None
        raise GGUFError("Unsupported GGUF metadata type.")


class GGUFInspector:
    """Parse a GGUF directory and expose bounded, immutable tensor reads."""

    def __init__(self, path: Path, *, max_tensor_bytes: int = 2 * 1024**3) -> None:
        self.path = Path(path).expanduser().resolve(strict=True)
        if not self.path.is_file():
            raise GGUFError("GGUF source must be a regular file.")
        if not 1 <= max_tensor_bytes <= 16 * 1024**3:
            raise ValueError("max_tensor_bytes is outside the safe range.")
        self._max_tensor_bytes = max_tensor_bytes
        self.version = 0
        self.alignment = _DEFAULT_ALIGNMENT
        self.data_offset = 0
        self.metadata: dict[str, Any] = {}
        self.tensors: tuple[TensorInfo, ...] = ()
        self._by_name: dict[str, TensorInfo] = {}
        self._parse()

    def _parse(self) -> None:
        size = self.path.stat().st_size
        with self.path.open("rb") as stream:
            reader = _Reader(stream, size)
            if reader.read(4) != _MAGIC:
                raise GGUFError("Not a GGUF file.")
            self.version = reader.u32()
            if self.version not in _SUPPORTED_VERSIONS:
                raise GGUFError("Unsupported GGUF version.")
            tensor_count, metadata_count = reader.u64(), reader.u64()
            if tensor_count > _MAX_TENSORS or metadata_count > _MAX_METADATA:
                raise GGUFError("GGUF directory exceeds safety limits.")
            for _ in range(metadata_count):
                key, kind = reader.string(), reader.u32()
                value = reader.skip_value(kind)
                if key == "general.alignment" and isinstance(value, int):
                    if value < 1 or value > 4096 or value & (value - 1):
                        raise GGUFError("Invalid GGUF tensor alignment.")
                    self.alignment = value
                if key in ("general.alignment", "general.architecture"):
                    self.metadata[key] = value
            raw: list[tuple[str, tuple[int, ...], int, int]] = []
            for _ in range(tensor_count):
                name, ndim = reader.string(), reader.u32()
                if not name or ndim > _MAX_DIMS:
                    raise GGUFError("Invalid GGUF tensor name or rank.")
                shape = tuple(reader.u64() for _ in range(ndim))
                if not shape or any(dimension == 0 for dimension in shape):
                    raise GGUFError("Invalid zero-sized GGUF tensor.")
                type_id, offset = reader.u32(), reader.u64()
                if type_id not in _TYPES:
                    raise GGUFError("Unsupported GGML tensor type.")
                raw.append((name, shape, type_id, offset))
            self.data_offset = _align(stream.tell(), self.alignment)
            if self.data_offset > size:
                raise GGUFError("GGUF data section lies beyond EOF.")
        tensors: list[TensorInfo] = []
        for name, shape, type_id, offset in raw:
            if offset % self.alignment:
                raise GGUFError("GGUF tensor offset is not aligned.")
            type_name, block_elements, block_bytes = _TYPES[type_id]
            elements = math.prod(shape)
            if elements % block_elements:
                raise GGUFError("Tensor shape is incompatible with its GGML block type.")
            physical = elements // block_elements * block_bytes
            start = self.data_offset + offset
            if physical > self._max_tensor_bytes or start > size or physical > size - start:
                raise GGUFError("GGUF tensor range exceeds file or safety limit.")
            if name in self._by_name:
                raise GGUFError("Duplicate GGUF tensor name.")
            tensor = TensorInfo(name, shape, type_id, type_name, offset, physical)
            self._by_name[name] = tensor
            tensors.append(tensor)
        self.tensors = tuple(tensors)

    def tensor(self, name: str) -> TensorInfo:
        try:
            return self._by_name[name]
        except KeyError as exc:
            raise KeyError("GGUF tensor not found.") from exc

    def read_tensor_window(self, name: str, *, offset: int = 0,
                           length: int | None = None) -> bytes:
        tensor = self.tensor(name)
        if offset < 0 or offset > tensor.size_bytes:
            raise ValueError("Tensor window offset is out of range.")
        length = tensor.size_bytes - offset if length is None else length
        if length < 0 or length > tensor.size_bytes - offset:
            raise ValueError("Tensor window length is out of range.")
        with self.path.open("rb", buffering=0) as stream:
            stream.seek(self.data_offset + tensor.offset + offset)
            data = stream.read(length)
        if len(data) != length:
            raise OSError("Short GGUF tensor read.")
        return data
