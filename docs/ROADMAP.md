# Brain-SSD — Roadmap incremental

## Marco atual

Fases 1–4D estão concluídas e congeladas. A trilha intermediária **Fase 4E-W — Windows Native Validation** foi concluída como `PASS_WITH_WARNINGS` e não altera a ordem científica. A **Fase 4E — Physical TARGET_8GB Validation** em Debian permanece pendente e deve ocorrer antes de qualquer implementação da Neuroarchitecture V2. Os componentes V2 abaixo são planejamento sujeito aos resultados físicos e a aprovação explícita.

## Fase 0 — Auditoria e especificação (concluída)

Hardware, limites do cgroup, filesystem, toolchain, arquitetura conceitual, decisões e 80 requisitos foram registrados. O repositório pai foi identificado como fora do escopo.

## Fase 1 — Prova de vida CPU-only (concluída em 2026-08-07)

- Core Qwen3-0.6B Q8_0 executado via backend modular llama.cpp.
- INPUT→OUTPUT validado sem GPU, 1 thread, ~780 MB RSS.
- Telemetria e resultados JSON reproduzíveis.
- Sondas negativas preservadas.

Limite: qualidade testada apenas por uma resposta canônica; nenhuma propriedade SSD-first foi validada.

## Fase 2 — Storage Brain V0 (concluída em 2026-08-07)

Corpus sintético de 1 GiB, manifests/checksums, mmap read-only, páginas 4/8/16/32 MiB, seis workloads, cold/warm/hot, telemetria ampliada, reopen e falhas de corrupção foram medidos. Não há cache próprio.

Resultado: 4 MiB minimizou latência por acesso em todos os workloads; tamanhos maiores às vezes reduziram amplificação por reutilização/coalescimento, sem vencedor universal. Próximo passo requer aprovação explícita e deverá começar por um baseline de cache simples, não por Fase 3 automática.

Checklist de saída:

- [x] StorageBackend e MMapStorageBackend;
- [x] Cortical Pages, manifest, checksums e corpus reproduzível;
- [x] 4/8/16/32 MiB comparados;
- [x] sequential, random, hot-set, clustered, topic-switch e associative-walk;
- [x] best-effort cold, warm e hot medidos;
- [x] faults, physical I/O, RSS, PSS e file-backed medidos;
- [x] working sets 64/256/512/1024 MiB comparados;
- [x] reopen, truncamento e corrupção testados;
- [x] resultados negativos e limitações preservados;
- [x] documentação atualizada.

## Fase 3 — Router + gating (concluída em 2026-08-07)

Router lexical sem LLM, controles Oracle/ALL_DOMAIN/RANDOM_K, Gate separado, inibição, orçamento 4–64 MiB e estado lógico foram implementados e medidos. Com 8 MiB, LEXICAL obteve recall 0,94, precision 0,59 e ativou 0,688% do cérebro de 1 GiB; o custo mediano foi ~0,126 ms. O resultado prova baixo custo e alta esparsidade, mas não recall suficiente para uso cognitivo sem fallback.

Histerese reduziu churn 23,4% em 8 MiB sem perder recall nessa sequência, mas causou regressão de recall em 4 MiB. Fase 4 permanece bloqueada até aprovação explícita.

Checklist Fase 3: Oracle, ALL_DOMAIN, RANDOM_K, LEXICAL, Gate/inibição/orçamentos, Cognitive State/decay/histerese, recall/precision/miss/activation/churn/custo/índice/bytes, topic-switch, cardinalidade, 21 testes e documentação estão concluídos. Nenhum cache próprio ou prefetch foi criado.

Checklist Fase 2.5:

- [x] integrity e performance separados;
- [x] 256/512 KiB e 1/2/4/8 MiB;
- [x] LogicalCorticalPage e StorageExtent;
- [x] logical-only/full-extent/group-required;
- [x] associative random/colocated com sequência idêntica;
- [x] topic-switch A1/B/A2;
- [x] Useful Byte Ratio e Activation Cost;
- [x] integridade 100%;
- [x] Fases anteriores verificadas por checksum;
- [x] nenhum componente da Fase 3.

## Fase 4 — Cognitive Cache

