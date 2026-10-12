"""Bounded LRU cache for read-only GGUF tensor byte windows.

This is a host-side cache primitive for experiments.  It neither decodes GGML
blocks nor integrates with llama.cpp; callers still need a native runtime to
consume a complete tensor during a mathematical operation.
"""
from __future__ import annotations
from collections import OrderedDict
from dataclasses import dataclass

from brain_ssd.gguf_inspector import GGUFInspector

MAX_CACHE_BYTES = 256 * 1024 * 1024


@dataclass(frozen=True)
class CacheStats:
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    cached_bytes: int = 0
    peak_cached_bytes: int = 0


class TensorWindowCache:
    """Cache exact tensor windows, enforcing an explicit Python RAM budget."""

    def __init__(self, inspector: GGUFInspector, *, budget_bytes: int) -> None:
        if not 1 <= budget_bytes <= MAX_CACHE_BYTES:
            raise ValueError("Tensor cache budget is outside the safe range.")
        self.inspector = inspector
        self.budget_bytes = budget_bytes
        self._cache: OrderedDict[tuple[str, int, int], bytes] = OrderedDict()
        self._cached_bytes = 0
        self._hits = self._misses = self._evictions = self._peak = 0

    @property
    def stats(self) -> CacheStats:
        return CacheStats(self._hits, self._misses, self._evictions,
                          self._cached_bytes, self._peak)

    def read(self, name: str, *, offset: int = 0, length: int | None = None) -> bytes:
        tensor = self.inspector.tensor(name)
        length = tensor.size_bytes - offset if length is None else length
        if length < 0 or offset < 0 or offset + length > tensor.size_bytes:
            raise ValueError("Tensor window is out of range.")
        key = (name, offset, length)
        value = self._cache.get(key)
        if value is not None:
            self._cache.move_to_end(key)
            self._hits += 1
            return value
        self._misses += 1
        value = self.inspector.read_tensor_window(name, offset=offset, length=length)
        # A window larger than the budget remains correct but is deliberately
        # not retained, rather than evicting the cache and exceeding its cap.
        if len(value) > self.budget_bytes:
            return value
        while self._cache and self._cached_bytes + len(value) > self.budget_bytes:
            _, victim = self._cache.popitem(last=False)
            self._cached_bytes -= len(victim)
            self._evictions += 1
        self._cache[key] = value
        self._cached_bytes += len(value)
        self._peak = max(self._peak, self._cached_bytes)
        return value
