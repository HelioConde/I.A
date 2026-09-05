# Brain-SSD — Benchmarks

## Método obrigatório

Cada mudança começa com hipótese refutável e termina com `ANTES`, `DEPOIS`, `DELTA` e classificação: melhorou, piorou, neutro ou inconclusivo. Workload, prompt, versão, checksum, cgroup e resultados brutos devem ser preservados. Cache frio e quente nunca são misturados.

Reportamos amostras individuais, mediana e faixa; p95/p99 só serão tratados como percentis estatísticos quando houver amostras suficientes. Com cinco repetições, o maior valor é apenas “máximo observado”, não uma estimativa confiável de p95.

## Definições

- **TTFT**: lançamento do processo até o primeiro caractere não branco da geração. Inclui carregamento do Core no benchmark Fase 1.
- **Tokens/s**: tokens de geração por segundo reportados pelo runtime, excluindo prompt eval.
- **Latência total**: lançamento até encerramento do processo.
- **Active Brain Size**: bytes do Core, páginas, estados e estruturas cognitivas necessários à interação. RSS não é substituto formal; na Fase 1 permanece indisponível.
- **Cognitive Cache Hit**: páginas necessárias já presentes no cache HOT/WARM ÷ páginas necessárias totais.
- **Circuit Activation Rate**: capacidade ativada ÷ capacidade total elegível.
- **Knowledge I/O per Answer**: bytes de Cortical Pages transferidos do armazenamento frio para atender a resposta. Leitura do arquivo do Core não é Knowledge I/O.
- **Prefetch Hit**: bytes/páginas prefetched usados antes da expiração ÷ total prefetched.
- **Prefetch Waste**: bytes prefetched e não usados antes da expiração/evicção.

Métrica não implementável deve ser `null` com justificativa, nunca zero inventado.

## B-001 — Prova de vida CPU-only

Data: 2026-08-07.

Hipótese: um Core GGUF sub-1B completa geração local CPU-only dentro da meta de 4–5 GB RSS.

Configuração:

- Qwen3-0.6B Q8_0 GGUF oficial, 639.446.688 bytes;
- SHA-256 `9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031`;
- llama.cpp commit `217df17ac30ba2a8c374088772f81926cc5beee3` (versão 1), GCC 13.3;
- `llama-completion`, `--device none`, 1 thread, contexto 512, máximo 24 tokens, temperatura 0;
- prompt: `Responda somente com a palavra AZUL. Qual é a cor do céu em um dia limpo? /no_think`;
- ambiente com quota cgroup aproximada de 1 CPU;
- cinco execuções frias e cinco quentes.

### Resultados

| Métrica | Cache frio (mediana; faixa) | Cache quente (mediana; faixa) |
|---|---:|---:|
| Qualidade mínima | 5/5 contêm `AZUL` | 5/5 contêm `AZUL` |
| TTFT | 1302 ms; 1291–1352 | 1125 ms; 1114–1179 |
| Latência total | 1619 ms; 1568–1668 | 1466 ms; 1415–1466 |
| Geração | 26,68 tok/s; 25,22–27,13 | 26,09 tok/s; 24,01–27,01 |
| RSS máximo | 780.320.768 B; 780.238.848–780.488.704 | 780.365.824 B; 780.333.056–780.500.992 |
| CPU média (escala de 1 core) | 99,55%; 98,94–99,60 | 99,67%; 98,99–99,68 |
| Leitura física atribuída | 639.447.040 B em todas | 0 B em todas |
| Major faults | 0 | 0 |
| Minor faults | 24.811; 24.301–24.825 | 22.398; 21.888–22.911 |

Resultado: **hipótese suportada para prova de vida**. INPUT→modelo local→OUTPUT funciona sem GPU e com RSS ~0,78 GB. Isso não valida Storage Brain, cérebro ativo proporcional ou qualidade geral. O teste de qualidade é propositalmente mínimo.

Observação negativa preservada: uma primeira sonda com `llama-cli` falhou com `failed to get a free port`, pois o CLI desse commit usa transporte local interno. O benchmark passou para `llama-completion`, que executa diretamente. Outra sonda sem `/no_think` atingiu o limite ainda no raciocínio e não respondeu `AZUL`; o protocolo foi corrigido, sem alegar ganho arquitetural.

### Reproduzir

