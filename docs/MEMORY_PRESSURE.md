# Controlled memory pressure — Phase 4C

## Scope and frozen architecture

Phase 4C preserves the Phase 4B decision: Linux page cache owns physical residency, Cognitive Cache V0 is frozen, and `mmap` remains the storage baseline. It tests whether one-shot `MADV_COLD` hints help only when a hard, isolated cgroup is under real pressure. There is no prefetch, `WILLNEED`, `mlock`, anonymous data cache, page copy, `PAGEOUT` normal strategy, `io_uring`, or `O_DIRECT`.

Logical states and physical states are independent. `LOGICALLY COLD + PHYSICALLY RESIDENT` is **opportunistic residency**, not an error. COLD hints remain advisory and do not force eviction.

## Runtime and hard-limit proof

- Docker client/server: 29.6.1; cgroup driver `cgroupfs`; cgroup v2.
- Podman: unavailable.
- Docker hard memory/swap/CPU limits: supported.
- Container image: `python:3.12-slim`; no network during benchmark containers.
- Environment label: `CODESPACE_CONTAINER_LIMITED`.

The proof container requested 512 MiB and observed:

- `memory.max = 536870912` bytes;
- `memory.swap.max = 0`;
- touching 256 MiB after best-effort cold increased `file_mapped` by exactly 256 MiB;
- `memory.current` increased by about 257 MiB.

The first probe exposed shared-host page-cache attribution between sequential cgroups. The corrected probe applies `POSIX_FADV_DONTNEED` before mapping and repeated successfully. Only the corrected proof is canonical.

## Methodology

- Existing deterministic corpus: 1 GiB, 1,024 × 1 MiB pages.
- Traces: frozen Phase 4A activation traces, expanded deterministically to a 1,024-page physical universe.
- Working sets: 430–1,024 unique pages and roughly 2,082–2,676 accesses per run.
- Profiles: hard 512 MiB and hard 1 GiB; swap disabled; 2 CPUs for every strategy.
- Two discarded-container repetitions per cell; randomized order seed `20260807`.
- Workloads remain separate: REALISTIC_MIX, STABLE_TOPIC, LONG_GAP_RETURN, A_TO_B_TO_A, RANDOM_TOPICS, ZIPF.
- Main strategies: KernelOnly, Cognitive Shadow, LRU+COLD and Cognitive+COLD.
- One PAGEOUT negative control only.
- Additional 12-run screening: Cognitive pressure-aware COLD at 512 MiB.

No 4 GiB corpus was needed. The 1 GiB corpus exceeded the usable file cache under the 512 MiB limit and produced direct reclaim, refaults and PSI stalls.

## Pressure obtained

At 512 MiB, reclaim was genuine:

- KernelOnly aggregate `pgscan`: 1,398,225 base pages;
- `pgsteal`: 938,574 pages;
- `workingset_refault_file`: 511,540.5 pages (sum of workload medians);
- cgroup `memory.events max`: non-zero;
- median final PSI some/full avg10: 0.54/0.54;
- samples cover LOW/MODERATE/HIGH/CRITICAL as the working set grows.

At 1 GiB, nearly all samples were LOW/MODERATE. Reclaim was negligible: KernelOnly aggregate `pgscan=1,897.5`, `pgsteal=1,893.5`, zero logical refault median, zero workingset refault median. COLD strategies added about 2 MiB and two logical refaults, providing no benefit.

## Main comparison — 512 MiB

Sums of per-workload medians:

| Strategy | Physical reads | Major faults | Logical refaults | pgscan | pgsteal |
|---|---:|---:|---:|---:|---:|
| KernelOnly | 6,577.77 MiB | 4,291 | 1,855 | 1,398,225 | 938,574 |
| Cognitive Shadow | 6,587.42 MiB | 4,300.5 | 1,846 | 1,389,264 | 942,416 |
| LRU + COLD | 6,440.51 MiB | 3,756 | 1,774 | 952,828 | 902,917 |
| Cognitive + COLD | 6,436.01 MiB | 3,753.5 | 1,772 | 952,950 | 903,215.5 |
| Cognitive pressure-aware | 6,332.20 MiB | 3,738.5 | 1,669 | 895,455 | 876,190.5 |

Static Cognitive+COLD versus KernelOnly:

- physical reads: −141.76 MiB / −2.15%;
- major faults: −12.53%;
- logical refault count: −4.47%;
- pgscan: −31.85%;
- pgsteal: −3.77%;
- access p95: 1,071.30 → 1,012.65 µs.

Static Cognitive versus static LRU differs by only 4.50 MiB (0.07%). That is **Result C: the simple policy is effectively equivalent**.

Pressure-aware Cognitive versus KernelOnly:

