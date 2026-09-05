# Brain-SSD — Arquitetura experimental

Status: Fases 1–4D concluídas e congeladas experimentalmente. A Fase 4E — Physical TARGET_8GB Validation — é o próximo teste executável. Neuroarchitecture V2 está documentada, não implementada.

## Tese

Brain-SSD investiga uma IA local cujo custo por interação é proporcional à parte ativada do cérebro, não ao volume total persistido. Não é swap de pesos, offload ingênuo de camadas ou KV cache em SSD.

Definição oficial V2: Brain-SSD é uma arquitetura cognitiva esparsa, hierárquica, dinâmica e seletiva, onde apenas os circuitos necessários para a tarefa atual são ativados e mecanismos de roteamento, inibição, memória, associação, previsão e automatização tentam minimizar trabalho computacional. Não deve ser definido como “RAG armazenado em SSD”; SSD é apenas uma camada física.

A pergunta arquitetural central passa a ser: **quanto do cérebro e quanto do computador precisaram trabalhar para produzir esta resposta?** Portanto Active Brain Size/Rate deve ser acompanhado por Computational Activation e pelo Brain Work Vector, sempre junto de qualidade.

- SSD/NVMe: capacidade cerebral fria e persistente.
- RAM: cérebro ativo, caches HOT/WARM e estado.
- CPU: caminho funcional e referência de desempenho.
- GPU: acelerador/cache L0 opcional, nunca requisito de correção.

Linux x86-64 é a plataforma primária. A meta normal é 8 GB de RAM, com processo residente em torno de 4–5 GB e margem para o sistema. Máquinas com 4 GB ou menos devem degradar em cache, buffers, prefetch e paralelismo, mas permanecer funcionais.

## Fluxo cognitivo proposto

```text
Input -> Reflex Core -- suficiente --> Resposta
                    |
                    v
             Thalamic Router -> Basal Gating -> Cognitive State
                    |                 |
                    +---- ativa somente Core + Cortical Pages
                                      + Hippocampus + Skills necessários
                                      |
                                      v
                         estado recorrente/delta -> Resposta

Resource Manager monitora e limita recursos em paralelo.
Cache Manager e Prefetcher movem páginas HOT/WARM/COLD.
Consolidation trabalha somente em idle, com journal e rollback.
```

Estado inicial de módulos é OFF. Inibição é tão importante quanto ativação. Histerese, dwell time e decay evitam carregar/descarregar o mesmo tema a cada token.

## Componentes e contratos

As fronteiras devem permanecer independentes do modelo e da linguagem:

- `InferenceBackend`: geração pelo Core; primeiro adaptador usa processo `llama.cpp` (`llama-completion` no baseline).
- `StorageBackend`: manifests, Cortical Pages, checksums, versões e leitura parcial.
- `MemoryBackend`: working, episodic, semantic e skill memory.
- `RouterBackend`: intenção/domínio/tópicos com custo pequeno.
- `GateBackend`: ativação/inibição esparsa.
- `SkillBackend`: skills determinísticas ou modelos pequenos, testados e reversíveis.
- `TelemetryBackend`: recursos do processo, I/O e métricas cognitivas.

O Core inicial será pequeno e substituível. Qwen3-0.6B GGUF serve apenas como baseline de prova de vida. llama.cpp é um adaptador experimental, não dependência arquitetural permanente. Alternativas futuras incluem backends recorrentes (RWKV/Mamba/SSM), BitNet-like e outros runtimes.

## Hierarquia de armazenamento proposta

- L0: caches de CPU e GPU opcional.
- L1: Core e páginas extremamente quentes em RAM.
- L2: cache WARM em RAM.
- L3: Cortical Pages no SSD/NVMe.
- L4: arquivo opcional.

Cortical Page/Microcircuit Page, e não neurônio individual, é a unidade física. Serão comparados 4, 8, 16 e 32 MiB. Metadados extensíveis incluem id, versão, tamanho, domínio, tópicos, ativações, hot score, importância, dependências, relações, inibições, checksum e localização. mmap/page cache será o primeiro mecanismo; leitura explícita, io_uring e O_DIRECT serão experimentos posteriores, nunca melhorias presumidas.

## Memórias e plasticidade propostas

