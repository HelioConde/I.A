"""Experimental read-only SSD -> RAM weight-window paging laboratory.

This is an I/O and host-memory experiment, NOT an LLM inference engine.
Pages are arbitrary byte windows (not parsed GGUF tensors). "moe" is a
synthetic access trace, not actual expert routing. No weights are modified.
"""
from __future__ import annotations

import mmap
import os
import stat
import time
import zlib
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path
from typing import Any

MODES = ("stream", "lru", "prefetch", "mmap", "full_window")
PATTERNS = ("dense", "moe", "switch")
MAX_PAGES = 1024
MAX_BUDGET_BYTES = 256 * 1024 * 1024


def make_trace(pages: int, turns: int, pattern: str, seed: int = 20261012) -> list[int]:
    """Deterministic synthetic page activations, without future-leaking hints."""
    import random

    if not 1 <= pages <= MAX_PAGES or not 1 <= turns <= 1000:
        raise ValueError("Page count or turn count out of laboratory bounds.")
    if pattern not in PATTERNS:
        raise ValueError("Invalid synthetic activation pattern.")
    rng = random.Random(seed)
    trace: list[int] = []
    core = max(1, min(2, pages // 8))
    for turn in range(turns):
        if pattern == "dense":
            trace.extend(range(pages))
        elif pattern == "moe":
            trace.extend(range(core))
            if pages > core:
                candidates = list(range(core, pages))
                # Synthetic expert locality; NOT a real MoE router.
                hot = candidates[:max(1, min(len(candidates), pages // 4))]
                for _ in range(min(3, len(candidates))):
                    trace.append(rng.choice(hot if rng.random() < .85 else candidates))
        else:
            half = max(1, pages // 2)
            segment = range(0, half) if turn % 8 < 4 else range(half, pages)
            segment = list(segment) or [0]
            trace.extend(segment[:min(5, len(segment))])
    return trace


def _rss_bytes() -> int | None:
    """Current RSS if psutil is installed or Linux /proc is available."""
    try:
        import psutil
        return int(psutil.Process().memory_info().rss)
    except (ImportError, OSError, AttributeError):
        pass
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        pass
    return None


def _io_bytes() -> int | None:
    """OS-reported physical process read bytes when available, else unknown."""
    try:
        for line in Path("/proc/self/io").read_text().splitlines():
            if line.startswith("read_bytes:"):
                return int(line.split()[1])
    except (OSError, ValueError, IndexError):
        pass
    return None


class WindowPager:
    """Read-only page cache with byte budget, optional observed-only prefetch."""

    def __init__(self, source: Path, *, offset: int, page_bytes: int,
                 pages: int, budget_bytes: int, mode: str):
        if mode not in MODES:
            raise ValueError("Unsupported paging mode.")
        if not 4 * 1024 <= page_bytes <= 16 * 1024 * 1024:
            raise ValueError("Page size must be between 4 KiB and 16 MiB.")
        if not 1 <= pages <= MAX_PAGES or offset < 0 or offset % page_bytes:
            raise ValueError("Invalid aligned weight window.")
        if not 0 <= budget_bytes <= MAX_BUDGET_BYTES:
            raise ValueError("Invalid maximum in-process byte cache.")
        if mode in ("lru", "prefetch") and budget_bytes < page_bytes:
            raise ValueError("LRU cache must hold at least one page.")
        path = Path(source).expanduser().resolve(strict=True)
        if not path.is_file() or not stat.S_ISREG(path.stat().st_mode):
            raise ValueError("Source must be an ordinary regular file.")
        size = path.stat().st_size
        if offset + (pages - 1) * page_bytes >= size:
            raise ValueError("Weight window extends beyond the file.")
        self.source = path
        self.offset = offset
        self.page_bytes = page_bytes
        self.pages = pages
        self.budget_bytes = budget_bytes
        self.mode = mode
        self._fd = None
        self._mapping = None
        self._entire: bytes | None = None
        self._cache: OrderedDict[int, bytes] = OrderedDict()
        self._cached_bytes = 0
        self._transitions: dict[int, Counter[int]] = defaultdict(Counter)
        self._previous: int | None = None
        self.stats: dict[str, int] = dict(
            demand_hits=0, demand_misses=0, demand_loads=0,
            prefetch_loads=0, evictions=0,
            bytes_requested_from_file=0, cache_bytes_peak=0,
        )

    def __enter__(self) -> "WindowPager":
        self._fd = self.source.open("rb", buffering=0)
        if self.mode == "mmap":
            self._mapping = mmap.mmap(
                self._fd.fileno(), length=0, access=mmap.ACCESS_READ)
        if self.mode == "full_window":
            # Load ONLY the selected window, never the whole model implicitly.
            size = min(self.pages * self.page_bytes,
                       self.source.stat().st_size - self.offset)
            if size > MAX_BUDGET_BYTES:
                raise ValueError("Full-window baseline exceeds 256 MiB safety ceiling.")
            self._fd.seek(self.offset)
            self._entire = self._fd.read(size)
            if len(self._entire) != size:
                raise OSError("Short read while preparing full-window baseline.")
            self.stats["bytes_requested_from_file"] += size
            self.stats["cache_bytes_peak"] = size
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._mapping is not None:
            self._mapping.close()
        if self._fd is not None:
            self._fd.close()
        self._cache.clear()
        self._entire = None

    def _read(self, page_id: int) -> bytes:
        start = self.offset + page_id * self.page_bytes
        remaining = self.source.stat().st_size - start
        size = min(self.page_bytes, remaining)
        if size <= 0:
            raise IndexError("Page outside source.")
        self._fd.seek(start)
        data = self._fd.read(size)
        if len(data) != size:
            raise OSError("Incomplete source page read.")
        self.stats["bytes_requested_from_file"] += size
        return data

    def _admit(self, page_id: int, data: bytes) -> None:
        if self.mode not in ("lru", "prefetch"):
            return
        if len(data) > self.budget_bytes:
            return
        if page_id in self._cache:
            self._cache.move_to_end(page_id)
            return
        while self._cache and self._cached_bytes + len(data) > self.budget_bytes:
            _, victim = self._cache.popitem(last=False)
            self._cached_bytes -= len(victim)
            self.stats["evictions"] += 1
        self._cache[page_id] = data
        self._cached_bytes += len(data)
        self.stats["cache_bytes_peak"] = max(
            self.stats["cache_bytes_peak"], self._cached_bytes)

    def _observed_prefetch(self, page_id: int) -> None:
        if self.mode != "prefetch":
            return
        predictions = self._transitions.get(page_id)
        if not predictions:
            return
        predicted, count = predictions.most_common(1)[0]
        if count < 2 or predicted in self._cache:
            return
        # Do not immediately evict the just used page just to prefetch.
        if self._cached_bytes + self._size(predicted) > self.budget_bytes:
            return
        self._admit(predicted, self._read(predicted))
        self.stats["prefetch_loads"] += 1

    def _size(self, page_id: int) -> int:
        return min(self.page_bytes,
                   self.source.stat().st_size - (self.offset + page_id * self.page_bytes))

    def access(self, page_id: int) -> int:
        """Return CRC32 to force touching every requested byte on all strategies."""
        if not 0 <= page_id < self.pages:
            raise IndexError("Invalid weight page ID.")
        if self.mode == "full_window":
            start = page_id * self.page_bytes
            data = memoryview(self._entire)[start:start + self._size(page_id)]
            self.stats["demand_hits"] += 1
        elif self.mode == "mmap":
            start = self.offset + page_id * self.page_bytes
            data = memoryview(self._mapping)[start:start + self._size(page_id)]
            # OS page cache manages residency; no user-space cache hit evidence.
            self.stats["demand_misses"] += 1
        else:
            hit = page_id in self._cache
            if hit:
                data = self._cache[page_id]
                self._cache.move_to_end(page_id)
                self.stats["demand_hits"] += 1
            else:
                data = self._read(page_id)
                self.stats["demand_misses"] += 1
                self.stats["demand_loads"] += 1
                self._admit(page_id, data)
        checksum = zlib.crc32(data)
        if isinstance(data, memoryview):
            data.release()
        # Online transition inference uses only previously observed requests.
        if self.mode == "prefetch":
            if self._previous is not None:
                transitions = self._transitions[self._previous]
                transitions[page_id] += 1
                if len(self._transitions) > MAX_PAGES:
                    self._transitions.pop(next(iter(self._transitions)))
            self._previous = page_id
            self._observed_prefetch(page_id)
        return checksum


def measure(source: Path, *, mode: str, pattern: str, page_bytes: int,
            pages: int, turns: int, budget_bytes: int,
            offset: int = 0, seed: int = 20261012) -> dict[str, Any]:
    """Single process/single strategy; no model inference and no OS cache reset."""
    trace = make_trace(pages, turns, pattern, seed)
    rss_before = _rss_bytes()
    io_before = _io_bytes()
    cpu_before = time.process_time()
    start = time.perf_counter()
    checksum = 0
    rss_peak = rss_before
    with WindowPager(source, offset=offset, page_bytes=page_bytes,
                     pages=pages, budget_bytes=budget_bytes, mode=mode) as pager:
        for idx, page_id in enumerate(trace):
            checksum = zlib.crc32(pager.access(page_id).to_bytes(4, "little"),
                                  checksum)
            if idx % 16 == 0:
                rss = _rss_bytes()
                if rss is not None:
                    rss_peak = max(rss_peak or 0, rss)
        stats = dict(pager.stats)
        rss = _rss_bytes()
        if rss is not None:
            rss_peak = max(rss_peak or 0, rss)
    wall = time.perf_counter() - start
    cpu = time.process_time() - cpu_before
    io_after = _io_bytes()
    return {
        "schema": 1, "type": "weight_window_io_only",
        "status": "measured", "mode": mode, "pattern": pattern,
        "turns": turns, "pages": pages, "page_bytes": page_bytes,
        "budget_bytes": budget_bytes,
        "total_requests": len(trace), "logical_requested_bytes": sum(
            min(page_bytes, max(0, Path(source).stat().st_size -
                               (offset + p * page_bytes))) for p in trace),
        "elapsed_seconds": round(wall, 6), "cpu_seconds": round(cpu, 6),
        "accesses_per_second": round(len(trace) / wall, 2) if wall else None,
        "rss_at_start_bytes": rss_before, "rss_peak_observed_bytes": rss_peak,
        "os_physical_read_bytes_delta": (
            None if io_before is None or io_after is None
            else max(0, io_after - io_before)),
        "checksum_sink": f"{checksum:08x}",
        "cache": stats,
        "notice": (
            "Benchmark de I/O sintético, NÃO inferência de Qwen: não mede "
            "tokens/s, qualidade do modelo, VRAM ou roteamento MoE real. "
            "bytes_requested_from_file são chamadas lógicas de leitura; "
            "o cache de páginas do SO pode evitar leituras físicas. "
            "rss_peak_observed é amostrado, não um limite rígido. "
            "O limite budget_bytes vale apenas para cache Python explícito."
        ),
    }
