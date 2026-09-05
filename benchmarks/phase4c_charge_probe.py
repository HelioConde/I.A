#!/usr/bin/env python3
from __future__ import annotations

import json
import mmap
import os
from pathlib import Path

from brain_ssd.resource_pressure import ResourcePressureMonitor, numeric_delta


path = Path("/brain/brain_data/synthetic-1gib-seed-20260807/brain.dat")
monitor = ResourcePressureMonitor()
before = monitor.snapshot()
sink = 0
with path.open("rb") as stream:
    if hasattr(os, "posix_fadvise"):
        os.posix_fadvise(stream.fileno(), 0, 256 * 1024**2, os.POSIX_FADV_DONTNEED)
    with mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as mapping:
        for offset in range(0, 256 * 1024**2, 4096): sink ^= mapping[offset]
        during = monitor.snapshot()
after = monitor.snapshot()
print(json.dumps({"before": before, "during": during, "after_unmap": after,
                  "stat_delta_during": numeric_delta(before["stat"], during["stat"]),
                  "current_delta_during": during["memory_current"] - before["memory_current"], "sink": sink}, sort_keys=True))
