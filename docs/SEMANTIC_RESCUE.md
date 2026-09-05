# Semantic Rescue + Context Hygiene

## Escopo e hipótese

A Fase 3.75 testa se melhorar seleção antes de expandir budget preserva recall, reduz ALL_DOMAIN e aproxima memória ativa do conjunto necessário. Permanecem congelados o LEXICAL 8 MiB da Fase 3 e o Progressive Contextual da Fase 3.5. A implementação nova é `HYBRID_RETRIEVAL_V0`; nenhum dos Routers anteriores foi alterado.

O baseline físico continua LogicalCorticalPage 1 MiB, StorageExtent 4 MiB, `logical-only`, Linux page cache ligado, cache próprio e prefetch desligados. Não há embedding neural, LLM Router, Hipocampo, Skills, aprendizado, io_uring ou O_DIRECT.

## Cascata

1. `LEVEL_0_EXACT`: termos fortes e fast path;
2. `LEVEL_1_FUZZY`: aliases universais/contextuais, edit distance limitada e índice de character trigrams;
3. `LEVEL_2_CONTEXT`: modulation para query completa e expansion somente quando `partial_probability >= 0,55`;
4. `LEVEL_3_SEMANTIC`: TF-IDF ou character n-gram sobre 39 perfis de tópicos;
5. `LEVEL_4_BUDGET`: 4→8→16→32 somente se dois slots por conceito não couberem;
6. `LEVEL_5_LIMITED_DOMAIN`: safety fallback, não acionado no holdout;
7. `LEVEL_6_INSUFFICIENT`: falha explícita.

O Semantic Rescue apenas gera/reranqueia conceitos; o Gate seleciona duas páginas por conceito em round-robin. Redundância recebe penalidade e nenhum tópico obtém a segunda página antes de todos os conceitos selecionados receberem a primeira. O budget é teto, não preenchimento.

## Context hygiene

`HybridContextState` mantém por conceito `topic`, `confidence`, `age`, `support_count`, `last_seen` e `current_query_support`. Confidence decai por 0,68 a cada turno.

- Modulation: contexto somente aumenta score de tópico já suportado pela query.
- Expansion: pode introduzir no máximo um conceito e apenas para pista parcial.
- Query completa com forte tópico novo não recebe páginas antigas.
- Alias contextual exige pista linguística parcial e domínio presente no estado.

Cada página registra provenance (`CURRENT_QUERY`, `CONTEXT_BOOST`, `CONTEXT_EXPANSION`, `ALIAS`, `FUZZY_MATCH`, `SEMANTIC_RESCUE`, `MULTI_DOMAIN` ou `FALLBACK`) e evidências lexical, semantic, context, alias, fuzzy, domain, coverage, inhibition e redundancy.

## Dataset e calibração sem leak operacional

O dataset 3.75 possui 11 consultas development e 36 holdout. O holdout inclui as 21 consultas 3.5, novas paráfrases, typos, dois nearest-neighbor traps e uma conversa adversarial com cinco turnos Python seguida por Biology.

Somente development seleciona método e thresholds. A política determinística prioriza OOD safety, required recall, false stop, precision e Active Brain; empates preferem TF-IDF, threshold e margem maiores. Latência é reportada, nunca usada como desempate.

| Melhor configuração development | Recall required | Precision | Active médio | OOD safe | Custo médio |
|---|---:|---:|---:|---:|---:|
| TF-IDF, threshold 0,24, margin 0,05 | 100% | 81,82% | 2,55 MiB | 100% | 0,315 ms |
| Character n-gram, threshold 0,14, margin 0,03 | 100% | 77,27% | 2,73 MiB | 100% | 0,333 ms |

TF-IDF venceu. LSA/SVD não foi introduzido: com apenas 39 perfis e 11 exemplos development, adicionar decomposição densa não teria base experimental suficiente. Tiny embedding permaneceu opcional e não foi baixado; as duas alternativas sparse já superaram os alvos.

## Matriz holdout

| Estratégia | Recall | Precision | Active mediana/média | Activation média | False confidence | False early stop | Router p50/p95 |
|---|---:|---:|---:|---:|---:|---:|---:|
| LEXICAL 8 MiB | 75,00% | 44,10% | 8/6,00 MiB | 0,586% | 5,56% | 27,78% | 0,099/0,292 ms |
| Progressive Contextual 3.5 | 91,67% | 33,75% | 10,5/17,03 MiB | 1,663% | 0% | 0% | 0,294/0,552 ms |
| HYBRID sem semantic | 88,89% | 77,08% | 2/2,39 MiB | 0,233% | 0% | 0% | 0,107/0,580 ms |
| **HYBRID + TF-IDF** | **100%** | **86,81%** | **2/2,67 MiB** | **0,260%** | **0%** | **0%** | **0,136/0,641 ms** |
| Oracle relevante completo | 100% | 100% | 5/4,72 MiB | 0,461% | 0% | 0% | não medido |
| ALL_DOMAIN | 100% | 14,14% | 189/149,64 MiB | 14,613% | 0% | 0% | não medido |

Os números dos baselines no holdout ampliado não substituem seus resultados canônicos anteriores. HYBRID fica abaixo do “Oracle” em bytes porque o Oracle deste protocolo ativa páginas required **e optional**, enquanto HYBRID pode parar após as required; não significa superar o limite mínimo omnisciente.