LRU primeiro; depois LFU/ARC e cache contextual em A/B. Adicionar estado, histerese, dwell e decay sem remover baselines.

Antes dela, a **Fase 3.5 foi concluída em 2026-08-07**. Progressive contextual atingiu recall holdout 100%, false confidence zero, mediana 8 MiB, média 13,71 MiB e decisão p95 0,805 ms. O custo foi precision 48,72%, ALL_DOMAIN limitado em 33,3% e physical bytes integrados 1,96× o LEXICAL no agregado. Fase 4 continua bloqueada até aprovação explícita.

A **Fase 3.75 foi concluída em 2026-08-07**: HYBRID+TF-IDF atingiu recall 100%, precision 86,81%, mediana 2 MiB, média 2,67 MiB, ALL_DOMAIN/false stop zero e custo médio 0,226 ms no holdout ampliado. Semantic foi usado em 30,56%; contexto útil 2 MiB e contaminação zero. Fase 4 permanece bloqueada até aprovação explícita.

A **Fase 4A foi concluída em 2026-08-07** como simulação, sem cache físico. Em 64 MiB, Cognitive V0 reduziu miss bytes 53,9% contra LRU e fechou ~73% do gap até Belady, com regret/pollution/churn menores; p95 foi 87,7 µs e metadata ~58 KiB no trace. Perdeu para LRU em A→B→A/16 MiB e para políticas simples em budgets específicos. Fase 4B permanece bloqueada até autorização explícita.

## Roadmap histórico anterior ao realinhamento V2

As seções Fase 5–10 abaixo são preservadas como histórico, mas sua numeração foi substituída pelo roadmap Neuroarchitecture V2 pós-4E ao final deste documento. Elas não autorizam Prefetch nem outra implementação.

## Fase 5 — Prefetch (histórica; não autorizada)

Predição e leituras coalescidas; medir hit, waste, bytes e latência. Prefetch que piora é removido e registrado.

## Fase 6 — Hipocampo

Working/episodic/semantic separadas, inicialmente com componentes leves como SQLite. Testar pattern separation/completion e novelty antes de vetores ou banco pesado.

## Fase 7 — Cerebelo/Skills

Detectar repetição e gerar somente candidatos. Testes, sandbox, versão e rollback antecedem execução.

## Fase 8 — Consolidação

Idle-only: deduplicação, estatísticas, clustering, poda e, depois, localidade física journaled. Sem auto-fine-tuning inicial.

## Fase 9 — Core recorrente

Comparar backends RWKV/Mamba/SSM com o mesmo protocolo de RAM, qualidade e latência.

## Fase 10 — Quantização extrema

Avaliar modelos arquiteturalmente compatíveis com BitNet/ternário/2-bit; nunca converter cegamente.

## Fora do MVP

Treino de modelo do zero, MoE gigantesco, simulação biológica detalhada, aprendizado contínuo sem controle, arquitetura de produção e qualquer otimização sem baseline.
# Phase 4B — completed

Physical residency was measured over 356 isolated runs. KernelOnly beat policy-guided PAGEOUT in aggregate. Active physical reclaim is not recommended without an isolated cgroup or physical low-RAM validation. Phase 5/prefetch remains unstarted and requires explicit authorization.
# Phase 4C — completed

Valid container hard limits and cgroup file-cache charging were proven. KernelOnly remains default. Pressure-aware COLD hints showed a 3.73% aggregate I/O reduction at 512 MiB but regressed STABLE_TOPIC and require native TARGET_8GB replication. Phase 5 remains unstarted.

## Fase 4D — concluída

Primeiro pipeline real completo validado com fontes Python/SQLite, KnowledgeRecords, packing semântico/aleatório, retrieval-only, mmap seletivo, ContextBuilder e Qwen CPU-only. `FIRST_REAL_END_TO_END_TEST = PASS`. Falhas de recall, baixa Knowledge Density e custo de prompt foram preservados. Nenhum prefetch foi iniciado.

## Fase 4E — Physical TARGET_8GB Validation (próxima)

