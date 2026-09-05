# Brain-SSD — Hypothesis Registry

Status: registro de hipóteses pós-realignment. Nenhuma hipótese `UNTESTED` está autorizada para implementação. A Fase 4E permanece anterior a todas elas.

## Estados

- `UNTESTED`: proposta documentada, sem implementação autorizada.
- `TESTING`: protocolo aprovado e experimento em execução.
- `SUPPORTED`: benefício reproduzido dentro dos critérios declarados.
- `REJECTED`: hipótese falhou ou custo/regressão superou o benefício.
- `CONDITIONAL`: funciona apenas em workloads, budgets ou perfis delimitados.
- `INCONCLUSIVE`: evidência insuficiente ou ambiente inadequado.

Mudar estado exige artefatos, configuração, quality check e resource check. Implementação existente sem benchmark não basta.

## Baselines empíricos preservados

| ID | Hipótese histórica | Estado | Evidência e limite |
|---|---|---|---|
| HYP-B01 | Um Core sub-1B executa CPU-only dentro do envelope de memória | SUPPORTED | Fase 1; prova de vida mínima, não qualidade ampla |
| HYP-B02 | Acesso mmap mantém memória proporcional ao conjunto tocado, não ao mapping total | SUPPORTED | Fase 2; ambiente virtual e sem pressão forte |
| HYP-B03 | 1 MiB logical / 4 MiB extent / logical-only é baseline equilibrado | CONDITIONAL | Fase 2.5; 256 KiB venceu custo absoluto, 1 MiB foi joelho multiobjetivo |
| HYP-B04 | HYBRID + TF-IDF recupera com alta esparsidade no corpus sintético | SUPPORTED | Fase 3.75 holdout; linguagem aberta não validada |
| HYP-B05 | Cognitive Cache V0 reduz misses lógicos contra LRU em 64 MiB | CONDITIONAL | Fase 4A; regressões em outros budgets/workloads |
| HYP-B06 | Controle físico agressivo traduz ganhos lógicos em economia agregada | REJECTED | Fase 4B; KernelOnly venceu PAGEOUT |
| HYP-B07 | COLD pressure-aware reduz I/O sob pressão | CONDITIONAL | Fase 4C; ganho a 512 MiB, regressão STABLE_TOPIC, neutro a 1 GiB |
| HYP-B08 | Pipeline real seletivo melhora Core-only e vence RAG padrão | CONDITIONAL | Fase 4D: melhora Core-only, empata RAG, fica abaixo do Oracle |

## Hipóteses V2

| ID | Hipótese | Fase candidata | Métricas principais | Baseline | Riscos | Estado |
|---|---|---|---|---|---|---|
| HYP-001 | Record Distillation reduz contexto e prompt compute mantendo qualidade | 4F | context tokens, prompt eval CPU/TTFT, required facts, groundedness | ContextBuilder 4D pós-4E | Remover evidência necessária; compressor custar mais | UNTESTED |
| HYP-002 | Oracle Minimal Context expõe desperdício acionável no contexto atual | 4F | Brain tokens / Oracle tokens, fact quality | Contexto 4D | Oracle irrealista ou limite mal definido | UNTESTED |
| HYP-003 | Like-to-like functional connectivity reduz trabalho de retrieval | 5A | Seed/Expanded Recall, precision, graph CPU/RAM, Active Brain | HYBRID direto | Grafo grande, correlação espúria | UNTESTED |
| HYP-004 | Seed circuits + expansão limitada preserva recall com menos busca direta | 5A | 0/1/2 hops, candidates, pages, CPU, recall | Direct retrieval | Explosão e dependência da seed | UNTESTED |
| HYP-005 | Inibição antes da expansão reduz candidatos sem perda de recall | 5B | Inhibition Savings, false-negative rate, overrides, CPU | Expansão sem inibição | Falsos negativos e score excessivo | UNTESTED |
| HYP-006 | Links excitativos melhoram ranking sem prefetch | 5B | Rank/recall/precision, pages, graph cost | HYBRID sem links | Excitação virar overactivation | UNTESTED |
| HYP-007 | Histórico de coativação prediz circuitos úteis futuros | 5C | Future useful links, precision@k, regret, support | Links semânticos estáticos | Coativação não causal; overfit de sessão | UNTESTED |
| HYP-008 | Decay e suporte entre sessões controlam plasticidade funcional | 5C | stale links, false expansion, rollback, metadata | Aprendizado sem decay | Esquecer relações úteis ou consolidar ruído | UNTESTED |
| HYP-009 | Phased cognitive execution reduz Module/Compute Duty Cycle | 6 | CPU total, duty cycle, latency, quality | ALWAYS_ON pipeline | Scheduler overhead e perda de paralelismo | UNTESTED |
| HYP-010 | Activity-silent state evita reexecução sem perder contexto | 6 | module invocations, CPU, context success | Módulo mantido/reexecutado | Estado compacto insuficiente | UNTESTED |
| HYP-011 | Context Delta reduz prompt processing repetido em multi-turn | 7 | repeated tokens, prompt eval CPU, TTFT, quality | Full context reprocessing | Core atual não suportar reutilização segura | UNTESTED |
| HYP-012 | ReflexCore resolve tarefas triviais sem pipeline completo | 7 | Core calls avoided, CPU/TTFT, false bypass | Pipeline completo | Classificar tarefa complexa como trivial | UNTESTED |
| HYP-013 | Memória episódica separada reduz colisão com conhecimento semântico | 8 | collision, false retrieval, episodic recall | KnowledgeRecords mistos/sem episódios | Complexidade e contaminação | UNTESTED |
| HYP-014 | Pattern completion recupera episódio correto por pista parcial | 8 | recall@k, false completion, bytes/CPU | Retrieval exato | Completar memória errada | UNTESTED |
| HYP-015 | Raciocínio repetido pode ser compilado em Skill validada | 9 | CPU/TTFT/tokens/Core calls avoided, pass rate | Core reasoning | Automatizar erro e risco de execução | UNTESTED |
| HYP-016 | Repacking offline por coativação reduz I/O real | 10 | physical reads, faults, latency, rollback | Layout semântico congelado | Write amplification, corrupção, ganho só sintético | UNTESTED |
| HYP-017 | Core recorrente/compacto reduz estado e compute mantendo qualidade | 11 | RAM, prompt cost, tok/s, quality | Qwen3-0.6B congelado | Ecossistema/modelo incompatível | UNTESTED |
| HYP-018 | Budget adaptativo por recursos reduz trabalho em PC fraco sem cruzar piso de qualidade | Pós-4E | Brain Work Vector por perfil, recall, OOM, thermal | Budget fixo | Economia comprada com perda de recall | UNTESTED |
| HYP-019 | Decisão multi-evidence é mais robusta que um proxy isolado | Fase dependente | ablations, OOD, calibration, CPU marginal | Melhor sinal isolado | Custo e regras difíceis de calibrar | UNTESTED |
| HYP-020 | Cascade recursiva evita acordar componentes caros em queries simples | Fase dependente | WhyWasIActivated, module calls, CPU, quality | Todos os módulos avaliados | Trigger incorreto/overhead da cascade | UNTESTED |

