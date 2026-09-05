# Resultados da Fase 2

Resultados canônicos:

- `page_matrix_v2/summary.json`: 216 runs; reset local antes de cold/warm/hot.
- `working_set_v2/summary.json`: 16 runs da curva final.
- `analysis_v2.json`: agregação final usada na documentação.
- `hardware_after.json`: snapshot pós-experimento.

Preservados como resultados negativos/históricos:

- `page_matrix/`: V1; warm herdava páginas do run anterior e não representa warm parcial controlado.
- `working_set/` e `working_set_pressure/`: iterações anteriores à correção uniforme de cache state.
- `analysis.json`: análise da V1.
- `smoke-cold-4mib.json`: sonda inicial.

Nenhum arquivo da Fase 1 foi alterado pela Fase 2.