- Working: estado da tarefa atual.
- Episodic: eventos distintos, com pattern separation.
- Semantic: conceitos consolidados, recuperáveis por pista parcial/pattern completion.
- Skill: operações baratas aprendidas e validadas.

Novelty/surprise, importância, recorrência, relevância, confiança e utilidade futura controlam retenção. Esquecimento inclui descarte, resumo, compressão, deduplicação e redução de prioridade. Conhecimento consolidado tem baixa plasticidade; uma experiência nova entra primeiro como episódio. Toda mutação persistente deve ser auditável, versionada e, quando possível, reversível.

## Cache, prefetch e localidade propostos

LRU é o baseline obrigatório. LFU/ARC e um hot score cognitivo contextual só entram em testes A/B posteriores. Prefetch será avaliado por acerto, desperdício e latência evitada. Leituras devem ser coalescidas. Consolidação poderá aproximar fisicamente páginas coativadas, com integridade, journal e rollback.

## Resource Manager

Monitora RAM, page cache, pressão, CPU, temperatura quando acessível, SSD I/O, filas e hit rate. Reduz WARM/prefetch/consolidação antes de ameaçar interação. Pesos read-only mapeados podem ser descartados e relidos; swap não é estratégia de armazenamento cerebral.

## Estado implementado

Somente:

Fase 1 preservada:

1. auditoria reproduzível de hardware;
2. interface mínima para Core externo;
3. adaptador CPU-only para executável llama.cpp;
4. baseline Qwen3-0.6B e resultados originais.

Fase 2:

1. corpus sintético determinístico e reutilizável;
2. manifests e Cortical Pages 4/8/16/32 MiB com SHA-256;
3. `StorageBackend` e `MMapStorageBackend` read-only;
4. seis workloads físicos isolados do LLM;
5. best-effort cold, warm e hot com evidência de residência;
6. RSS/PSS/anônimo/file-backed/private/shared, I/O, faults, CPU e cgroup v2;
7. 216 runs de tamanho/workload/cache e 16 runs de working set.

Fase 2.5:

1. separação entre integrity, first-activation verification e performance touch;
2. LogicalCorticalPages de 256 KiB a 8 MiB;
3. StorageExtents experimentais de 4/8/16 MiB;
4. layouts associativos random/colocated com sequência idêntica;
5. modos logical-only/full-extent/group-required;
6. Useful Byte Ratio e Activation Cost;
7. baseline recomendado: Logical Page 1 MiB, Extent 4 MiB, acesso logical-only.

Fase 3:

1. metadados semânticos sintéticos e dataset com ground truth;
2. `RouterBackend`, Oracle/ALL_DOMAIN/RANDOM_K e Router lexical leve;
3. `GatingBackend` separado, thresholds, top-k, orçamento e inibição;
4. Cognitive State V0 com decay, dwell e histerese lógica;
5. métricas de recall, precision, miss, activation rate, Active Brain Size e churn;
6. benchmark de cardinalidade até 1 milhão de páginas sem materializar TB;
7. ensaio Route→Gate→Storage preservando 1 MiB/4 MiB/logical-only.

Fase 3.5 adiciona `LexicalProgressiveRouter` sem alterar o LEXICAL original: decomposição, aliases pequenos, multi-domínio, Query Coverage, contexto limitado, partial-cue/topic-switch, budgets progressivos 4/8/16/32 MiB e fallback limitado/recusa explícita. Budget é teto; páginas não são ativadas apenas para preenchê-lo. Cognitive State auxilia retrieval, mas não controla residência. Resultados e limites estão em [RECALL_SHIELD.md](RECALL_SHIELD.md).

Fase 3.75 adiciona `HybridRetrievalV0`: cascata exact→fuzzy/aliases→context gate→semantic sparse→budget→fallback. Estado é por conceito e contexto completo apenas modula; expansão exige partial cue. TF-IDF e character n-gram foram comparados, sem embedding/modelo externo. CandidateEvidence e provenance explicam cada ativação. Detalhes em [SEMANTIC_RESCUE.md](SEMANTIC_RESCUE.md).

