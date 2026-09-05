# Phase 3.75 measured summary

Development selected `tfidf` with threshold 0.24 and margin 0.05.

| Strategy | Recall | Precision | Active median/mean MiB | Activation | False confidence | False early stop | Route p50/p95 ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| all_domain_evaluation | 1.0000 | 0.1414 | 189.00/149.64 | 14.613% | 0.00% | 0.00% | 0.0000/0.0000 |
| hybrid_best_semantic | 1.0000 | 0.8681 | 2.00/2.67 | 0.260% | 0.00% | 0.00% | 0.1359/0.6406 |
| hybrid_no_semantic | 0.8889 | 0.7708 | 2.00/2.39 | 0.233% | 0.00% | 0.00% | 0.0933/0.5381 |
| lexical_phase3_8mib | 0.7500 | 0.4410 | 8.00/6.00 | 0.586% | 5.56% | 27.78% | 0.0964/0.2907 |
| oracle | 1.0000 | 1.0000 | 5.00/4.72 | 0.461% | 0.00% | 0.00% | 0.0000/0.0000 |
| progressive_contextual_phase3_5 | 0.9167 | 0.3375 | 10.50/17.03 | 1.663% | 0.00% | 0.00% | 0.2997/0.5435 |

## Hybrid cascade

- Semantic rescue rate: 30.56%
- Rescue success without budget expansion: 63.64%
- ALL_DOMAIN rate: 0.00%
- Context helpful bytes: 2097152
- Context contamination bytes: 0
- Expected average routing cost: 0.2265 ms

Cold storage measurements remain best-effort. Unknown recall=1 only denotes zero required pages and must be read with NO_KNOWLEDGE.
