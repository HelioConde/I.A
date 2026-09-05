# Physical Residency — Phase 4B

## Scope

Phase 4B asks whether Phase 4A logical retention decisions become physical savings when applied to a read-only, file-backed `mmap`. It does not alter HYBRID routing, CachePolicy weights, or the trace order. It implements no prefetch, `WILLNEED`, `mlock`, anonymous page cache, `io_uring`, or `O_DIRECT`.

The layers remain separate:

1. `StorageBackend` exposes the file-backed mapping.
2. `CachePolicy` chooses logical HOT pages and eviction victims.
3. `ResidencyController` observes residency and optionally gives safe advisory hints.

`KEEP` is deliberately a no-op. No periodic touch keeps a page resident.

## Implementation

`MappedRegion` borrows the address of the existing read-only Python `mmap` through the buffer protocol. It owns no data buffer. `mincore(2)` observes base-page residency. Range boundaries are validated and aligned to the system base-page size.

Controllers:

- `KernelOnlyResidencyController`: observation only; no hint.
- `madv_cold`: `MADV_COLD` on a policy victim.
- `madv_dontneed`: `MADV_DONTNEED` on a policy victim.
- `fadv_dontneed`: `POSIX_FADV_DONTNEED` on the matching file range.
- `madv_pageout`: separate aggressive experiment using `MADV_PAGEOUT`.

Every mechanism is best-effort. A successful syscall is not interpreted as confirmed eviction; `mincore` supplies the observed result.

## Codespace API calibration

Kernel: Linux 6.8.0-1052-azure. Filesystem for `/workspaces`: ext4 on `/dev/loop4` in this container view.

One 1 MiB page was loaded, advised, observed immediately, after 20 ms and after 100 ms, then accessed again.

| Mechanism | Accepted | Resident after 100 ms | Reload physical bytes | Reload faults | Observed meaning |
|---|---:|---:|---:|---:|---|
| KernelOnly | no action | yes | 0 | 0 major | kernel retains page |
| MADV_COLD | yes | yes | 0 | 0 major | marks cold; no prompt eviction |
| MADV_DONTNEED | yes | yes | 0 | 16 minor | drops this process's PTEs, file cache remains |
| POSIX_FADV_DONTNEED | yes | yes | 0 | 0 | ineffective while the clean page remains mapped/resident |
| MADV_PAGEOUT | yes | no | 1 MiB | 1 major + 16 minor | effective physical eviction here |

`MADV_COLD` is the safe demotion hint. `MADV_PAGEOUT` is not promoted to the default; it exists solely as a controlled aggressive track.

## Methodology

- Corpus: existing 1 GiB deterministic corpus, 1,024 × 1 MiB pages.
- No 4 GiB corpus was materialized: 1 GiB already covers the required 128/256/512/1,024-page cardinalities.
- Workloads: REALISTIC_MIX, LONG_GAP_RETURN, A_TO_B_TO_A, RANDOM_TOPICS, ZIPF_TOPIC_POPULARITY and STABLE_TOPIC.
- Budgets: 8, 16, 32 and 64 MiB.
- Policies: KernelOnly, LRU, LFU, LRFU and frozen COGNITIVE_CACHE_V0.
- Physical comparisons use identical events, seeds and ordering.
- Run order is shuffled with seed `20260807`.
- Main cells have two independent processes/repetitions; medians are reported.
- Best-effort cold uses `POSIX_FADV_DONTNEED` before mapping and validates initial residency with `mincore`.
- Observability runs call `mincore` before accesses and take periodic full snapshots.
- Performance runs omit per-access `mincore`; resident/ghost/false-hot values are explicitly unavailable there.

The trace expander changes only deterministic physical page IDs to exercise the requested cardinality. It does not call or modify the Router.

## Results at 64 MiB

Aggregate physical reads across the six workloads:

| Mode | Physical reads | Major faults | Interpretation |
|---|---:|---:|---|
| KernelOnly | 966.06 MiB | 630 | best aggregate result |
| LRU + PAGEOUT | 1,018.62 MiB | 671 | 5.44% more than kernel |
| LFU + PAGEOUT | 1,048.62 MiB | 681 | worse than kernel/LRU |
| LRFU + PAGEOUT | 1,048.62 MiB | 681 | worse than kernel/LRU |
| Cognitive V0 + PAGEOUT | 1,036.00 MiB | 680 | 7.24% more than kernel; 1.71% more than LRU |

COGNITIVE_CACHE_V0 versus LRU by workload:

| Workload | LRU physical | Cognitive physical | Cognitive delta | Realized savings when logical saving was positive |
|---|---:|---:|---:|---:|
| REALISTIC_MIX | 277.06 MiB | 274.56 MiB | −2.50 MiB | 83.3% |
| LONG_GAP_RETURN | 243.13 MiB | 226.50 MiB | −16.63 MiB | 103.9% (readahead/block granularity) |
| A_TO_B_TO_A | 68.63 MiB | 68.63 MiB | 0 | n/a |
| RANDOM_TOPICS | 276.44 MiB | 275.94 MiB | −0.50 MiB | 50.0% |
| ZIPF_TOPIC_POPULARITY | 54.50 MiB | 54.50 MiB | 0 | n/a |
| STABLE_TOPIC | 98.88 MiB | 135.88 MiB | +37.00 MiB | regression |