Fase 4A adiciona apenas `CachePolicy`, trace v1 e simulador offline. NO_CACHE/LRU/LFU/LRFU/Adaptive2Q/Cognitive/Belady decidem metadata KEEP/EVICT/PROMOTE/DEMOTE; nenhuma delas controla mmap ou residência Linux. Cognitive usa recency/frequency/topic/transition/reload/provenance/hysteresis/age somente após acesso, nunca como prefetch. Detalhes em [COGNITIVE_CACHE.md](COGNITIVE_CACHE.md).

Brain Cache continua inexistente e é reportado como 0 bytes gerenciados; não se confunde com Linux page cache. Active Brain Size e activation rate agora medem o plano lógico, não residência. `physical_read_bytes` mede armazenamento físico atribuído ao processo; ainda não é `Knowledge I/O per Answer`, pois não há resposta cognitiva.

## Fora da Fase 4A

Reflex Core, caches cognitivos, prefetch, Hipocampo, skills, consolidação, autoaprendizado, adapters, GPU, io_uring, O_DIRECT, backends recorrentes e quantização extrema continuam planejados/experimentais conforme a matriz.
# Phase 4B physical-residency boundary

The runtime now has an experimental `ResidencyController` boundary below the frozen `CachePolicy`. It can observe the existing file-backed mapping with `mincore` and issue optional advisory COLD/DONTNEED/PAGEOUT hints. It never chooses victims, copies page contents, prefetches, or guarantees residency. Phase 4B selected KernelOnly as the architectural baseline; policies remain suitable for shadow telemetry, not active reclaim. See `PHYSICAL_RESIDENCY.md`.
# Phase 4C resource-pressure boundary

`ResourcePressureMonitor` is the minimal read-only Glia V0 interface. It observes cgroup memory, reclaim and PSI and emits a pressure label. The default physical controller remains KernelOnly. One-shot `MADV_COLD` is retained only as an experimental pressure-gated hint; it never forces residency and preserves opportunistic Linux page-cache retention.

## Fase 4D — Real Knowledge MVP

`KnowledgeRecord` é a unidade semântica e `LogicalCorticalPage` de 1 MiB continua sendo a unidade física. O pipeline determinístico empacota snapshots oficiais Python/SQLite em páginas mmap, cria índice a partir do conteúdo, recupera Records, deduplica páginas e envia somente Records selecionados ao `ContextBuilder`. Qwen permanece Core provisório CPU-only. Cache cognitivo continua shadow e KernelOnly controla residência. Veja [REAL_KNOWLEDGE.md](REAL_KNOWLEDGE.md) e [END_TO_END_MVP.md](END_TO_END_MVP.md).

## Realinhamento Neuroarchitecture V2

O realinhamento V2 preserva todo o runtime e todos os resultados anteriores. Ele adiciona uma agenda experimental, não novos componentes:

- Context Compression/Record Distillation após o baseline físico;
- CorticalConnectivityGraph primeiro em shadow mode;
- excitação e inibição como ajustes de candidatura, nunca prefetch implícito;
- coativação funcional separada de similaridade semântica;
- plasticidade apenas em metadata versionada, limitada, com decay e rollback;
- Cognitive Cycles comparados obrigatoriamente com pipeline always-on;
- activity-silent state, Context Delta, ReflexCore, Hipocampo e Skills como hipóteses futuras;
- Brain Work Vector e Computational Activation como métricas de primeira classe.

Nenhum desses itens está implementado. Não há mudança em HYBRID retrieval, Qwen, page size, residência, cache físico ou prefetch. Consulte [NEUROARCHITECTURE_V2.md](NEUROARCHITECTURE_V2.md), [BIOLOGICAL_PRINCIPLES.md](BIOLOGICAL_PRINCIPLES.md), [COMPUTE_EFFICIENCY.md](COMPUTE_EFFICIENCY.md) e [HYPOTHESIS_REGISTRY.md](HYPOTHESIS_REGISTRY.md).

## Visual HUD / Cognitive Observability

O HUD é uma projeção read-only e removível. `BrainEventBus` mantém um stream limitado e não bloqueante; `HudStateStore` deriva estado visual sem reter objetos mutáveis do pipeline; HTTP/SSE atende apenas leitura. O MVP usa demo sintética ou replay dos JSONs canônicos da Fase 4D. Nenhum módulo cognitivo congelado foi instrumentado ou alterado. Consulte [VISUAL_HUD.md](VISUAL_HUD.md).
