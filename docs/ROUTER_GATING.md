# Thalamic Router + Basal Gating V0

## Escopo e hipótese

Hipótese da Fase 3: um índice lexical residente e um Gate por orçamento conseguem preservar alto recall ativando poucos LogicalCorticalPages, com custo muito menor que os bytes evitados. Esta fase mede seleção; o Router não responde, não usa LLM e não realiza prefetch. Não existem cache cognitivo, Hipocampo, Skills ou aprendizado.

O baseline físico está congelado em página lógica de 1 MiB, extent de 4 MiB, acesso `logical-only`, `full-extent=false`, Brain Cache zero e Linux page cache habilitado.

## Corpus cognitivo

`semantic-manifest.json` acrescenta metadados determinísticos às 1.024 páginas físicas do corpus de 1 GiB: `page_id`, domínio, tópico, palavras-chave, páginas relacionadas, tags inibitórias e importância. Nove domínios e 39 subtópicos são distribuídos de forma reproduzível pela seed 20260807. O conteúdo físico continua sintético.

O dataset contém 25 consultas com ground truth explícito: domínio, tópicos, duas páginas obrigatórias por tópico, três opcionais, sequência e turno. Ele cobre tópico único, multitópico, ambiguidade, continuação, mudança A→B→A, distractor, pista parcial e unknown/OOD.

## Contratos

`RouterBackend.route(query, cognitive_state) -> RouteResult` retorna domínios, tópicos, candidatos com score/motivo, confiança, domínios inibidos e previsões apenas registradas. `LexicalRouter` normaliza acentos, remove stopwords, consulta índice invertido e aplica score IDF/BM25-like leve. Oracle, ALL_DOMAIN, ALL_BRAIN e RANDOM_K são controles; Oracle nunca é Router real.

`GatingBackend.apply(route_result, budget, cognitive_state) -> ActivationPlan` permanece separado do Storage. `BasalGate` valida IDs, aplica inibição, threshold, top-k e máximo de MiB/páginas. Estado inicial é OFF. `CognitiveState` guarda somente domínio/tópicos, páginas recentes, força, idade, confiança e turno. Decay é 0,72 por turno; threshold de ativação e desativação são distintos. Histerese pode reservar 25% do orçamento lógico para páginas ainda persistentes; isso não força residência física.

## Métricas

- Routing Recall = obrigatórias ativadas / obrigatórias.
- Routing Precision = relevantes ativadas / ativadas.
- Required Page Miss Rate = 1 − recall.
- Circuit Activation Rate = ativadas / 1.024.
- Active Brain Size = ativadas × 1 MiB.
- Activation Churn = cardinalidade da diferença simétrica entre planos consecutivos.
- Avoided Logical Bytes = baseline − bytes ativados.
- Net Routing Benefit permanece vetor: latência/CPU do Router, páginas/bytes evitados, bytes ativados e recall. Não há score único.

Unknown sem ground truth usa recall 1 apenas como convenção matemática acompanhada de `required_count=0`; uma ativação desconhecida recebe precision zero.

## Resultado canônico

Médias sobre as 25 consultas:

| Router | Budget | Recall | Precision | Miss | Activation | Active Brain | Router p50 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Oracle | 4 MiB | 1,000 | 1,000 | 0 | 0,359% | 3,68 MiB | 0,0032 ms |
| ALL_DOMAIN | 16 MiB | 1,000 | 0,278 | 0 | 1,438% | 14,72 MiB | 0,0131 ms |
| RANDOM_K | 64 MiB | 0,980 | 0,031 | 0,020 | 6,250% | 64 MiB | 0,3401 ms |
| LEXICAL | 4 MiB | 0,880 | 0,830 | 0,120 | 0,344% | 3,52 MiB | 0,1267 ms |
| LEXICAL | 8 MiB | 0,940 | 0,590 | 0,060 | 0,688% | 7,04 MiB | 0,1258 ms |
| LEXICAL | 32 MiB | 0,960 | 0,242 | 0,040 | 2,543% | 26,04 MiB | 0,1257 ms |

