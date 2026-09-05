# Phase 4E — local start status

- Start date: `2026-08-20`
- State: `PREPARATION_STARTED_PHYSICAL_MATRIX_NOT_EXECUTED`
- Freeze: `BRAIN_SSD_PHASE4D_FROZEN_2026-08-07`
- Freeze files: **31/31 verified** by `tools/start_phase4e_preflight.py`
- Qwen model: **restored and verified**
  - bytes: `639446688`
  - SHA-256: `9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031`
- llama.cpp source: **restored and verified**
  - commit: `217df17ac30ba2a8c374088772f81926cc5beee3`
- Frozen runtime binary: **not built on this host**
- Current host: `WINDOWS_PREPARATION_ONLY`, approximately 15.79 GiB RAM
- WSL/Debian: not installed
- Physical matrix: **not executed**
- TARGET_8GB: **not tested**

The existing hashed `results/phase4e/STATUS.md` was intentionally not modified. This sidecar records the new local preparation without invalidating the Phase 4E preparation checksums.

## Required next action on native Debian

From the transferred `Brain-SSD` directory:

```bash
git -C third_party/llama.cpp rev-parse HEAD
cmake -S third_party/llama.cpp -B build/llama.cpp -DGGML_CUDA=OFF -DLLAMA_CURL=OFF -DCMAKE_BUILD_TYPE=Release
cmake --build build/llama.cpp --target llama-completion -j 4
PYTHONPATH=src python3 tools/prepare_physical_validation.py
PYTHONPATH=src python3 tools/run_physical_end_to_end_validation.py --audit-only --acknowledge-physical-native
```

Only if that authoritative audit confirms a genuine native Debian machine and the intended memory/storage identity:

```bash
PYTHONPATH=src python3 tools/run_physical_end_to_end_validation.py \
  --profile physical_native \
  --acknowledge-physical-native \
  --session-queries 50 \
  --sustained-minutes 10
```

For a host larger than approximately 8 GiB, use the already documented isolated `TARGET_8GB` cgroup procedure instead of labeling the 16 GiB host as TARGET_8GB.
