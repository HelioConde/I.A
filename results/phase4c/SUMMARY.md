# Phase 4C result

The Codespace supports valid isolated hard-pressure testing through Docker/cgroup v2. The corrected proof observed `memory.max=512 MiB`, swap zero, and exactly 256 MiB growth in `file_mapped` after touching 256 MiB.

At 512 MiB, Cognitive+COLD reduced physical reads by 2.15% versus KernelOnly, but was only 0.07% better than LRU+COLD. Pressure-aware Cognitive+COLD improved the aggregate by 3.73%, major faults by 12.88%, logical refaults by 10.03%, pgscan by 35.96%, and p95 access latency by 9.35% versus KernelOnly.

The gain is not universal: STABLE_TOPIC regressed by 13.13 MiB, while REALISTIC_MIX improved by 151.21 MiB and LONG_GAP_RETURN by 74.85 MiB. At 1 GiB, reclaim was negligible and COLD hints provided no benefit.

Architectural recommendation: KernelOnly remains default; pressure-aware MADV_COLD remains experimental and requires TARGET_8GB native replication. Static Cognitive is not justified over LRU.

All 109 benchmark containers completed without OOM. Swap was disabled. Anonymous RSS growth median/max was 720 KiB/1.47 MiB, confirming no page duplication.

No prefetch or Phase 5 implementation was started.