```bash
python3 -m unittest discover -s tests -v
python3 tools/hardware_audit.py --output results/hardware.json
PYTHONPATH=src python3 benchmarks/baseline.py \
  --llama-cli build/llama.cpp/bin/llama-completion \
  --model models/Qwen3-0.6B-Q8_0.gguf \
  --threads 1 --ctx-size 512 --max-tokens 24 \
  --cache-mode cold --repeat 5 \
  --output results/baseline_cold_5x.json
```

`--cache-mode cold` usa `POSIX_FADV_DONTNEED` apenas no arquivo do modelo; nunca descarta o page cache global do host.

## Plano original do B-002 (preservado para comparação)

Este foi o protocolo proposto antes da execução; os resultados efetivos aparecem na seção B-002 abaixo. Hipótese: páginas agregadas permitem um working set limitado e tornam o custo por consulta dependente das páginas ativadas, não do corpus total.

Plano:

1. corpus sintético determinístico com manifest/checksums, sem conhecimento ou modelo real;
2. tamanhos de página 4/8/16/32 MiB;
3. padrões sequencial, aleatório e conjunto quente temático;
4. primeiro mecanismo mmap/page cache; leitura explícita como controle;
5. budgets ativos 256/512 MiB e 1/2/4 GiB, nunca alocando só porque há RAM;
6. medir latência p50/p95/p99 com amostra adequada, RSS, faults, bytes/operações de I/O, hit rate, amplificação e Active Brain Size;
7. LRU será introduzido somente depois do baseline sem cache cognitivo.

Critério de prova: manter o cérebro total fixo, reduzir o orçamento ativo e observar conclusão funcional com degradação mensurável. Nenhum limiar de ganho será inventado antes da calibração.

## Limitações

O workspace é loop/ext4 virtual, não NVMe físico. Dez execuções curtas não medem qualidade ampla, energia, temperatura, p95/p99 real nem sessão persistente. `/proc/<pid>/io` mede bytes físicos atribuídos, mas não fornece latência individual de I/O. O monitor atual observa o processo do runtime; backends que criem filhos exigirão agregação futura.

## B-002 — Storage Brain V0: matriz de páginas

Data: 2026-08-07. Resultados separados em `results/phase2/`; nenhum JSON da Fase 1 foi alterado.

Hipótese: mmap permite acessar páginas de um cérebro maior que o conjunto tocado mantendo memória proporcional às páginas residentes, e granularidade troca latência por reutilização/amplificação.

Configuração:

- corpus determinístico de 1 GiB, seed `20260807`;
- páginas 4/8/16/32 MiB sobre os mesmos bytes;
- 6 workloads × 3 estados × 4 tamanhos × 3 repetições = 216 runs;
- 256 MiB lógicos solicitados por run; working set configurado 256 MiB; budget lógico 512 MiB;
- SHA-256 completo por acesso;
- best-effort cold usa fadvise local e exige mapping RSS inicial zero.

Integridade/cache evidence:

- 216/216 runs com sucesso;
- `checksum_errors = 0`;
- 72/72 runs cold aplicaram fadvise;
- 0/72 mappings cold tinham RSS não zero antes do acesso.

### Visão agregada entre workloads

Cada célula é mediana das medianas por workload; não substitui a tabela específica.

| Página | Estado | p95 por acesso | Amplificação física | Leitura física | RSS máx. | PSS máx. | File RSS | Anônimo | Throughput lógico |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 4 MiB | cold | 5,10 ms | 0,630 | 161,22 MiB | 179,74 MiB | 172,92 MiB | 169,22 MiB | 10,53 MiB | 1,023 GB/s |
| 4 MiB | warm | 4,92 ms | 0,475 | 121,72 MiB | 179,74 MiB | 172,94 MiB | 169,22 MiB | 10,53 MiB | 1,090 GB/s |
| 4 MiB | hot | 3,02 ms | 0 | 0 | 179,77 MiB | 172,95 MiB | 169,26 MiB | 10,52 MiB | 1,397 GB/s |
| 8 MiB | cold | 10,09 ms | 0,568 | 145,44 MiB | 165,59 MiB | 158,84 MiB | 155,18 MiB | 10,41 MiB | 1,047 GB/s |
| 8 MiB | warm | 9,89 ms | 0,441 | 112,94 MiB | 165,56 MiB | 158,75 MiB | 155,16 MiB | 10,40 MiB | 1,118 GB/s |
| 8 MiB | hot | 6,03 ms | 0 | 0 | 165,63 MiB | 158,83 MiB | 155,24 MiB | 10,40 MiB | 1,399 GB/s |
| 16 MiB | cold | 19,72 ms | 0,534 | 136,66 MiB | 157,55 MiB | 150,75 MiB | 147,19 MiB | 10,37 MiB | 1,061 GB/s |
| 16 MiB | warm | 19,46 ms | 0,439 | 112,41 MiB | 157,56 MiB | 150,76 MiB | 147,20 MiB | 10,37 MiB | 1,114 GB/s |
| 16 MiB | hot | 12,07 ms | 0 | 0 | 157,51 MiB | 150,73 MiB | 147,15 MiB | 10,37 MiB | 1,399 GB/s |
| 32 MiB | cold | 39,32 ms | 0,563 | 144,25 MiB | 165,54 MiB | 158,73 MiB | 155,22 MiB | 10,33 MiB | 1,062 GB/s |
| 32 MiB | warm | 37,23 ms | 0,438 | 112,12 MiB | 165,50 MiB | 158,72 MiB | 155,17 MiB | 10,33 MiB | 1,138 GB/s |
| 32 MiB | hot | 24,05 ms | 0 | 0 | 165,49 MiB | 158,73 MiB | 155,17 MiB | 10,32 MiB | 1,399 GB/s |

