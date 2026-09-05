# Cognitive Cache Policy — Phase 4A

## Escopo

A Fase 4A é exclusivamente simulação de políticas sobre traces de ativação produzidos pelo HYBRID+TF-IDF congelado. Nenhuma política lê, copia, mapeia, fixa ou antecipa páginas. `KEEP`, `EVICT`, `PROMOTE` e `DEMOTE` são decisões lógicas; Linux page cache continua separado e nenhuma residência física é alterada.

Não existem cache de dados anônimo, `mlock`, prefetch, Fase 4B, Hipocampo, Skills, aprendizado ou consolidação.

## Contrato e trace

`CachePolicy` expõe `observe_access`, `choose_evictions`, `update_state` e `stats`. Ground truth required/optional aparece apenas no trace para análise e nunca é lido pelas políticas.

Trace schema v1 é JSON Lines comprimido com gzip. O header registra workload, split, turns, eventos, seed, Router e tamanhos. Cada evento contém turn/query/page/timestamp, domínio/tópicos, activation provenance, required/optional analíticos, route confidence, Cognitive State, tamanhos físico/lógico, fase, topic-transition e reload cost sintético.

Foram materializados 36 traces reproduzíveis:

- development: 500 e 1.000 turns × 9 workloads;
- holdout: 100 e 5.000 turns × 9 workloads;
- stable-topic, burst, A→B→A, alternating, multi-domain, long-gap-return, random, Zipf e realistic-mix.

Unknown gera zero evento e não altera conteúdo residente.

## Políticas

- NO_CACHE: todo acesso é miss.
- LRU: recência estrita por `OrderedDict`.
- LFU: menor frequência; desempate por acesso mais antigo e page_id.
- LRFU: `0,55*log1p(frequency) + 0,45/(1+age)`.
- Adaptive 2Q: fila recent e frequent; segundo acesso promove. É o equivalente adaptativo escolhido em vez de ARC completo, reduzindo risco de implementação incorreta.
- Cognitive V0: score explícito com recency, frequency, topic relevance, transition/coactivation, reload cost, provenance, hysteresis e age.
- Belady: Oracle offline remove a página cujo próximo uso está mais distante.

Cognitive usa associações apenas para retenção. Nunca admite uma página não solicitada.

## Calibração

Cinco conjuntos pequenos de pesos foram comparados somente nos traces development, budgets 8/16/32 MiB. A política determinística minimiza miss bytes, regret@8, pollution e nome. Venceu `association`:

```text
recency    0.18
frequency  0.16
topic      0.20
transition 0.28
reload     0.03
provenance 0.08
hysteresis 0.10
age        0.03 (penalidade)
```

Não houve ML nem busca extensa.

## Curva agregada de Miss Bytes

Nove traces holdout de 5.000 turns; valores em GiB:

| Policy | 4 MiB | 8 MiB | 16 MiB | 32 MiB | 64 MiB | 128 MiB |
|---|---:|---:|---:|---:|---:|---:|
| NO_CACHE | 114,283 | 114,283 | 114,283 | 114,283 | 114,283 | 114,283 |
| LRU | 107,290 | 88,929 | 30,800 | 16,809 | 9,537 | 0,367 |
| LFU | **94,725** | 76,274 | 28,438 | 13,264 | 8,637 | 0,367 |
| LRFU | 98,249 | 80,423 | 28,308 | **13,238** | 8,573 | 0,367 |
| Adaptive 2Q | 103,453 | 78,773 | 28,391 | 15,772 | 8,498 | 0,367 |
| Cognitive V0 | 106,856 | **78,369** | **27,409** | 13,311 | **4,396** | 0,367 |
| Belady | 77,968 | 44,193 | 16,949 | 8,854 | 2,491 | 0,367 |

Não há vencedor universal: LFU vence em 4 MiB, Cognitive em 8/16/64, LRFU em 32 e todos empatam em 128 porque o universo observado cabe. 128 MiB minimiza misses, mas é um resultado trivial. **64 MiB é o melhor compromisso experimental**: ainda pequeno frente à meta de RAM e revela ganho cognitivo relevante sem simplesmente conter todas as páginas.

## Resultado principal em 64 MiB

| Policy | Hit | Miss GiB | Evictions | Regret@8 | Pollution GiB | Churn pages | p95 decisão | Metadata |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| LRU | 90,96% | 9,537 | 9.440 | 7,63% | 6,738 | 19.206 | 2,14 µs | 8,79 KiB |
| LFU | 91,83% | 8,637 | 8.518 | 5,53% | 7,645 | 17.362 | 7,64 µs | 8,96 KiB |
| LRFU | 91,89% | 8,573 | 8.453 | 5,43% | 7,292 | 17.232 | 14,15 µs | 8,96 KiB |
| Adaptive 2Q | 91,95% | 8,498 | 8.376 | 5,63% | 6,062 | 17.078 | 2,25 µs | 9,72 KiB |
| **Cognitive V0** | **95,86%** | **4,396** | **4.176** | **2,02%** | **3,603** | **8.678** | **87,67 µs** | **58,40 KiB** |
| Belady | 97,64% | 2,491 | 2.225 | 0% | 1,391 | 4.776 | 3,68 µs | 37,07 KiB* |

