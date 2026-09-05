# WCRE-1B — Runtime Causality + Context Cost

- Status: `PASS`
- ENG-CORE-002: `SUPPORTED`
- ENG-CORE-003: `SUPPORTED`
- Frozen results preserved: `True`

## Causality medians

| Metric | A Original | B Experimental | C Persistent |
|---|---:|---:|---:|
| ttft_ms | 1034.3201999785379 | 1032.4816000065766 | 146.22549997875467 |
| total_latency_ms | 1446.938500041142 | 1447.3466000054032 | 344.50399997876957 |
| prompt_tokens_per_second | 132.63 | 129.41 | 191.05314823945122 |
| generation_tokens_per_second | 35.18 | 35.58 | 40.560341112468755 |
| cpu_time_seconds | 3.078125 | 3.125 | 1.359375 |
| working_set_bytes | 1176162304.0 | 1176137728.0 | 1206415360.0 |
| private_bytes | 913416192.0 | 913367040.0 | 620486656.0 |

## Context cost

| Requested | Actual tokens | Prompt eval ms | TTFT ms | CPU seconds |
|---:|---:|---:|---:|---:|
| 0 | 39.0 | 211.473 | 221.88480000477284 | 1.109375 |
| 128 | 180.0 | 872.149 | 882.849299989175 | 3.765625 |
| 256 | 322.0 | 1623.728 | 1650.8829000522383 | 6.8125 |
| 512 | 603.0 | 3122.741 | 3134.329400025308 | 12.796875 |
| 768 | 883.0 | 4723.269 | 4734.605100005865 | 19.1875 |
| 1024 | 1165.0 | 6649.239 | 6661.291299969889 | 26.890625 |
| 1536 | 1729.0 | 10625.433 | 10637.798200012185 | 42.890625 |
| 2048 | 2290.0 | 14994.686 | 15007.59220001055 | 60.203125 |
| 3072 | 3418.0 | 25629.745 | 25644.585500005633 | 102.78125 |

Theoretical estimate: `{'label': 'THEORETICAL_ONLY', 'brain_reference_tokens': 1963, 'synthetic_512_prompt_eval_ms': 3122.741, 'real_persistent_prompt_eval_ms': 13425.15, 'potential_prompt_eval_savings_ms': 10302.409, 'quality_preservation': 'NOT_TESTED; no future gain promised'}`

WCRE-1B only measures. Phase 4F, Phase 5 and prefetch were not started.
