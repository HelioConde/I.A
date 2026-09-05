# First Real End-to-End Brain-SSD MVP

## Status

`FIRST_REAL_END_TO_END_TEST = PASS`.

The passing path is `query → real content index → record candidates → page-aware gate → selective mmap pages → verified extraction → ContextBuilder → Qwen3-0.6B Q8_0 CPU-only → answer with source IDs`.

No runtime ground truth is used. Qwen uses four threads, 4,096 context, temperature zero, 96 output tokens, `--device none`, reasoning off and no warmup. Each baseline launches a separate process for isolated memory and TTFT.

## Holdout comparison

The required-fact checker is deliberately narrow; it is not a general hallucination detector.

| Variant | Required-fact quality | Median TTFT | Mean total latency | Mean generation |
|---|---:|---:|---:|---:|
| Qwen only | 25.00% | 0.862 s | 1.630 s | 50.78 tok/s |
| Standard retrieval | 43.75% | 11.688 s | 11.753 s | 31.29 tok/s |
| Brain-SSD | 43.75% | 11.667 s | 11.744 s | 30.55 tok/s |
| Oracle records | 62.50% | 2.211 s | 3.436 s | 43.76 tok/s |

Brain-SSD improved the fact score by 18.75 percentage points over Core-only. It did not beat standard RAG on quality; its demonstrated benefit is selective, page-accounted storage with semantic locality. Oracle's imperfect 62.5% exposes a separate small-Core/context-following ceiling.

## Storage and memory

Semantic Brain-SSD used mean/median active storage of 2.625/2.5 MiB per answer. Mean context was 1,719.75 estimated tokens and mean Knowledge Density 0.2432%. Canonical `read_bytes=0` and major faults=0 mean warm Linux page cache, not zero cold SSD cost.

Peak Brain-SSD Qwen process memory was RSS 1,204,232,192 bytes (1.121 GiB), PSS 1,199,662,080 (1.117 GiB), anonymous 557,088,768 (531.3 MiB), and file-backed RSS 651,255,808 (621.1 MiB). The knowledge tree is 143,417,537 bytes and frozen GGUF 639,446,688 bytes. This fits the desired process envelope but is not native 8 GB validation.

## Outcomes

Successful grounded examples:

- repeated `json.dump`: 2 MiB activated; answer correctly stated JSON is not framed and cited record `2b0a025ac1549a6b04ae5a17`;
- `SQLITE_THREADSAFE=0/1/2`: 3 MiB activated; Brain-SSD returned Single-threaded / Serialized / Multi-threaded while Core-only failed the exact mapping.

Preserved failures:

- typo-heavy SQLite busy API missed the declared record and returned `NO_KNOWLEDGE`;
- multi-document binding + locking retrieved one of two required records;
- eager-task record was retrieved, but Brain-SSD and Oracle still returned `NO_KNOWLEDGE`;
- `check_same_thread` context corrected the default, but Qwen misstated user responsibility;
- OOD `OrionDB` activated zero pages and returned `NO_KNOWLEDGE`.

Keep KernelOnly residency and semantic packing. Before prefetch, retrieval redundancy and context cost need a separately authorized phase: TTFT is dominated by the ~1.7K-token prompt, not mmap. Phase 5 remains unstarted.

