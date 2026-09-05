# Windows Core Runtime Experiment

`WCRE-1` tests hypothesis `ENG-CORE-001`: keeping Qwen3-0.6B Q8_0 resident between requests may remove redundant model reload time without changing Brain-SSD cognition.

This is an isolated Windows runtime experiment. It is not Phase 4F, Phase 5, prefetch, or a new cognitive architecture. Phase 4E-W and every earlier baseline remain frozen.

## Architecture

Both modes expose the same `generate(prompt, config)` behavior to the local pipeline:

- `SUBPROCESS_PER_QUERY` launches the frozen `llama-completion.exe` for every request.
- `PERSISTENT_CORE` starts the official `llama-server.exe` from the same frozen llama.cpp commit, binds only to a dynamic `127.0.0.1` port, loads the same model once, and sends independent `/v1/chat/completions` requests with `cache_prompt=false`.

The experimental server is built separately in `third_party/llama.cpp/build-win-persistent`. It never replaces `third_party/llama.cpp/build-win/bin/llama-completion.exe`. CPU-only, four threads, context size 4096, temperature zero, reasoning off, the frozen prompt, and a 96-token maximum remain unchanged.

The global default remains `subprocess` until the user explicitly approves a change.

## Measurements

The runner records one-time process startup, model readiness, model load estimate, first-query TTFT, warm-session TTFT, total latency, prompt and generation throughput, CPU time, Working Set, Private Bytes, handles, threads, model loads, reload avoidance, amortized latency, cognitive signatures, quality, context hashes, NO_KNOWLEDGE behavior, cleanup, and sustained time series.

Knowledge Active Brain remains distinct from Core Resident Memory. Residency is a runtime resource cost and does not make the cognitive system more intelligent.

## Safety and lifecycle

The persistent Core is session-scoped. Normal exit, exception, timeout, Ctrl+C, and context-manager exit call shutdown. Benchmark failures remain visible; there is no silent fallback to the subprocess backend.

Each request disables prompt caching and carries only the prompt produced for that query. The server also runs with one slot, RAM prompt cache disabled, and idle-slot caching disabled. The contamination test alternates known and unknown questions to detect cross-query leakage.

## Reproduce

Quick development run:

```powershell
python tools\run_windows_core_runtime_experiment.py --all --quick
```

Canonical experiment:

```powershell
python tools\run_windows_core_runtime_experiment.py --all
```

Manual local session, subprocess baseline:

```powershell
python tools\run_local_brain_ssd.py --core-mode subprocess
```

Manual local session, persistent experimental backend:

```powershell
python tools\run_local_brain_ssd.py --core-mode persistent
```

Results are written only below `results/windows_core_runtime/`. The current measured conclusion is published in `results/windows_core_runtime/SUMMARY.md` after a complete run.

## Decision rules

The hypothesis is supported only if cognition and context are equivalent, quality has no relevant regression, cross-query leakage is absent, memory stays bounded, cleanup succeeds, and warm-session TTFT or total latency improves beyond server overhead. High resident-memory cost or weak speed gain produces a conditional or rejected recommendation. This experiment does not validate future `TARGET_8GB` suitability.

## Canonical Windows result - 2026-08-21

Matrix `matrix-20260821T091306Z-95bf26ce26` completed with operational `PASS`. `ENG-CORE-001` is `SUPPORTED`, with recommendation `KEEP` as an opt-in Windows runtime optimization. The global default remains `SUBPROCESS_PER_QUERY` pending explicit approval.

Core-only warm TTFT improved from a subprocess median of 1105.82 ms to a persistent warm median of 150.14 ms, saving 955.68 ms or 86.42%. Median per-request total latency improved from 1614.10 ms to 344.15 ms, saving 1269.94 ms or 78.68%. Persistent startup reached READY in 1150.47 ms; its measured first request reached the first token in 134.65 ms after readiness. Startup remains visible and is included in amortized results.

In the 15-query Core-only A/B, subprocess loaded the model 15 times and persistent loaded it once, avoiding 14 reloads. Persistent Working Set median was 1,181,274,112 bytes and Private Bytes median was 618,770,432 bytes. This reserves substantial RAM but used less private commit than subprocess-per-query's 913,309,696-byte median.

The complete Brain-SSD A/B preserved selected pages, Active Brain, record IDs and order, deterministic context hashes, context-token estimates, retrieval status, generation-config hashes, required facts, sources, and NO_KNOWLEDGE behavior. The adversarial known/unknown sequence reported `cross_query_context_leak=false`.

The 20-minute sustained session ran for 1205.00 seconds and completed 93 queries. It was classified `STABLE`: Working Set ended 221,368,320 bytes below its first measured request, Private Bytes grew 1,601,536 bytes, handles grew by seven, and thread count did not grow. Cleanup left zero `llama-server` processes.
