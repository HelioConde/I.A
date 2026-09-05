#!/usr/bin/env python3
from __future__ import annotations

import json
import mmap
import os
import resource
import time
from pathlib import Path

from brain_ssd.residency import MappedRegion, controller_for
from brain_ssd.system_metrics import process_io


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "brain_data/synthetic-1gib-seed-20260807/manifest-1048576.json"


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    path = MANIFEST.parent / manifest["data_file"]
    page_size = manifest["page_size_bytes"]
    results = []
    for mode in ("kernel_only", "madv_cold", "madv_dontneed", "fadv_dontneed", "madv_pageout"):
        with path.open("rb") as cold:
            if hasattr(os, "posix_fadvise"):
                os.posix_fadvise(cold.fileno(), 0, 0, os.POSIX_FADV_DONTNEED)
        file = path.open("rb"); mapping = mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_READ)
        region = MappedRegion.borrow(mapping, file.fileno())
        try:
            controller = controller_for(mode, region, page_size)
            initial = controller.resident(0)
            io0 = process_io().get("read_bytes"); faults0 = resource.getrusage(resource.RUSAGE_SELF)
            start = time.perf_counter_ns(); sink = 0
            for offset in range(0, page_size, 4096): sink ^= mapping[offset]
            load_us = (time.perf_counter_ns() - start) / 1000
            loaded = controller.resident(0)
            io1 = process_io().get("read_bytes"); faults1 = resource.getrusage(resource.RUSAGE_SELF)
            start = time.perf_counter_ns(); accepted = controller.evict(0)
            advise_us = (time.perf_counter_ns() - start) / 1000
            immediate = controller.resident(0)
            time.sleep(.02)
            delayed_20ms = controller.resident(0)
            time.sleep(.08)
            delayed_100ms = controller.resident(0)
            io2 = process_io().get("read_bytes"); faults2 = resource.getrusage(resource.RUSAGE_SELF)
            start = time.perf_counter_ns()
            for offset in range(0, page_size, 4096): sink ^= mapping[offset]
            reload_us = (time.perf_counter_ns() - start) / 1000
            io3 = process_io().get("read_bytes"); faults3 = resource.getrusage(resource.RUSAGE_SELF)
            results.append({
                "mode": mode, "initial_resident": initial, "resident_after_load": loaded,
                "advice_accepted": accepted, "resident_immediate": immediate,
                "resident_after_20ms": delayed_20ms, "resident_after_100ms": delayed_100ms,
                "load_us": load_us, "advice_us": advise_us, "reload_us": reload_us,
                "initial_load_read_bytes": io1 - io0, "post_advice_read_bytes": io2 - io1,
                "reload_read_bytes": io3 - io2,
                "initial_major_faults": faults1.ru_majflt - faults0.ru_majflt,
                "reload_major_faults": faults3.ru_majflt - faults2.ru_majflt,
                "initial_minor_faults": faults1.ru_minflt - faults0.ru_minflt,
                "reload_minor_faults": faults3.ru_minflt - faults2.ru_minflt,
                "controller_stats": controller.stats(), "sink": sink,
            })
        finally:
            region.release(); mapping.close(); file.close()
    cgroup = Path("/sys/fs/cgroup")
    delegation = {
        "v2": (cgroup / "cgroup.controllers").exists(),
        "path": Path("/proc/self/cgroup").read_text().strip(),
        "writable": os.access(cgroup, os.W_OK),
        "subtree_control": (cgroup / "cgroup.subtree_control").read_text().strip() if (cgroup / "cgroup.subtree_control").exists() else None,
        "memory_max": (cgroup / "memory.max").read_text().strip() if (cgroup / "memory.max").exists() else None,
    }
    payload = {"schema_version": 1, "page_size": page_size, "apis": results,
               "child_cgroup": delegation}
    output = ROOT / "results/phase4b/calibration.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__": main()
