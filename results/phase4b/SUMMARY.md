# Phase 4B Result

**Decision: KernelOnly wins.** Logical cache-policy gains did not become an aggregate physical win under advisory/aggressive control in this Codespace.

At 64 MiB across six physical workloads:

| Strategy | Physical reads | Major faults |
|---|---:|---:|
| KernelOnly | 966.06 MiB | 630 |
| LRU + MADV_PAGEOUT | 1,018.62 MiB | 671 |
| Cognitive V0 + MADV_PAGEOUT | 1,036.00 MiB | 680 |

Cognitive beat LRU physically in REALISTIC_MIX (2.50 MiB), LONG_GAP_RETURN (16.63 MiB), and RANDOM_TOPICS (0.50 MiB), tied two workloads, and lost 37 MiB in STABLE_TOPIC. Aggregate Cognitive physical savings versus LRU: **−17.38 MiB**. Versus KernelOnly it read **69.94 MiB more**.

API calibration:

- `MADV_COLD`: accepted, page resident after 100 ms, no reload I/O.
- `MADV_DONTNEED`: accepted, page resident after 100 ms; PTE refault only.
- `POSIX_FADV_DONTNEED`: accepted, page resident after 100 ms.
- `MADV_PAGEOUT`: page nonresident immediately, 1 MiB physical reload and one major fault.

`MADV_PAGEOUT` eviction effectiveness was 100% and budget overshoot zero, but its median intervention cost was p50/p95/p99 = 350.98/377.42/391.10 µs and it removed useful Kernel Bonus pages.

No child cgroup was available. Non-duplication passed: median/max anonymous RSS growth was 1.94/2.25 MiB, far below the 8 MiB investigation threshold and not proportional to cache budget.

Full methodology and limitations: `docs/PHYSICAL_RESIDENCY.md`.

No prefetch or Phase 5 work was started.