The stable-topic regression dominates. Aggregate logical saving is −17 MiB and physical saving is −17.38 MiB, so an aggregate positive Realized Savings Ratio does not exist. The Phase 4A gain does not transfer to this expanded physical trace as a universal result.

## Budget curve

Aggregate physical reads:

| Budget | KernelOnly | LRU+PAGEOUT | Cognitive+PAGEOUT |
|---:|---:|---:|---:|
| 8 MiB | 966.06 MiB | 1,403.06 MiB | 1,338.23 MiB |
| 16 MiB | 966.06 MiB | 1,038.88 MiB | 1,047.81 MiB |
| 32 MiB | 966.06 MiB | 1,036.38 MiB | 1,102.44 MiB |
| 64 MiB | 966.06 MiB | 1,018.62 MiB | 1,036.00 MiB |

The known 16/32 MiB policy regressions remain visible. Aggressive eviction is especially damaging at 8 MiB.

## Shadow versus guided residency

In shadow mode all policies produce the same median physical reads, 160.50 MiB per run (distribution median: 168.30 MiB), because Linux alone controls residence. Median resident hit rate is 43.0%. Logical policy-hit rates differ: LRU 39.7%, LFU/LRFU 37.7%, Cognitive 38.6%.

Kernel Bonus is visible: median ghost hits range from 6.5 for LRU to 12.5 for LFU/LRFU. False HOT is zero under this unconstrained host run: Linux did not reclaim policy-HOT pages naturally.

With `MADV_PAGEOUT`, immediate eviction effectiveness is 100%; resident hit equals policy hit, ghost residency falls to zero and p95 budget overshoot is zero. This high fidelity is purchased by extra physical I/O and faults.

## Intervention and latency

Median `MADV_PAGEOUT` intervention costs across the main matrix:

- p50: 350.98 µs
- p95: 377.42 µs
- p99: 391.10 µs

Minimal-instrumentation performance medians at 64 MiB:

| Mode | Access p50 | Access p95 | Median physical read/run |
|---|---:|---:|---:|
| KernelOnly | 268.17 µs | 620.40 µs | 160.50 MiB |
| LRU + PAGEOUT | 284.32 µs | 599.18 µs | 171.00 MiB |
| Cognitive + PAGEOUT | 466.13 µs | 633.21 µs | 181.19 MiB |

The Cognitive path has material decision/intervention overhead and does not compensate with aggregate I/O savings.

## Eviction regret, return and transition

At 64 MiB over 12 runs per policy:

- LRU: 1,052 effective evictions; 12 physical regrets within 8 turns (1.14%).
- LFU/LRFU: 1,112 evictions; 96 regrets (8.63%).
- Cognitive: 1,086 evictions; 90 regrets (8.29%).

For LONG_GAP_RETURN, Cognitive physical return cost is 0 while LRU reloads about 10.06 MiB. Cognitive transition reads are 224.13 MiB versus LRU's 240.75 MiB. This is a real workload-specific win, but it cannot justify the stable-topic regression or beat KernelOnly globally.

## Residency budget fidelity and pollution

Shadow p95 overshoot is approximately 4.8 MiB at a 64 MiB logical budget: Linux usefully retains pages outside the policy set. Guided PAGEOUT p95 overshoot is zero and ghost residency is zero. This demonstrates controllability, not superiority: removing the kernel's bonus causes more reads.

Physical residency pollution is therefore not simply waste. Some COLD+resident pages become Kernel Bonus hits.

## Child cgroup

cgroup v2 is present, but `/proc/self/cgroup` is `0::/init`, `/sys/fs/cgroup` is not writable by the user, and no delegated child subtree is available. The parent has `memory.max=max`. No child cgroup was created and no parent limit was changed. Controlled hard-memory-pressure results remain unavailable in this Codespace.

## Non-duplication evidence

All page accesses remain reads from the single file-backed mapping. No page payload is stored by `ResidencyController` or `CachePolicy`. Across all 356 runs:

- median anonymous RSS growth: 1.94 MiB;
- maximum anonymous RSS growth: 2.25 MiB;
- safety threshold: 8 MiB;
- mapped file remains a 1 GiB file-backed VMA.

Growth is metadata/interpreter overhead and is not proportional to 8–64 MiB cache budgets. The non-duplication check passes.

For a conceptual 100 GiB brain (102,400 pages), Phase 4A Python-object measurements extrapolate to about 25.3 MiB for Cognitive metadata and 3.7 MiB for LRU. This is a diagnostic extrapolation, not a production representation.

## Architectural decision

Use **KernelOnly residency** as the Phase 4B winner and future baseline. Keep CachePolicy in shadow mode for telemetry and future experiments. Do not use `MADV_PAGEOUT` for routine eviction. `MADV_COLD` may remain an optional low-risk demotion hint, but this Codespace provided no evidence that it reduced I/O without real memory pressure.

Physical policy-guided reclaim should be reconsidered only in an isolated child cgroup or physical 8 GiB machine where natural reclaim actually occurs. No prefetch conclusion follows from this phase.