Amplificação abaixo de 1 é esperada quando a sequência reutiliza páginas; `logical_bytes_requested` conta cada acesso, enquanto `read_bytes` conta somente busca física.

### Vencedores por workload

| Workload | Menor cold p95 | Menor amplificação cold | Menor hot p95 |
|---|---:|---:|---:|
| Sequential | 4 MiB | empate técnico: todos 1,000488 | 4 MiB |
| Uniform random | 4 MiB | 32 MiB | 4 MiB |
| Hot-set | 4 MiB | 32 MiB | 4 MiB |
| Clustered | 4 MiB | 32 MiB | 4 MiB |
| Topic-switch | 4 MiB | 8 MiB | 4 MiB |
| Associative walk | 4 MiB | 16 MiB | 4 MiB |

Resultado: **hipótese parcialmente suportada**. mmap manteve anônimo em ~10,3–10,5 MiB e tornou file-backed proporcional às páginas únicas tocadas. O Linux page cache eliminou leitura física nos runs quentes observados. Porém a página que minimiza latência não minimiza amplificação; não existe tamanho único vencedor.

Resultado negativo: p95 cold cresceu aproximadamente com o tamanho porque checksum lê toda a página: ~5 ms (4 MiB) para ~39 ms (32 MiB). Página grande penaliza uma ativação pequena. A matriz V1 revelou que warm herdava páginas do cold anterior e foi invalidada para essa comparação. Na V2, fadvise precede todos os estados: mapping inicial foi zero em 216/216 runs, warm pré-carregou mediana de 32 MiB e ainda leu fisicamente 112–122 MiB medianos.

## B-003 — Curva de working set

Configuração: página de 8 MiB, 32 acessos (256 MiB lógicos), working set universo 64/256/512/1024 MiB, uniform-random e clustered, cold/hot. 16/16 passaram, checksum zero.

| Working set | Workload | Cold leitura/amp | Cold RSS/map residente | Cold p95 | Hot leitura | Hot p95 |
|---:|---|---:|---:|---:|---:|---:|
| 64 MiB | random | 64,19 MiB / 0,251 | 85,73 / 64 MiB | 9,69 ms | 0 | 6,07 ms |
| 64 MiB | clustered | 56,19 MiB / 0,219 | 77,68 / 56 MiB | 14,59 ms | 0 | 8,45 ms |
| 256 MiB | random | 161,75 MiB / 0,632 | 181,60 / 160 MiB | 10,28 ms | 0 | 6,05 ms |
| 512 MiB | random | 196,25 MiB / 0,767 | 213,57 / 192 MiB | 9,95 ms | 0 | 6,05 ms |
| 1024 MiB | random | 229,50 MiB / 0,896 | 245,62 / 224 MiB | 9,62 ms | 0 | 6,04 ms |
| 1024 MiB | clustered | 228,50 MiB / 0,893 | 245,52 / 224 MiB | 10,44 ms | 0 | 6,01 ms |

O RSS segue páginas únicas realmente tocadas, não o mapping virtual de 1 GiB nem o universo declarado. O teste não percorreu todo working set; ele amostrou 256 MiB lógicos. Portanto demonstra esparsidade de acesso, mas não o ponto de thrashing.

