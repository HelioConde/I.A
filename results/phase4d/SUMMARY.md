# Phase 4D canonical summary

- Status: `FIRST_REAL_END_TO_END_TEST = PASS`
- Sources: Python 3.14.7 and SQLite 3.53.4 official documentation snapshots
- Records: 12,521; record bytes: 15,131,094
- Each layout: 15 × 1 MiB pages; utilization mean: 96.20%
- Index: 13,882,560 serialized bytes; measured Python RSS increment: 197,120,000 bytes
- Holdout Brain semantic: Record recall 75.00%, precision 10.71%; Page recall 75.00%, precision 28.57%
- Active Brain: mean 2.625 MiB, median 2.5 MiB
- Knowledge Density: 0.2432%; context mean: 1,719.75 estimated tokens
- Semantic packing: 25% fewer mean activated page bytes than random control
- Fact quality: Qwen-only 25.00%; Standard 43.75%; Brain-SSD 43.75%; Oracle 62.50%
- Brain-SSD: median TTFT 11.667 s; mean latency 11.744 s; generation 30.55 tok/s
- Brain-SSD peak process: RSS 1.121 GiB; PSS 1.117 GiB; anon 531.3 MiB; file-backed 621.1 MiB
- Canonical physical reads: 0 bytes, explicitly classified warm Linux page cache; not a cold-SSD result
- Unknown safety: 2/2 OOD queries activated zero pages
- Tests: 66 passed in project suite; vendored llama.cpp tests excluded from the canonical command
- Prefetch/Phase 5: not started

See `retrieval-only.json`, `end-to-end.json`, `docs/REAL_KNOWLEDGE.md`, and `docs/END_TO_END_MVP.md`.