O melhor Router real é LEXICAL. O ponto recomendado é 8 MiB como baseline conservador de custo, mas **não satisfaz recall próximo de 100%**: faltam 6% das páginas obrigatórias em média. Aumentar para 32/64 MiB só chega a 96%, com forte queda de precision. Oracle demonstra que o corpus exigiria em média apenas 4,84 MiB no orçamento de 8 MiB; portanto o gargalo é seleção, não capacidade física mínima.

Em 8 MiB, LEXICAL deixa 99,312% das páginas OFF e evita em média 1.016,96 MiB lógicos contra ALL_BRAIN. Isso é economia teórica de ativação, não leitura física evitada comprovada. O índice de 1K páginas mede 228.978 bytes serializados e aproximadamente 854.168 bytes como objetos Python residentes.

## Histerese e churn

Na sequência A A A A→B B B→A A com 8 MiB, stateless teve recall 1,000, precision 0,569 e churn total 128. Histerese manteve recall 1,000, reduziu churn para 98 (−23,4%) e precision para 0,556. Com 4 MiB, reduziu churn 64→48, mas recall caiu 0,944→0,889. Isso é uma regressão real: reservar estabilidade sob orçamento estreito pode bloquear uma página obrigatória. Boosts de estado sem reserva no Gate não reduziram churn nessa sequência explícita.

## Custo físico integrado

O ensaio opcional Route→Gate→mmap toca uma posição por página base de 4 KiB, sem SHA no hot path. Cada run reabre o backend e solicita `POSIX_FADV_DONTNEED`; cold continua **best-effort**. Para 36 runs LEXICAL, foram solicitados 234.881.024 bytes lógicos e atribuídos 289.144.832 bytes físicos; mediana de ponta a ponta 8,93 ms. Oracle solicitou 134.217.728 e leu 164.102.144 bytes, mediana 6,80 ms. O Router (~0,126 ms) foi pequena fração deste ensaio, mas ALL_BRAIN não foi fisicamente percorrido por consulta: não se converte o 1 GiB lógico evitado em alegação de SSD evitado.

## Cardinalidade

O screening usa postings compactos `uint32`, cinco associações por página, sem materializar corpos completos:

| Páginas | Payload postings | Peak tracemalloc | Lookup p50 |
|---:|---:|---:|---:|
| 1K | 20 KB | 45,8 KB | 0,0034 ms |
| 10K | 200 KB | 230 KB | 0,0035 ms |
| 100K | 2 MB | 2,13 MB | 0,0035 ms |
| 1M | 20 MB | 20,65 MB | 0,0037 ms |

Um cérebro de 100 GiB com páginas de 1 MiB teria aproximadamente 102.400 páginas. No formato compacto deste screening, apenas postings ficariam perto de 2,05 MB. Isso não inclui strings, documentos, objetos Python ou expansão de vocabulário; não se afirma escala linear do índice real. O índice Python atual deve ser substituído ou serializado de forma compacta antes de escalas grandes.

## Resultados negativos e limites

- LEXICAL não chegou a 100% de recall em nenhum orçamento testado.
- Ambiguidade, distractors e pistas sem estado produzem falsos negativos.
- Histerese prejudicou recall no orçamento de 4 MiB.
- RANDOM_K foi lento porque embaralha 1.024 IDs a cada consulta e permaneceu impreciso.
- O dataset sintético repete palavras dos metadados e provavelmente superestima linguagem real.
- Não houve cgroup privado de 8 GiB; o Codespace não valida hardware físico alvo.
- Linux page cache impede identificar diretamente hit versus physical SSD miss.

## Reprodução

```bash
python3 -m unittest discover -s tests -v
python3 benchmarks/phase3_benchmark.py
python3 benchmarks/analyze_phase3.py
sha256sum -c results/phase3-checksums.sha256
```

Resultados completos ficam em `results/phase3/`. Nenhum componente da Fase 4 foi iniciado.
