# Recall Shield + Progressive Retrieval

## Hipótese e escopo

A Fase 3.5 testa se recuperação progressiva consegue aproximar recall de 100% sem ativar normalmente mais de 1–2% do cérebro. O baseline físico continua 1 MiB lógico, extent 4 MiB, `logical-only`, Linux page cache ligado, cache próprio e prefetch desligados. O `LexicalRouter` da Fase 3 não foi modificado; a variante nova é `LexicalProgressiveRouter`.

Não há LLM no Router, embeddings, cache cognitivo, prefetch, Hipocampo, Skills, aprendizado, io_uring ou O_DIRECT.

## Pipeline

1. normalização e tabela explícita pequena de aliases;
2. decomposição por termos e conjunções;
3. detecção de conceitos e múltiplos domínios;
4. expansão contextual limitada a quatro termos do Cognitive State quando a pista é parcial;
5. ativação 4→8→16→32 MiB, parando quando coverage e representação dos conceitos são suficientes;
6. ALL_DOMAIN limitado a até três domínios candidatos, nunca ALL_BRAIN;
7. `NO_KNOWLEDGE` para unknown, ou `INSUFFICIENT_RETRIEVAL_CONFIDENCE` quando a evidência continua incompleta.

Budget é teto, não meta. Uma consulta resolvida por duas páginas usa 2 MiB mesmo no estágio de 4 MiB. A decomposição intercala páginas dos conceitos para evitar que um tópico denso ocupe todo o top-k.

## Sinais expostos

Cada decisão registra score absoluto, gap, conceitos, domínios, Query Coverage, unknown ratio, conflito de domínio, partial cue, uso de estado, estabilidade e `new_topic_score`. A confiança transparente combina coverage, conceitos, unknown ratio e conflito; os sinais originais permanecem no JSON.

Query Coverage considera termos informativos explicados pelas páginas selecionadas. Ground truth nunca entra no Router: serve somente para recall, false confidence e diagnóstico `required_page_causes_missed`.

A histerese é adaptativa por budget e confiança. Topic switch forte (`new_topic_score >= 0,75`) zera a reserva histórica. O estado continua lógico e não força residência.

## Dataset e protocolo

O dataset determinístico contém cinco queries de desenvolvimento e 21 holdout, incluindo paráfrases nunca usadas na escolha inicial dos thresholds, typos, ruído, ambiguidade, dois unknowns e duas conversas multi-turn. Resultados finais abaixo são exclusivamente holdout. O baseline LEXICAL da Fase 3 foi reexecutado no holdout novo; por isso seus 80,95% não substituem nem contradizem os 94% medidos no dataset da Fase 3.

## Resultado holdout

| Estratégia | Recall | Precision | Active MiB mediana/média | Activation média | False confidence | Decisão p50/p95 |
|---|---:|---:|---:|---:|---:|---:|
| LEXICAL Fase 3, 8 MiB | 80,95% | 53,57% | 8 / 6,10 | 0,595% | 4,76% | 0,078/0,224 ms |
| Progressive sem aliases | 85,71% | 26,04% | 32 / 22,95 | 2,241% | 0% | 0,291/0,481 ms |
| Progressive stateless | 100% | 54,07% | 8 / 15,43 | 1,507% | 0% | 0,232/0,529 ms |
| Progressive contextual | **100%** | 48,72% | **8 / 13,71** | **1,339%** | **0%** | **0,296/0,805 ms** |
| ALL_DOMAIN avaliação | 100% | 12,66% | 189 / 155,71 | 15,206% | 0% | não medido |
| Oracle | 100% | 100% | 5 / 5 | 0,488% | 0% | não medido |

O alvo experimental foi atingido neste corpus sintético: recall >=99%, false confidence zero, mediana 8 MiB, média 13,71 MiB/1,339% e decisão p95 abaixo de 1 ms. Isso não demonstra generalização para linguagem real.

O gap para Oracle é 8,71 MiB médios extras e 51,28 pontos de precision. Progressive usa aproximadamente 91,2% menos memória ativa média que ALL_DOMAIN.

## Escalation e fallback