Não houve reclaim: deltas cgroup `pgscan = 0`, `pgsteal = 0`, `pgscan_direct = 0`; logo **nenhum thrashing foi observado**, mas o ambiente tinha memória abundante e não permite concluir comportamento sob 8 GB/hard limit.

## Reproduzir Fase 2

```bash
python3 tools/generate_corpus.py \
  --directory brain_data/synthetic-1gib-seed-20260807 \
  --size-gib 1 --seed 20260807 \
  --page-size-mib 4 --page-size-mib 8 --page-size-mib 16 --page-size-mib 32

PYTHONPATH=src python3 benchmarks/storage_matrix.py \
  --corpus-directory brain_data/synthetic-1gib-seed-20260807 \
  --output-directory results/phase2/page_matrix_v2 \
  --repeat 3 --logical-mib-per-run 256 \
  --working-set-mib 256 --memory-budget-mib 512
```

## B-004 — Fase 2.5: granularidade sem SHA no hot path

Resultados em `results/phase2_5/`; Fase 2 permanece intacta.

- integrity: 6 manifests, 8.064 páginas, 6 GiB verificados, 0 erros;
- performance: 324/324 runs, 256 KiB–8 MiB, seis workloads, cold/warm/hot;
- extent/locality: 216/216 runs, nove combinações, duas disposições e três modos;
- validation policy: 9/9 runs.

Principais deltas:

- 256 KiB venceu p95 e Activation Cost em todos os workloads;
- 4 MiB caiu de 5,103 ms p95 com integrity para 2,384 ms performance (-53,3%);
- 8 MiB caiu de 10,088 para 4,761 ms (-52,8%);
- 1 MiB oferece o joelho recomendado: 0,692 ms cold p95, amplificação 0,647 e manifest 281 KB;
- full extent colocalizado reduziu I/O frente ao random, mas continuou pior que logical-only;
- no topic-switch 512 KiB/8 MiB/full-extent, retorno A2 reduziu I/O 82,3% colocalizado versus 24,0% random;
- o menor Activation score absoluto ocorreu em 256 KiB logical-only/colocated associative: 0,658.

Metodologia, tabelas completas, Useful Byte Ratio, regressões e limitações estão em [STORAGE_REFINEMENT.md](STORAGE_REFINEMENT.md). Artefato canônico: `results/phase2_5/analysis.json`.

Reprodução:

```bash
PYTHONPATH=src python3 benchmarks/integrity_matrix.py \
  --corpus-directory brain_data/synthetic-1gib-seed-20260807 \
  --output-directory results/phase2_5/integrity

PYTHONPATH=src python3 benchmarks/storage_matrix.py \
  --corpus-directory brain_data/synthetic-1gib-seed-20260807 \
  --output-directory results/phase2_5/performance_matrix \
  --repeat 3 --validation-mode performance \
  --page-size-mib .25 --page-size-mib .5 --page-size-mib 1 \
  --page-size-mib 2 --page-size-mib 4 --page-size-mib 8

PYTHONPATH=src python3 benchmarks/extent_matrix.py \
  --corpus-directory brain_data/synthetic-1gib-seed-20260807 \
  --output-directory results/phase2_5/extent_matrix --repeat 2
```

## B-005 — Fase 3: Router + Gate isolados

Matriz canônica: 4 Routers × 5 orçamentos × 25 consultas = 500 registros, com 31 repetições internas de Router por registro. LEXICAL em 8 MiB: recall 0,940, precision 0,590, miss 0,060, Active Brain 7,04 MiB, Activation Rate 0,688%, 1.016,96 MiB lógicos evitados e p50 ~0,126 ms. Oracle em 8 MiB: recall/precision 1,0 e 4,84 MiB ativos.

Topic-switch: em 8 MiB, histerese reduziu churn 128→98 (−23,4%) mantendo recall 1,0; em 4 MiB reduziu churn 64→48, mas piorou recall 0,944→0,889. Screening cardinalidade mediu postings compactos de 20 bytes/página e lookup p50 ~0,0034–0,0037 ms entre 1K e 1M páginas.

O ensaio físico é best-effort cold e não prova miss de SSD. Detalhes, limites e reprodução: [ROUTER_GATING.md](ROUTER_GATING.md). Artefatos: `results/phase3/`.

## B-006 — Fase 3.5: Recall Shield

Holdout separado de 21 consultas. Progressive contextual obteve recall 1,0, precision 0,4872, false confidence zero, Active Brain mediano 8 MiB/médio 13,71 MiB, Activation Rate médio 1,339% e decisão p50/p95 0,296/0,805 ms. LEXICAL 8 MiB no mesmo holdout: recall 0,8095 e false confidence 4,76%.

