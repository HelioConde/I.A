# Phase 3.5 measured summary

| Strategy | Holdout recall | Precision | Median active MiB | Mean active MiB | Activation | False confidence | Decision p50/p95 ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| all_domain_evaluation | 1.0000 | 0.1266 | 189.00 | 155.71 | 15.206% | 0.00% | 0.0000/0.0000 |
| lexical_phase3_8mib | 0.8095 | 0.5357 | 8.00 | 6.10 | 0.595% | 4.76% | 0.0780/0.2242 |
| lexical_progressive_contextual | 1.0000 | 0.4872 | 8.00 | 13.71 | 1.339% | 0.00% | 0.2956/0.8054 |
| lexical_progressive_hysteresis | 1.0000 | 0.5407 | 8.00 | 15.43 | 1.507% | 0.00% | 0.2587/0.5405 |
| lexical_progressive_no_aliases | 0.8571 | 0.2604 | 32.00 | 22.95 | 2.241% | 0.00% | 0.2908/0.4808 |
| lexical_progressive_stateless | 1.0000 | 0.5407 | 8.00 | 15.43 | 1.507% | 0.00% | 0.2316/0.5287 |
| oracle | 1.0000 | 1.0000 | 5.00 | 5.00 | 0.488% | 0.00% | 0.0000/0.0000 |

## Escalation

- 0 expansions: 8/21 (38.1%)
- 1 expansions: 5/21 (23.8%)
- 2 expansions: 1/21 (4.8%)
- 3 expansions: 7/21 (33.3%)

## Fallback events

- all_domain_limited: 7
- budget_expansion: 28
- explicit_failure: 7

Physical reads are best-effort-cold observations. Recall for unknown queries uses required_count=0 and must be read together with NO_KNOWLEDGE status.