- zero expansões: 8/21 (38,1%);
- uma: 5/21 (23,8%);
- duas: 1/21 (4,8%);
- três: 7/21 (33,3%);
- ALL_DOMAIN limitado: 7/21 (33,3%);
- explicit failure/status especial: 7 eventos, incluindo os dois unknowns seguros.

Esse fallback é frequente demais para considerar a heurística eficiente em todos os casos. O recall foi comprado, em parte, com ativações de 32 MiB.

## Estado, partial cues e topic switch

Contexto manteve recall 100% e reduziu Active Brain médio de 15,43 para 13,71 MiB frente ao progressive stateless (−11,1%). Porém precision caiu de 54,07% para 48,72%.

Nas três partial cues, todos os modos tiveram recall 100%. O estado melhorou fortemente `sw3`, de 32 para 4 MiB, mas contaminou `mt3` (2→13 MiB) e `mt4` (2→8 MiB). Portanto o ganho contextual não é uniforme. Topic switch forte zerou a reserva histórica nos testes.

## Multi-domain, paráfrase, typos e aliases

- multi-domain: recall 100%, precision 42,71%, média 19 MiB;
- paráfrases: recall 100%, precision 62,5%, média 5 MiB;
- typo/noise: recall 100%, precision 62,5%, média 5 MiB;
- aliases elevaram recall do progressive sem aliases de 85,71% para 100%, reduziram média 22,95→15,43 MiB e aumentaram precision 26,04%→54,07%.

A tabela manual funcionou neste domínio pequeno, mas possui custo de manutenção e não substitui uma camada semântica futura. Ela também gera expansões falsas quando um alias é polissêmico.

## Calibração

Todos os quatro bins de confiança tiveram recall observado de 100% após fallback. Logo a curva final não prova correlação entre confidence e sucesso: o Recall Shield tornou o desfecho plano. Confidence isolada não deve governar expansão. Coverage, conflito, status e fallback precisam continuar expostos e avaliados antes do fallback em datasets maiores.

## Integração Storage

21 runs holdout por estratégia, com `POSIX_FADV_DONTNEED` best-effort antes de cada abertura:

| Estratégia | Active média | TT first activation mediana | Storage mediana | Total mediana | Logical bytes | Physical bytes | Minor/Major faults |
|---|---:|---:|---:|---:|---:|---:|---:|
| LEXICAL 8 MiB | 6,10 MiB | 4,21 ms | 8,64 ms | 8,64 ms | 134.217.728 | 163.840.000 | 2.106 / 116 |
| Progressive contextual | 13,71 MiB | 4,38 ms | 8,82 ms | 9,29 ms | 301.989.888 | 320.733.184 | 4.622 / 120 |

O Recall Shield adicionou ~0,65 ms à mediana total e mais que dobrou bytes lógicos/físicos agregados contra o baseline de recall inferior. Cold é best-effort; physical bytes são atribuídos pelo kernel ao processo, não prova direta de miss no dispositivo.

## Resultados negativos

- precision contextual caiu para 48,72%;
- um terço do holdout chegou ao último fallback limitado;
- sete consultas ativaram 32 MiB;
- contexto contaminou duas partial cues;
- sem aliases, recall caiu para 85,71% e média excedeu 2% do cérebro;
- confidence final não pôde ser calibrada contra falhas porque o fallback eliminou todas;
- `h_storage_net`, distractor, início de multi-turn e dois topic switches ainda retornaram `INSUFFICIENT_RETRIEVAL_CONFIDENCE` apesar de recall completo;
- unknown é corretamente recusado, mas recall matemático 1 com zero requisitos nunca deve ser interpretado como conhecimento recuperado.

## Recomendação para Fase 4

Congelar dois baselines: LEXICAL 8 MiB e Progressive contextual. Antes de cache/prefetch, refinar o fallback para reduzir ativações de 32 MiB e contaminação contextual sem perder recall. Na futura Fase 4, medir cache com ambos os traces; não atribuir ao cache ganhos causados pela mudança do Router. Manter fallback explícito e ALL_DOMAIN limitado disponível como safety baseline.

## Reprodução

```bash
python3 -m unittest discover -s tests -v
python3 benchmarks/phase3_5_benchmark.py
python3 benchmarks/analyze_phase3_5.py
sha256sum -c results/phase3_5-checksums.sha256
```