- physical reads: −245.56 MiB / −3.73%;
- major faults: −12.88%;
- logical refaults: −10.03%;
- pgscan: −35.96%;
- pgsteal: −6.65%;
- access p95 median: 1,071.30 → 971.18 µs / −9.35%.

This is evidence for pressure-gated hints, but not enough to replace KernelOnly without native-machine replication.

## Workload results at 512 MiB

Physical reads, MiB:

| Workload | KernelOnly | LRU+COLD | Cognitive+COLD | Pressure-aware Cognitive |
|---|---:|---:|---:|---:|
| REALISTIC_MIX | 1,878.80 | 1,798.65 | 1,781.28 | **1,727.58** |
| STABLE_TOPIC | **709.00** | 718.56 | 712.63 | 722.13 |
| LONG_GAP_RETURN | 1,371.13 | 1,357.90 | 1,369.14 | **1,296.28** |
| A_TO_B_TO_A | 552.04 | 550.19 | 554.38 | **541.13** |
| RANDOM_TOPICS | 1,573.30 | **1,521.70** | 1,525.09 | 1,551.59 |
| ZIPF | 493.50 | 493.50 | 493.50 | 493.50 |

REALISTIC_MIX validates the central hypothesis under high pressure: pressure-aware Cognitive saves 151.21 MiB (8.05%) and reduces refaults from 832 to 694.5.

STABLE_TOPIC remains the sentinel failure: pressure-aware hints read 13.13 MiB more (+1.85%) and cause 225 versus 208 major faults. Any future runtime must retain a no-hint escape path.

LONG_GAP_RETURN benefits most from gating hints by pressure: 74.85 MiB less than KernelOnly. Static Cognitive saved only 1.99 MiB and lost to LRU.

## Cold-hint cost and quality

Static Cognitive+COLD:

- median COLD hints/run: 1,896;
- median calls per 1,000 accesses: 775.1;
- hint cost p50/p95/p99: 80.74/100.61/120.42 µs;
- COLD regret ≤16 turns: zero;
- COLD regret ≤32 turns: three cases across 12 runs.

Pressure-aware hint cost p50/p95/p99 is 80.69/102.21/123.52 µs. It reduces unnecessary hinting in most workloads, though its decision cadence remains experimental.

## Shadow prediction and HOT quality

Offline analysis uses future reuse only after replay; policy decisions never see it.

- 9,520 Cognitive COLD predictions;
- 42.17% were never reused;
- median reuse distance for reused COLD pages: 96 turns;
- only 18.81% returned within 32 turns;
- median future reuse distance among sampled HOT pages: 149 turns.

Under Kernel-controlled Cognitive Shadow at 512 MiB, sum of per-workload medians records 108 HOT reclaims/refaults. This confirms that advisory HOT cannot protect pages; the kernel remains sovereign. Under the COLD-guided runs, observed hot-refault median falls to zero, but causality cannot be separated perfectly from altered reclaim ordering.

`workingset_restore_file` rises strongly with COLD hints (KernelOnly 140,076 versus Cognitive 416,535.5 base pages). This counterintuitive kernel signal is preserved; it warns against interpreting lower I/O alone as a complete reclaim-quality score.

## OOM, swap and safety

- 109 matrix/screening containers completed successfully.
- OOMKilled: zero.
- `memory.events oom`: zero.
- `memory.events oom_kill`: zero.
- `memory.events max`: non-zero under pressure, as expected.
- `memory.swap.max=0`; swap did not participate.

Anonymous RSS growth across the 97 main runs:

- median: 720 KiB;
- maximum: 1.47 MiB;
- non-duplication threshold: 8 MiB;
- result: passed.

No structure stores CorticalPage payloads. Growth is small metadata/interpreter state and not proportional to the 64 MiB logical budget.

## ResourcePressureMonitor

The Glia V0 monitor is read-only and synchronous. It parses cgroup limits/stat/events, PSI and labels pressure LOW/MODERATE/HIGH/CRITICAL. It performs no linguistic reasoning, background polling or automatic policy mutation.

## Recommendation

Keep **KernelOnly as the default**. Preserve opportunistic residency and Cognitive Shadow telemetry.

Retain pressure-aware `MADV_COLD` as an experimental opt-in candidate only when all of these hold:

1. a finite trusted cgroup/native memory limit exists;
2. measured reclaim/PSI indicates HIGH or CRITICAL pressure;
3. hints are one-shot and rate-limited;
4. STABLE_TOPIC-like continuity can disable hints;
5. the gain is reproduced on TARGET_8GB native hardware.

Static Cognitive+COLD is not justified over LRU+COLD. No Phase 5 or prefetch work follows automatically.