Executar o V0 congelado em hardware Debian físico. Medir cold/warm, CPU, RAM, SSD, TTFT, prompt processing, geração, I/O, faults, temperatura, throttling, qualidade e sessão sustentada. Nenhum algoritmo da Fase 4D deve mudar para melhorar esse baseline.

Saída obrigatória: Brain Work Vector físico e decisão `TARGET_8GB` conforme [PHYSICAL_END_TO_END.md](PHYSICAL_END_TO_END.md).

## Fase 4E-W — Windows Native Validation (trilha intermediária concluída)

Mediu o V0 congelado no Windows físico atual sob `WINDOWS_NATIVE_FUNCTIONAL`, com Core isolation, single-shot, sessão, repeated query, sustained e overhead do HUD. A matriz `matrix-20260820T133446Z-07ae123074` concluiu todos os conjuntos como `PASS`, gerando estado final `PASS_WITH_WARNINGS`, `phase4ew_canonical=true`, `phase4e_valid=false` e `TARGET_8GB=NOT_TESTED`. Ver [PHASE_4EW_WINDOWS_VALIDATION.md](PHASE_4EW_WINDOWS_VALIDATION.md) e `results/phase4ew/summary.json`.

## Roadmap Neuroarchitecture V2 pós-4E

### Fase 4F — Context Compression / Over-retrieval Reduction

Primeira prioridade provisória. Comparar ContextBuilder congelado, Record Distillation barato e Oracle Minimal Context. Objetivo: reduzir tokens, prompt CPU e TTFT mantendo required facts, groundedness e unknown safety. Não usar um segundo LLM pesado como baseline por query.

### Fase 5A — Cortical Connectivity Graph shadow

Executar previsões sem alterar runtime. Separar links semânticos estáticos de links funcionais aprendidos. Comparar retrieval direto com seed + expansão de 0/1/2 hops sob budget de páginas, MiB e CPU.

### Fase 5B — Excitatory/Inhibitory Gating

Permitir influência controlada somente se o shadow passar. Excitação altera ranking; inibição exige confidence, decay, override e medição de false negatives. Nenhum link implica prefetch.

### Fase 5C — Coactivation Learning

Atualizar apenas metadata versionada e reversível. Exigir suporte entre sessões, limites, decay, holdout e anti-overfitting. Nenhum repacking online.

### Fase 6 — Cognitive Cycle Scheduler

Comparar pipeline always-on com execução em fases. Medir Module/Compute Duty Cycle, CPU, latência e qualidade. Rejeitar se o overhead superar a economia.

### Fase 7 — Predictive/Delta Processing e Reflex

Comparar full context com Context Delta conforme capacidades reais do Core. Investigar ReflexCore separadamente com proteção contra false bypass.

### Fase 8 — Hippocampus

Adicionar memória episódica separada da memória semântica/documental. Testar pattern separation, collision, false retrieval e pattern completion.

### Fase 9 — Cerebellum / Skills

Transformar raciocínio repetido em Skill candidata somente após testes, sandbox, versão e rollback. Medir CPU, TTFT, tokens e Core calls evitados.

### Fase 10 — Sleep / Consolidation / Physical Repacking

Analisar coativação offline, deduplicação e layout. Qualquer mudança física exige journal, checksum, rollback e A/B contra semantic packing congelado.

### Fase 11 — Alternative recurrent/compact Core

Comparar Core recorrente/compacto pelo mesmo protocolo físico e de qualidade. Qwen congelado permanece baseline.

## Regra de prioridade

A ordem pós-4E é provisória: Context Reduction → CPU/TTFT → Connectivity shadow → Inhibition → Scheduler → Delta → Skills → Memory evolution. Dados físicos podem reordená-la. Apenas uma hipótese principal por fase, com ID em [HYPOTHESIS_REGISTRY.md](HYPOTHESIS_REGISTRY.md).

## Trilha transversal — Visual HUD

O MVP de observabilidade local está implementado como trilha transversal e não ocupa nem reordena uma fase experimental. Ele visualiza demo sintética e replay da Fase 4D, mantém modos Simples/Técnico e deixa integração live como trabalho futuro. A Fase 4E continua sendo o próximo experimento autorizado; o HUD não autoriza mudanças de algoritmo.