Escalation: 38,1% sem expansão, 23,8% uma, 4,8% duas e 33,3% três; ALL_DOMAIN limitado foi usado em 7/21. Aliases elevaram recall de 85,71% para 100%. Contexto reduziu memória média 11,1% contra stateless, mas reduziu precision e contaminou duas partial cues.

Integração: Progressive leu 301.989.888 bytes lógicos e 320.733.184 físicos, contra 134.217.728/163.840.000 do LEXICAL; mediana total 9,29 vs 8,64 ms. Metodologia completa: [RECALL_SHIELD.md](RECALL_SHIELD.md). Artefatos: `results/phase3_5/`.

## B-007 — Fase 3.75: Semantic Rescue

Calibração em 11 development queries escolheu TF-IDF threshold 0,24/margin 0,05 contra character n-gram. Holdout ampliado de 36 queries: HYBRID recall 1,0, precision 0,8681, Active Brain mediano 2 MiB/médio 2,67 MiB, Activation Rate 0,260%, false confidence/early stop/ALL_DOMAIN zero. Fast p50/p95 0,069/0,284 ms; semantic slow 0,400/0,705 ms; custo ponderado 0,226 ms.

Integração: 100.663.296 bytes lógicos e 122.355.712 físicos, contra LEXICAL 226.492.416/276.824.064 e Progressive 642.777.088/680.460.288. Context helpful 2 MiB, contamination zero. Resultados negativos incluem fuzzy 8 hits úteis/20 falsos e confidence development não monotônica. Detalhes: [SEMANTIC_RESCUE.md](SEMANTIC_RESCUE.md). Artefatos: `results/phase3_75/`.

## B-008 — Fase 4A: Cognitive Cache Policy

36 traces (100/500/1.000/5.000 turns), 9 workloads, budgets 4/8/16/32/64/128 MiB e sete policies foram simulados sem tocar residência física. Em 64 MiB: Cognitive 4,396 GiB miss vs LRU 9,537 e Belady 2,491; hit 95,86%; regret@8 2,02%; pollution 3,603 GiB; churn 8.678; p95 87,7 µs. Cognitive fechou ~73% do gap LRU→Oracle.

Resultados negativos: LFU venceu em 4 MiB, LRFU em 32, Cognitive perdeu 94 MiB para LRU no A→B→A/16 e topic/transition quase não ajudaram na ablation holdout. Metodologia: [COGNITIVE_CACHE.md](COGNITIVE_CACHE.md). Artefatos: `results/phase4a/`.
# Phase 4B physical matrix

The canonical artifacts are `results/phase4b/calibration.json`, `runs.json`, `aggregate.json`, and `summary.json`. The matrix covers six workloads, four budgets, five policies, shadow/guided tracks, four cardinalities, two repetitions, randomized run order, and separate observability/performance runs. At 64 MiB aggregate reads were KernelOnly 966.06 MiB, LRU+PAGEOUT 1,018.62 MiB, and Cognitive+PAGEOUT 1,036.00 MiB.
# Phase 4C controlled pressure

Canonical artifacts are under `results/phase4c/`. The matrix contains 97 main runs plus 12 pressure-aware runs, two repetitions, hard 512 MiB/1 GiB limits, swap zero, six workloads and randomized order. At 512 MiB, KernelOnly/Cognitive+COLD/pressure-aware reads were 6,577.77/6,436.01/6,332.20 MiB. At 1 GiB, hints were neutral and added two small refaults.

## B-009 — Fase 4D: Real Knowledge end-to-end

Corpus: 12.521 Records / 15 páginas / 15 MiB por layout, utilização média 96,20%; índice gzip 13,24 MiB. Holdout semantic+Brain: Record recall/precision estritos 75,00%/10,71%, Page recall/precision 75,00%/28,57%, Active Brain médio/mediano 2,625/2,5 MiB e densidade 0,2432%. Packing semântico reduziu páginas médias em 25% contra random.

Qwen-only/Standard/Brain/Oracle obtiveram qualidade de fatos 25,00/43,75/43,75/62,50%. Brain mediu TTFT mediano 11,667 s, latência média 11,744 s e 30,55 tok/s; pico RSS/PSS 1,121/1,117 GiB. `read_bytes=0` e major faults=0 representam cache Linux quente, não cold SSD. Artefatos: `results/phase4d/`.