Metas atendidas no corpus: recall 100%, precision >65%, média <8–10 MiB e ALL_DOMAIN 0%. Não há remaining required-page failures.

## Uso e custo da cascata

- L0 exact: 11/36;
- L1 fuzzy/alias: 16/36;
- L2 context: 2/36;
- L3 semantic: 7 resoluções finais;
- semantic layer invocada em 11/36 (30,56%);
- rescue sem expansão entre chamadas semantic: 7/11 (63,64%);
- ALL_DOMAIN: 0/36;
- fast/non-semantic: 69,44%, p50 0,069 ms, p95 0,284 ms;
- semantic slow path: 30,56%, p50 0,400 ms, p95 0,705 ms;
- custo médio ponderado observado: 0,226 ms.

O índice TF-IDF mede 11.609 bytes serializados e ~291.859 bytes residentes estimados. O índice fuzzy de trigrams mede 21.328 bytes serializados. Construção combinada: 18,4 ms, pico tracemalloc ~738 KB e incremento RSS/PSS observado ~426 KB. Tudo é carregado uma vez; consulta semantic compara perfis pré-computados.

## Contexto, aliases e fuzzy

- Context Helpful Bytes: 2.097.152;
- Context Contamination Bytes: 0;
- partial cues: recall/precision 100%, média 2 MiB;
- `mt5` (“e depois?”) recuperou 2 MiB exclusivamente por contexto;
- `sw3`, `mt3` e `mt4`: 2 MiB, recall/precision 100%, sem contaminação;
- conversa adversarial A→B: recall 100%, precision 77,78%, média 3,33 MiB; Biology abandonou Python no último turno.

Aliases: 29 expansões, 26 hits úteis e 8 falsos. Fuzzy: 8 hits úteis e 20 falsos. A seleção por conceito impediu esses falsos hits de virar falha de recall, mas eles explicam precision menor em typo/distractor.

## Unknown/OOD

Os dois unknowns e dois nearest-neighbor traps retornaram `NO_KNOWLEDGE`, zero páginas, zero ALL_DOMAIN. Semantic similarity não obriga vizinho mais próximo. Os traps continham “rede” ou “servidor” junto a música/receitas e foram rejeitados pela combinação de novelty, unknown ratio e generic-anchor detector.

## Categorias críticas

- Multi-domain: recall 100%, precision 83,33%, média 5 MiB.
- Semantic paraphrase: recall 100%, precision 90%, média 2,4 MiB.
- Typo/noise: recall 100%, precision 58,33%, média 4,67 MiB.
- Distractor: recall 100%, precision 33,33%, 6 MiB — pior caso de precision.

## Confidence raw

Pre e post-rescue confidence são registrados separadamente. No development, a curva pre-confidence não foi monotônica: o bin 0,7–0,85 teve recall pré-rescue 50%, enquanto bins inferiores chegaram a 100% em amostra pequena. Portanto confidence continua inadequada como decisão isolada. No holdout, pre-confidence correlacionou melhor, mas não autoriza substituir coverage/novelty/cascade.

## Integração Storage

36 runs por estratégia, cada um best-effort cold com mmap logical-only:

| Estratégia | Active médio | TTFA mediana | Storage mediana | Total mediana | Logical bytes | Physical bytes | Minor/Major faults |
|---|---:|---:|---:|---:|---:|---:|---:|
| HYBRID | 2,67 MiB | 4,27 ms | 5,19 ms | 5,37 ms | 100.663.296 | 122.355.712 | 1.539 / 92 |
| LEXICAL | 6,00 MiB | 4,23 ms | 8,49 ms | 8,71 ms | 226.492.416 | 276.824.064 | 3.509 / 196 |
| Progressive 3.5 | 17,03 MiB | 4,23 ms | 10,27 ms | 10,81 ms | 642.777.088 | 680.460.288 | 9.814 / 232 |

HYBRID reduziu physical reads agregados em 55,8% contra LEXICAL e 82,0% contra Progressive neste ensaio. Cold continua best-effort; não é prova direta de miss físico no SSD.

## Resultados negativos

- Character n-gram semantic teve mesma segurança/recall development, mas pior precision, memória ativa e latência que TF-IDF.
- Fuzzy produziu 20 hits falsos contra 8 úteis.
- Alias produziu 8 hits falsos.
- Semantic Rescue só resolveu 63,64% de suas chamadas sem expansão.
- 30,56% de uso semantic é menor que 100%, mas ainda alto para uma cascata ideal.
- Distractor e typo/noise continuam com precision baixa.
- Confidence development não foi monotônica.
- Resultados dependem de perfis/glosses sintéticos e não validam linguagem aberta.

## Recomendação para Fase 4

Congelar três traces: LEXICAL 8 MiB, Progressive Contextual 3.5 e HYBRID+TF-IDF 3.75. HYBRID é o candidato principal para experimentos de cache, mas qualquer ganho deve ser comparado nos mesmos traces para não confundir melhor routing com melhor residência. Manter OOD gate, provenance e baselines anteriores. Não habilitar prefetch com os semantic candidates nesta etapa.

## Reprodução

```bash
python3 -m unittest discover -s tests -v
python3 benchmarks/phase3_75_benchmark.py
python3 benchmarks/analyze_phase3_75.py
sha256sum -c results/phase3_75-checksums.sha256
```