*Oracle guarda a agenda futura; sua metadata não é comparável a uma policy online.

Cognitive economizou 5,141 GiB/53,9% de miss bytes versus LRU. O gap LRU→Belady era 7,046 GiB; Cognitive fechou aproximadamente 73,0% dele, restando 1,905 GiB até Oracle.

## Workloads: ganhos e regressões

Em 64 MiB, Cognitive empatou com LRU em stable, burst, A→B→A, alternating e multi-domain; ganhou:

- long-gap-return: 7.090→1.897 MiB, 93,2% do gap para Belady fechado;
- random: 1.826→1.811 MiB, ganho pequeno;
- Zipf: 80→76 MiB;
- realistic-mix: 700→648 MiB.

Não perdeu para LRU em 64 MiB. Porém perdeu em outros budgets:

- 16 MiB, A→B→A: 23→117 MiB, regressão de 94 MiB; return cost 4→6 MiB e transition cost 20→110 MiB.
- 32 MiB, realistic-mix: regressão de 60 MiB.
- 32 MiB, LRFU superou Cognitive por ~75 MiB agregados.
- 4 MiB, LFU foi 12,1 GiB melhor que Cognitive.

Logo Cognitive não substitui políticas simples universalmente.

## Return e transição

Em long-gap-return/64 MiB:

- LRU return cost 4 MiB, reactivation hit 99,68%, transition cost 7.088 MiB;
- Cognitive return cost 0, reactivation hit 100%, transition cost 1.895 MiB;
- Belady return cost 0, transition cost 1.518 MiB.

Em A→B→A com budget 32/64, todos mantiveram A e empataram. A diferença aparece em budgets estreitos, onde Cognitive pode proteger histórico errado.

## Ablation em 16 MiB

| Variante | Miss GiB | Delta vs full |
|---|---:|---:|
| Full | 27,409 | — |
| sem topic | 27,411 | +0,002 |
| sem frequency | 30,040 | +2,631 |
| sem transition | 27,433 | +0,024 |
| sem reload | 28,346 | +0,937 |
| sem hysteresis | 27,895 | +0,486 |
| sem provenance | 28,208 | +0,799 |

Frequency foi o sinal mais importante. Provenance, reload e hysteresis ajudaram. Topic e transition quase não contribuíram no holdout agregado, apesar de o conjunto `association` vencer development — um indício de overfit/baixa transferência que deve ser preservado.

Fuzzy-only recebe provenance baixo e semantic/contextual recebem prioridade moderada. A ablation de provenance piorou 0,799 GiB, oferecendo suporte mensurável à hipótese, embora os traces ainda sejam sintéticos.

## Metadata RAM

Medição com 1.000 page IDs únicos; projeção linear, excluindo dados e não linearidades do allocator:

| Policy | Medido 1K | Por página | 100K projetado | 1M projetado |
|---|---:|---:|---:|---:|
| LRU | 38.039 B | 37,4 B | 3,74 MB | 37,42 MB |
| LFU/LRFU | 118.855 B | 118,2 B | 11,82 MB | 118,16 MB |
| Adaptive 2Q | 38.217 B | 37,4 B | 3,74 MB | 37,42 MB |
| Cognitive V0 | 260.544 B | 259,4 B | 25,94 MB | 259,37 MB |

Para um cérebro de 100 GiB/≈100K páginas, ~26 MB é aceitável como experimento, mas 1M páginas exigiria otimização/representação compacta antes de produção.

## Interpretação

Cognitive V0 mostrou benefício mensurável sobre LRU em workloads relevantes, especialmente long-gap-return, com menos miss bytes, regret, pollution e churn. O custo p95 é ~41× LRU, mas permanece abaixo de 0,1 ms por decisão neste ambiente. A vantagem não é universal e os sinais topic/transition não generalizaram tão bem quanto development sugeria.

Isso justifica considerar uma Fase 4B controlada, mas **não justifica ativá-la automaticamente**. Uma implementação física deve começar pequena, manter LRU como fallback/A-B e medir residência real sem copiar páginas mmap para buffers anônimos.

## Reprodução

```bash
python3 -m unittest discover -s tests -v
python3 benchmarks/phase4a_benchmark.py
python3 benchmarks/analyze_phase4a.py
sha256sum -c results/phase4a-checksums.sha256
```

Resultados completos por workload/budget estão em `results/phase4a/matrix.json`; regret nas janelas 1/2/4/8/16 e todas as métricas exigidas permanecem no artefato bruto.
