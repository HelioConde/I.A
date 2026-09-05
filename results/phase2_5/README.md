# Resultados canônicos da Fase 2.5

- `integrity/summary.json`: seis sweeps SHA completos.
- `performance_matrix/summary.json`: 324 runs sem SHA no hot path.
- `validation_policy/summary.json`: always/first/performance.
- `extent_matrix/summary.json`: 216 runs logical/extent/layout.
- `analysis.json`: agregação canônica usada na documentação.

Sondas preservadas:

- `smoke-performance.json`;
- `extent-smoke-colocated.json`;
- `extent-smoke-random.json`.

Resultados anteriores permanecem em `results/phase2/`. Seus três artefatos canônicos podem ser verificados com `sha256sum -c results/phase2-canonical-checksums.sha256`.