## Ordem experimental

1. Executar a Fase 4E sem mudanças funcionais.
2. Analisar Brain Work Vector físico.
3. Confirmar ou alterar a prioridade pós-4E.
4. Selecionar uma hipótese principal.
5. Escrever protocolo, critérios de qualidade e stop conditions.
6. Obter aprovação explícita.
7. Implementar em módulo/artefato separado.
8. Executar A/B e preservar negativos.
9. Atualizar o estado da hipótese.

## Prioridade provisória após a Fase 4E

1. HYP-001/HYP-002 — Context Reduction;
2. redução direta de CPU/TTFT indicada pelo perfil físico;
3. HYP-003/HYP-004 — Connectivity shadow;
4. HYP-005/HYP-006 — inibição/excitação;
5. HYP-009/HYP-010 — scheduler e activity-silent;
6. HYP-011/HYP-012 — delta/reflex;
7. HYP-015 — Skills;
8. HYP-013/HYP-014 — evolução de memória;
9. HYP-016/HYP-017 — repacking e Core alternativo.

Essa ordem é provisória. A Fase 4E pode demonstrar que outra fonte de custo domina.

## Hipóteses de engenharia de runtime

Estas hipóteses medem a implementação Windows e não são hipóteses biológicas nem autorização para alterar a arquitetura cognitiva.

| ID | Hipótese refutável | Experimento | Critério | Estado |
|---|---|---|---|---|
| ENG-CORE-002 | A maior parte do ganho A→C do WCRE-1 permanece no controle B→C, indicando contribuição principal da persistência e não apenas do build | WCRE-1B | `SUPPORTED` se a parcela B→C exceder 60%; `CONDITIONAL` entre 40–60%; caso contrário `REJECTED` | SUPPORTED — B→C explicou ~100,04% do ganho mediano de latency A→C; A→B foi +0,03% |
| ENG-CORE-003 | Prompt eval/TTFT cresce materialmente com os tokens reais de contexto enviados ao Qwen | WCRE-1B | Evidência prática de crescimento positivo, sem exigir linearidade; outliers 1,5×IQR preservados | SUPPORTED — 211,47 ms/39 tokens para 25.629,75 ms/3418 tokens; R² linear descritivo 0,9877 |

## Hipóteses Phase 4F-W — Windows experimental

Estas hipóteses pertencem à trilha Windows `PHASE_4F_W`. Elas não concluem a Fase 4F canônica Debian e não autorizam substituir o ContextBuilder V0.

| ID | Hipótese | Estado inicial | Critério central |
|---|---|---|---|
| HYP-4FW-001 | Distillation extrativa reduz tokens mantendo required-fact recall | CONDITIONAL | Extractive reduziu compute, mas nenhum budget preservou simultaneamente o perfil completo de qualidade V0 nas 14 queries |
| HYP-4FW-002 | Records recuperados sem contribuição podem ser removidos pós-retrieval | SUPPORTED | Pruning mediano 8→3 Records; correctness 28,57→35,71%, OOD 100%, com perda de Context Fact Recall em um retrieval miss |
| HYP-4FW-003 | Contexto menor/focado pode melhorar o Qwen3-0.6B | SUPPORTED | `holdout_thread_modes` passou com 891 tokens após falhar grounding no V0 com 1792; sinal de overload, não prova de mecanismo |
| HYP-4FW-004 | Redução real de contexto reduz prompt eval, CPU e TTFT | SUPPORTED | Pruning reduziu prompt eval 53,23%, TTFT 53,18% e CPU 40,72%; custo mediano 1,69 ms |
| HYP-4FW-005 | Existe Minimal Useful Context por consulta | CONDITIONAL | Identificado em 5/14 queries; mediana 358 tokens entre os casos resolvidos |

## Template para nova hipótese

```text
ID:
Título:
Estado: UNTESTED
Observação/origem:
Abstração computacional:
Hipótese refutável:
Baseline congelado:
Mudança única:
Dataset/split:
Métricas de qualidade:
Brain Work Vector:
Critério de suporte:
Critério de rejeição:
Riscos/stop conditions:
Artefatos:
Resultado:
```

## Regra de autorização

Registro não é autorização. Nenhuma hipótese V2 pode ser implementada apenas por aparecer nesta tabela. Cada fase precisa de aprovação explícita depois da Fase 4E.
