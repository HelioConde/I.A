# Real Knowledge MVP — Phase 4D

## Scope and frozen boundaries

Phase 4D introduces real, attributable documents without changing the physical baseline: 1 MiB `LogicalCorticalPage`, 4 MiB `StorageExtent`, logical-only mmap access, KernelOnly residency and shadow-only Cognitive Cache. It does not prefetch, copy pages into a persistent anonymous cache, use GPU, or start Phase 5.

## Source snapshot

The offline snapshot is declared in `brain_data/real_knowledge/source-manifest.json`.

| Source | Snapshot | License | Local SHA-256 |
|---|---|---|---|
| Python documentation text archive | 3.14.7 | PSF License v2; examples additionally 0BSD | `3711ce2e47a010c9f79453695844ea174d0634349fa7e475bbdbc5cf26cc143e` |
| SQLite documentation bundle | 3.53.4 | Public domain | `a1d0f5de57485d062796ed7e67daff0758b50d00001a0f233a2c15aaf40bbdc8` |

Origins, versions, retrieval date and licenses are recorded with the files. Benchmarks require no network after ingestion.

## Deterministic ingestion format

The pipeline is `ZIP source → normalized text → configurable chunks → KnowledgeRecord → layout → 1 MiB page → manifest/index`. A record contains its source, document, title/section, terms, page, in-page offset, byte length and SHA-256. Pages remain the mmap/storage unit; no mmap is created per record.

The development configuration uses 500-byte minimum, 1,400-byte target and 2,800-byte maximum chunks. The earlier 2,400-byte target was retained as a negative screening result: long mixed-topic records harmed strict record retrieval. The final corpus has 12,521 records and 15,131,094 record bytes.

Both layouts contain exactly the same record IDs and bytes: semantic source/document locality and a random control with seed `20260807`. Each is 15 pages / 15 MiB. Mean page utilization is 96.20%, median approximately 99.94%, and mean records/page is 834.73.

## Index and retrieval

The real index is built exclusively from titles, sections and record text. It contains normalized lexical postings and sparse BM25/TF-IDF-like scoring, plus small universal aliases and bounded fuzzy rescue. Ground-truth QA IDs are not visible to the Router.

The compressed index is 13,882,560 bytes, with 58,164 terms and 12,521 records. Python prototype object overhead is not a final packed-index estimate.

The ContextBuilder receives only selected Records, deduplicates them, preserves source IDs and enforces a 2,048-token budget. Whole pages are never sent to Qwen. Document text is explicitly labelled untrusted data.

## Retrieval-only holdout

For semantic packing + page-aware Brain retrieval:

| Metric | Result |
|---|---:|
| Strict expected Record recall | 75.00% |
| Strict expected Record precision | 10.71% |
| Page recall | 75.00% |
| Page precision | 28.57% |
| Active Brain mean | 2.625 MiB |
| Active Brain median | 2.5 MiB |
| Context mean | 1,719.75 estimated tokens |
| Knowledge Density mean | 0.2432% |

“Strict” means only the predeclared ground-truth record counts as relevant. Neighboring official passages that may also answer are deliberately counted as false positives; the benchmark is not relaxed after observing output. Unknown safety passed both OOD cases with zero pages. Misses remained for the typo-heavy SQLite busy query and the busy half of a multi-document query.

## Semantic versus random packing

On identical holdout queries, semantic packing reduced mean active storage from 3.5 MiB to 2.625 MiB (25%) and improved strict Record recall from 62.5% to 75%. Physical `read_bytes` was zero in the canonical warm run because Linux already held these small files; this is a page-cache observation, not a cold-SSD claim.

The low Knowledge Density is evidence that 1 MiB is coarse for this 15 MiB corpus. Page size was not changed in this phase.

## Reproduction

```bash
PYTHONPATH=src python tools/ingest_real_knowledge.py
PYTHONPATH=src python tools/build_real_index.py
PYTHONPATH=src python tools/run_phase4d.py
PYTHONPATH=src pytest -q tests
```

Source, record and page hashes are validated. Wrong offsets, truncation or corruption fail explicitly.

