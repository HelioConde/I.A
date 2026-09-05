# Phase 4E — Physical End-to-End Validation

## Purpose and current status

Phase 4E reproduces the frozen Phase 4D on native Debian hardware. It does not optimize retrieval, packing, context, Qwen, residency or cache policy. No physical numbers exist yet in this repository: the current Codespace was correctly classified `CODESPACE_UNCONSTRAINED`, and the physical runner refused to label it `PHYSICAL_NATIVE`.

The transfer package is ready. Its freeze identity is `BRAIN_SSD_PHASE4D_FROZEN_2026-08-07`; the cryptographic manifest is `results/phase4e/preparation/phase4d-freeze-manifest.json`. A Git tag was not created because the only `.git` belongs to the parent repository outside the authorized Brain-SSD directory.

## Frozen configuration

- Qwen3-0.6B Q8_0, model SHA-256 `9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031`;
- llama.cpp source commit `217df17ac30ba2a8c374088772f81926cc5beee3`;
- CPU only, `--device none`, four threads, 4,096 context, 96 output tokens, temperature zero;
- 1 MiB LogicalCorticalPage, 4 MiB StorageExtent, logical-only mmap;
- 2,048-token ContextBuilder;
- KernelOnly residency, Cognitive Cache shadow-only;
- no COLD/PAGEOUT, no WILLNEED and no prefetch in the canonical matrix.

## Debian preparation

Copy the complete Brain-SSD directory, including the model, source snapshots, `brain_data`, results and llama.cpp source. Do not regenerate the corpus.

Minimal Debian packages, if absent:

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-venv build-essential cmake git util-linux pciutils lm-sensors
```

No Python ML framework is required. Build the frozen llama.cpp source when the transferred binary is incompatible with the host:

```bash
git -C third_party/llama.cpp checkout 217df17ac30ba2a8c374088772f81926cc5beee3
cmake -S third_party/llama.cpp -B build/llama.cpp -DGGML_CUDA=OFF -DLLAMA_CURL=OFF -DCMAKE_BUILD_TYPE=Release
cmake --build build/llama.cpp --target llama-completion -j 4
```

Compiler-specific binary hashes may differ; source commit, runtime version and frozen command must match and are recorded in the hardware result.

## Prepare and audit

From the Brain-SSD directory:

```bash
PYTHONPATH=src python3 tools/prepare_physical_validation.py
PYTHONPATH=src python3 tools/run_physical_end_to_end_validation.py --audit-only --acknowledge-physical-native
```

Preparation validates every Phase 1–4D checksum and refuses a modified frozen file. The audit records CPU topology/frequency, RAM, swap, block model/interface/rotational flag, filesystem/mount options, kernel, Debian release, cgroup v2, governors, temperatures and explicit GPU disablement.

`prepare_physical_validation.py` also cryptographically anchors every `src/brain_ssd/*.py` core module, the model, dataset and Phase 4D build/runner inputs. The physical runner rechecks this freeze before writing any physical result and aborts on the first mismatch.

Inspect `results/phase4e/preparation/runner-audit.json`. Continue only if the machine is genuinely native Debian and storage/RAM identity is correct.

## Native execution

For a physical machine with approximately 8 GiB total RAM:

```bash
PYTHONPATH=src python3 tools/run_physical_end_to_end_validation.py \
  --profile physical_native \
  --acknowledge-physical-native \
  --session-queries 50 \
  --sustained-minutes 10
```

Add `--include-oracle` only when the optional quality-only Oracle rows are wanted. Oracle is never included implicitly in the canonical three-way matrix.

For a machine larger than 8 GiB, create a genuinely isolated cgroup/container whose `/sys/fs/cgroup/memory.max` equals exactly 8 GiB, then run:

```bash
PYTHONPATH=src python3 tools/run_physical_end_to_end_validation.py \
  --profile target_8gb --acknowledge-physical-native
```

The runner refuses `TARGET_8GB` without either an approximately 8 GiB native machine or verified `memory.max=8589934592`. It similarly refuses `LOW_4GB` without `memory.max=4294967296`. Do not change the parent cgroup or create global memory pressure.

Run LOW_4GB only after TARGET_8GB passes:

```bash
PYTHONPATH=src python3 tools/run_physical_end_to_end_validation.py \
  --profile low_4gb --acknowledge-physical-native
```

## Cold/warm methodology

For each holdout query and each Qwen-only, Standard RAG and Brain-SSD variant, the runner:

1. requests per-file best-effort eviction with `POSIX_FADV_DONTNEED`;
2. observes model and knowledge file residency with `mincore`;
3. labels the run `COLD` only when initial residency is below 5%; otherwise `BEST_EFFORT_COLD`;
4. executes the frozen pipeline;
5. immediately repeats it as `WARM` without eviction.

It never invokes global `drop_caches`. Model physical I/O is taken from the isolated llama.cpp process; knowledge physical I/O and faults are bracketed around retrieval/mmap in the parent process. Logical activated bytes remain separate. The full system sampler spans retrieval, ContextBuilder and Qwen rather than Qwen alone.

## Outputs and PASS criteria

Outputs remain separated under:

- `results/phase4e/physical_native/`;
- `results/phase4e/target_8gb/`;
- `results/phase4e/low_4gb/`.

`TARGET_8GB = PASS` requires all end-to-end runs to finish, no OOM, at least 128 MiB `MemAvailable`, measured system use within 8 GiB, quality within one holdout case (12.5 percentage points) of Phase 4D, and complete metrics. Speed does not determine PASS.

On a cgroup-limited profile, the 8 GiB decision uses measured cgroup memory rather than host-wide `MemTotal`. On a native approximately-8-GiB machine it uses host `MemTotal - MemAvailable`. Swap is observed and reported but is not counted as Brain-SSD architecture; if it is active, preserve that run as a clearly identified comparison and perform the primary no-swap run only when disabling swap is operationally safe.

Performance labels are reported separately: FUNCTIONAL for a completed run, INTERACTIVE when Brain-SSD warm median TTFT is at most 15 s, and FAST when at most 5 s. These thresholds are reporting conventions anchored to the Phase 4D ~11.7 s TTFT, not optimization targets.

The session continues until both 50 queries and 10 minutes have been reached. It records RAM growth, first-half versus second-half latency, page cache, per-core CPU, temperature, load, faults, physical bytes and per-process/system memory. Direct throttling state is reported as unavailable when the kernel does not expose it; temperature/frequency evidence remains in the audit/raw data. Any OOM, swap use, throttling, high refault rate or latency regression remains a result; configuration must not be changed mid-matrix.

Each completed profile produces `hardware.json`, `configuration.json`, `raw-runs.json`, `session-runs.json`, `summary.json`, `REPORT.md` and `checksums.json`. The report is a compact index; raw JSON remains authoritative for every requested timing, memory, I/O and quality field.

## Present limitation

Physical execution must occur on the target machine. The Codespace preparation result is not included in any physical average and cannot produce TARGET_8GB PASS/FAIL.
