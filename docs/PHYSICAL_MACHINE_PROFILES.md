# Native Debian memory-pressure profiles

Use `tools/run_memory_pressure_validation.py` on a controlled Debian Linux host. Set `BRAIN_SSD_PHYSICAL_NATIVE=1` only when the machine is genuinely native and dedicated to the test.

Profiles:

- `LOW_4GB`: conceptual validation for a 4 GiB machine. It does not claim that a container is identical to a complete 4 GiB PC.
- `TARGET_8GB`: primary Brain-SSD hardware target.

Before running, verify that the 1 GiB deterministic corpus and all phase checksums are present. Run the probe first. A result is valid only when the generated proof records the requested finite `memory.max` and at least 128 MiB of cgroup `file` growth after touching 256 MiB.

Example on native Debian with an existing Docker daemon:

```bash
BRAIN_SSD_PHYSICAL_NATIVE=1 python tools/run_memory_pressure_validation.py \
  --profiles LOW_4GB TARGET_8GB --physical-profile --repetitions 3
```

The runner disables container swap, holds CPU quota constant within each profile, randomizes run order, records OOM state, and writes JSON artifacts plus hashes. It never changes the parent cgroup and never performs global cache drops.

