# Phase 4A measured summary

Development selected Cognitive weights `association`.

## Aggregate at 64 MiB

| Policy | Hit rate | Miss GiB | Evictions | Regret@8 | Pollution GiB | Churn pages | Decision p95 us | Metadata KiB |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| adaptive_2q | 0.9195 | 8.498 | 8376 | 0.0563 | 6.062 | 17078 | 2.25 | 9.72 |
| belady_oracle | 0.9764 | 2.491 | 2225 | 0.0000 | 1.391 | 4776 | 3.68 | 37.07 |
| cognitive_v0 | 0.9586 | 4.396 | 4176 | 0.0202 | 3.603 | 8678 | 87.67 | 58.40 |
| lfu | 0.9183 | 8.637 | 8518 | 0.0553 | 7.645 | 17362 | 7.64 | 8.96 |
| lrfu | 0.9189 | 8.573 | 8453 | 0.0543 | 7.292 | 17232 | 14.15 | 8.96 |
| lru | 0.9096 | 9.537 | 9440 | 0.0763 | 6.738 | 19206 | 2.14 | 8.79 |
| no_cache | 0.0000 | 114.283 | 0 | 0.0000 | 0.000 | 0 | 1.39 | 1.45 |

## Cognitive versus LRU by workload at 64 MiB

| Workload | LRU miss MiB | Cognitive miss MiB | Saved MiB | Oracle miss MiB | Gap closed |
|---|---:|---:|---:|---:|---:|
| stable_topic | 10 | 10 | 0 | 10 | n/a |
| burst | 18 | 18 | 0 | 18 | n/a |
| a_b_a | 18 | 18 | 0 | 18 | n/a |
| alternating | 8 | 8 | 0 | 8 | n/a |
| multi_domain | 16 | 16 | 0 | 16 | n/a |
| long_gap_return | 7090 | 1897 | 5193 | 1520 | 93.2% |
| random_topics | 1826 | 1811 | 15 | 625 | 1.2% |
| zipf_topic_popularity | 80 | 76 | 4 | 72 | 50.0% |
| realistic_mix | 700 | 648 | 52 | 264 | 11.9% |

This is policy simulation only. No mmap residency, page copying, mlock, or prefetch is performed.
