# Fase 4E-W — Windows Native Validation

## Separação científica

`PHASE_4E_W` é a validação funcional/física experimental do Brain-SSD V0 no Windows nativo deste computador. Ela mede estabilidade, CPU, memória, latência, sessões, execução sustentada e overhead do HUD sem alterar algoritmos.

Ela **não equivale** à Fase 4E canônica:

| Trilha | Ambiente | Decisão permitida |
|---|---|---|
| 4E-W | `WINDOWS_NATIVE_FUNCTIONAL` | `PASS`, `PASS_WITH_WARNINGS`, `FAIL` ou `INCOMPLETE` para Windows |
| 4E | Debian Linux físico | `PHYSICAL_NATIVE` e `TARGET_8GB` |

Todo artefato 4E-W contém:

```text
validation_track = PHASE_4E_W
environment = WINDOWS_NATIVE_FUNCTIONAL
development_status = EXPERIMENTAL_FUNCTIONAL_RUNTIME
phase4e_valid = false
phase4e_invalid_reason = Phase 4E canonical physical baseline requires Debian/Linux native environment.
target_8gb = NOT_TESTED
```

## Preservação do V0

Router HYBRID, TF-IDF, Recall Shield, Gate, KnowledgeRecords, corpus, índice, packing, páginas de 1 MiB, extent de 4 MiB, ContextBuilder, prompt, Qwen3-0.6B Q8_0, geração, `NO_KNOWLEDGE`, mmap e backend permanecem congelados. O `llama.cpp` não é recompilado durante a matriz inicial.

O baseline anterior em `results/windows_native/first-end-to-end.json` não é modificado. A 4E-W usa somente `results/phase4ew/`.

## Runner

Visualizar a matriz sem executar:

```powershell
python tools/run_phase4ew_windows_validation.py --dry-run
python tools/run_phase4ew_windows_validation.py --dry-run --quick
```

Modos disponíveis:

```powershell
python tools/run_phase4ew_windows_validation.py --audit
python tools/run_phase4ew_windows_validation.py --core-isolation
python tools/run_phase4ew_windows_validation.py --single-shot
python tools/run_phase4ew_windows_validation.py --session
python tools/run_phase4ew_windows_validation.py --repeated-query
python tools/run_phase4ew_windows_validation.py --sustained --duration-minutes 20
python tools/run_phase4ew_windows_validation.py --hud-overhead
python tools/run_phase4ew_windows_validation.py --all
```

`--quick` reduz repetições e usa sustained de cinco minutos por padrão. Todo resultado quick recebe `canonical=false`. A matriz completa somente recebe `phase4ew_canonical=true` quando todos os conjuntos obrigatórios passam, incluindo 15 execuções Core, 5 single-shot, sessão de 10 queries, 10 repetições, sustained de pelo menos 20 minutos e as três variantes do HUD.

## Semântica de sessão

O índice, o processo Python e o mapeamento do cérebro são reutilizados dentro de session/repeated/sustained. O modelo não é reutilizado: o backend congelado `llama-completion` é single-shot e cria um filho por pergunta. Isso é medido como comportamento do baseline, não corrigido.

O trace de memória registra Working Set, Private Bytes, RAM disponível, CPU acumulada, handles, threads e contadores de transferência. `physical_read_bytes` permanece `null`. Uma amostra por segundo é usada no sustained.

## Métricas e limitações

São suportados Working Set, Private Bytes, CPU do processo, RAM disponível, I/O transfer counters, handles e threads quando expostos. PSS Linux, cgroup, PSI, pgscan, pgsteal, `mincore`, `MADV_COLD`, `MADV_PAGEOUT`, page-cache Linux, bytes físicos do SSD e temperatura não são substituídos por zero.

O runtime separa model load, prompt evaluation, generation e total conforme `common_perf_print`. AVX/AVX2/FMA/F16C/OpenMP/BLAS são registrados somente quando aparecem no `system_info` do binário.

## Estabilidade e velocidade

Velocidade não determina PASS. Os rótulos reutilizam a convenção já documentada na Fase 4E: `FAST` para TTFT mediana até 5 s, `INTERACTIVE` até 15 s e `FUNCTIONAL` acima disso. A origem do threshold é salva no resumo.

Throughput abaixo de metade do sinal histórico do Codespaces gera `PERFORMANCE_WARNING`, mas o hardware não é tratado como comparável. Baixo throughput com uso médio inferior a metade da capacidade configurada de quatro threads gera `POSSIBLE_CPU_UNDERUTILIZATION`; caso contrário, `CORE_COMPUTE_LIMITED`. É diagnóstico, não otimização.

## Resultados imutáveis

Cada run recebe timestamp, UUID, commit, hashes do runtime/modelo, hash de configuração e fingerprint do ambiente. JSONs completos são criados de modo exclusivo e nunca reescritos. Resumos derivados são publicados em:

```text
results/phase4ew/summaries/<matrix-id>.json
results/phase4ew/summaries/<matrix-id>.md
results/phase4ew/summary.json
results/phase4ew/PHASE4EW_SUMMARY.md
```

Outliers são marcados pela regra 1,5×IQR e preservados em todas as estatísticas. Falhas usam a taxonomia `STARTUP_ERROR`, `MODEL_ERROR`, `RETRIEVAL_ERROR`, `STORAGE_ERROR`, `CONTEXT_ERROR`, `CORE_ERROR`, `TIMEOUT`, `OOM`, `HUD_ERROR` e `CLEANUP_ERROR`.

Nenhuma conclusão desta fase inicia Context Compression, Fase 4F, conectividade, Scheduler, Skills, Fase 5 ou prefetch.
