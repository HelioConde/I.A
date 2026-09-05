# Brain-SSD — Registro de Decisões

## D-001 — Restringir alterações ao diretório Brain-SSD

- Status: aceito
- Data: 2026-08-07
- Decisão: todas as escritas deste projeto ficam em `/workspaces/Pal-Server/Brain-SSD`.
- Motivo: o repositório pai contém outro projeto fora do escopo.

## D-002 — CPU-only como referência funcional

- Status: aceito
- Data: 2026-08-07
- Decisão: toda funcionalidade essencial deve operar sem GPU; GPU será opcional.
- Consequência: benchmarks e testes de correção começam pela CPU.

## D-003 — Memória como orçamento explícito

- Status: aceito
- Data: 2026-08-07
- Decisão: 8 GB é o alvo rápido, mas configurações menores devem continuar funcionais com degradação de desempenho.
- Consequência: RSS máximo e comportamento sob limites baixos são métricas de primeira classe.

## D-004 — Baseline antes de otimização

- Status: aceito
- Data: 2026-08-07
- Decisão: não introduzir otimizações ou frameworks pesados sem hipótese, baseline e justificativa mensurável.

## D-005 — Adiar escolhas de implementação

- Status: aceito
- Data: 2026-08-07
- Decisão: linguagem, framework, formato, algoritmo e modelo permanecem em aberto nesta fase.
- Motivo: a auditoria ambiental não basta para selecionar uma arquitetura.

## Decisões futuras

- D-F01: linguagem/runtime do protótipo.
- D-F02: formato e unidade do armazenamento frio.
- D-F03: mecanismo de I/O e indexação.
- D-F04: política do cérebro ativo.
- D-F05: workload representativo e critérios quantitativos.
- D-F06: camada opcional de GPU.

## D-006 — Backend de processo como primeira fronteira

- Status: aceito para Fase 1
- Data: 2026-08-07
- Decisão: Python orquestra e mede um runtime externo; não incorpora o caminho crítico de inferência.
- Motivo: permite trocar llama.cpp/RWKV/Mamba sem acoplar arquitetura e facilita migração futura para C/C++/Rust.

## D-007 — Core de prova Qwen3-0.6B Q8_0

- Status: aceito somente como baseline
- Data: 2026-08-07
- Decisão: usar o GGUF oficial de 639.446.688 bytes, checksum registrado.
- Motivo: pequeno, CPU-friendly, multilíngue e suficiente para provar INPUT→OUTPUT. Não representa a faixa final 1B–3B nem valida qualidade geral.

## D-008 — llama.cpp isolado e fixado por commit

- Status: aceito para Fase 1
- Data: 2026-08-07
- Decisão: compilar CPU-only o commit `217df17ac30ba2a8c374088772f81926cc5beee3` dentro de `Brain-SSD`.
- Motivo: GGUF/mmap, Linux CPU e métricas internas. Nenhuma instalação global.
- Custo observado: o grafo atual do CLI inclui módulos de servidor/multimodais e tentou provisionar UI; isso amplia o build. Reavaliar/pinar uma release menor antes de distribuição.

## D-009 — Usar llama-completion, não llama-cli, no baseline

- Status: aceito
- Data: 2026-08-07
- Decisão: `llama-completion` executa geração direta.
- Motivo: `llama-cli` do commit atual falhou no Codespace ao obter porta interna. O resultado negativo foi mantido.

## D-010 — Evicção fria limitada ao arquivo

- Status: aceito
- Data: 2026-08-07
- Decisão: `POSIX_FADV_DONTNEED` só no GGUF para cenário frio.
- Motivo: não requer privilégio nem interfere deliberadamente no page cache global do host.

## D-011 — Não equiparar RSS a Active Brain Size

- Status: aceito
- Data: 2026-08-07
- Decisão: métricas cognitivas inexistentes ficam nulas e justificadas.
- Motivo: RSS inclui runtime/estruturas e não identifica circuitos/páginas necessários à resposta.

## D-012 — Um arquivo de dados, vários manifests

- Status: aceito na Fase 2
- Data: 2026-08-07
- Decisão: segmentar o mesmo `brain.dat` em páginas de tamanhos diferentes por manifest.
- Motivo: controla conteúdo/seed e evita quatro cópias de 1 GiB.

## D-013 — SHA-256 completo em toda leitura medida

- Status: aceito para Storage V0
- Data: 2026-08-07
- Decisão: integridade faz parte do caminho medido.
- Consequência: latência inclui custo CPU proporcional ao tamanho da página; benchmarks futuros poderão separar validação amostrada somente com novo baseline explícito.

## D-014 — Cold somente best-effort e local ao arquivo

- Status: aceito
- Data: 2026-08-07
- Decisão: exigir fadvise aplicado e mapping com RSS inicial zero, chamando o estado de `best-effort cold`.
- Motivo: não há garantia de cache físico global e não é seguro descartar cache do host.

## D-015 — Não impor hard limit no cgroup compartilhado

- Status: aceito
- Data: 2026-08-07
- Decisão: `--memory-budget-mib` é orçamento lógico declarado, não limite kernel.
- Motivo: `memory.max` é compartilhado pelo Codespace; alterá-lo pode prejudicar outros processos. Um benchmark hard-limit precisa de cgroup/contêiner isolado.

## D-016 — Nenhum vencedor universal de página

- Status: aceito como conclusão da matriz V0
- Data: 2026-08-07
- Decisão: manter tamanho configurável.
- Evidência: 4 MiB venceu p95; amplificação favoreceu 8/16/32 MiB dependendo do workload. Throughput sequencial isolado não decide.

## D-017 — Separar integrity de performance

- Status: aceito
- Data: 2026-08-07
- Decisão: SHA completo fica em integrity/first activation; performance toca cada página base de 4 KiB e acumula sink.
- Motivo: SHA respondia por ~53% do p95 em 4/8 MiB e contaminava granularidade.

## D-018 — LogicalCorticalPage distinta de StorageExtent

- Status: aceito
- Data: 2026-08-07
- Decisão: unidade ativável e agrupamento físico possuem tamanhos independentes.
- Motivo: página pequena reduz Activation Cost; extent pode organizar localidade sem obrigar overfetch.

## D-019 — Baseline 1 MiB lógico / 4 MiB extent

- Status: recomendado para a próxima fase; aguarda aprovação
- Data: 2026-08-07
- Decisão: acesso padrão logical-only. Full extent fica experimental/desabilitado.
- Motivo: 1 MiB é o joelho medido de latência/amplificação/metadados; 4 MiB foi o extent menos prejudicial.

## D-020 — Colocalização útil não implica leitura coalescida útil

- Status: aceito como resultado negativo
- Data: 2026-08-07
- Decisão: preservar layout próximo como hipótese, sem habilitar full-extent/group-required automaticamente.
- Evidência: colocalização reduziu I/O contra random quando o extent já era lido, mas logical-only continuou com menor custo absoluto.

## D-021 — Não materializar 4 GiB nesta sessão

- Status: aceito
- Data: 2026-08-07
- Motivo: `memory.max=max` e ausência de reclaim; mais volume não criaria limite controlado. Priorizar causalidade no corpus de 1 GiB.

## D-022 — Router lexical residente como baseline V0

- Status: aceito para Fase 3
- Data: 2026-08-07
- Decisão: normalização, índice invertido e score IDF/BM25-like, sem LLM.
- Evidência: ~0,126 ms p50 e índice Python estimado em 854 KB para 1.024 páginas.
- Limite: recall 0,94 em 8 MiB; fallback será obrigatório antes de uso real.

## D-023 — Gate separado e orçamento recomendado de 8 MiB

- Status: baseline experimental, não vencedor definitivo
- Data: 2026-08-07
- Decisão: começar futura integração com 8 páginas de 1 MiB e manter 4/16/32/64 configuráveis.
- Motivo: 8 MiB equilibrou 0,94 recall, 0,59 precision e 0,688% de ativação; 4 MiB perdeu mais páginas e 32/64 ativaram mais sem chegar a recall perfeito.

## D-024 — Histerese lógica não implica residência

- Status: aceito com proteção de orçamento
- Data: 2026-08-07
- Decisão: reservar no máximo 25% do plano para persistência acima do deactivation threshold; Linux continua decidindo residência.
- Evidência: churn −23,4% em 8 MiB, recall estável; regressão de recall em 4 MiB registrada.

## D-025 — Não alegar bytes físicos evitados contra ALL_BRAIN

- Status: aceito
- Data: 2026-08-07
- Decisão: reportar bytes lógicos evitados e physical reads observados separadamente.
- Motivo: ALL_BRAIN não foi fisicamente relido para toda consulta e fadvise é somente best-effort cold.

## D-026 — Preservar LEXICAL e adicionar Progressive como variante

- Status: aceito
- Data: 2026-08-07
- Decisão: `LexicalRouter`/`BasalGate` da Fase 3 permanecem inalterados; Recall Shield vive em módulo novo.
- Motivo: comparação A/B e reprodução dos 94% originais.

## D-027 — Budget progressivo é teto, não preenchimento

- Status: aceito
- Data: 2026-08-07
- Decisão: 4→8→16→32 MiB com early stop; duas páginas podem usar 2 MiB no estágio de 4.
- Evidência: mediana holdout 8 MiB apesar de teto final até 32 MiB.

## D-028 — Unknown não aciona ALL_DOMAIN

- Status: aceito
- Data: 2026-08-07
- Decisão: ausência de termos/contexto conhecidos retorna `NO_KNOWLEDGE`, zero páginas.
- Motivo: proteger segurança e evitar falsa recuperação.

## D-029 — Aliases V0 aceitos somente como baseline explícito

- Status: experimental
- Data: 2026-08-07
- Evidência: recall 85,71→100%, precision 26,04→54,07%, memória média 22,95→15,43 MiB.
- Limite: manutenção manual e polissemia; não generaliza.

## D-030 — Recall Shield não substitui fallback nem calibração futura

- Status: aceito
- Data: 2026-08-07
- Decisão: preservar sinais e status, sem confiar em score único.
- Motivo: todos os bins pós-fallback tiveram recall 100%, impedindo provar correlação de confidence; 33,3% usaram ALL_DOMAIN limitado.

## D-031 — Context Gate separa modulation de expansion

- Status: aceito
- Data: 2026-08-07
- Decisão: query completa só modula tópicos atuais; contexto introduz no máximo um conceito quando partial probability >=0,55.
- Evidência: 2 MiB úteis, zero contamination; adversarial A→B recall 100%.

## D-032 — TF-IDF sparse como Semantic Rescue V0

- Status: aceito como baseline experimental
- Data: 2026-08-07
- Decisão: threshold 0,24, margin 0,05, escolhido somente em development.
- Evidência: mesmo recall/OOD safety que char n-gram, com melhor precision, Active Brain e latência development.
- Limite: glosses sintéticos/manuais; não equivale a semântica aberta.

## D-033 — Não baixar tiny embedding nem adicionar LSA nesta fase

- Status: aceito
- Data: 2026-08-07
- Motivo: duas opções sparse já atingiram metas; 39 perfis/11 development queries não justificam modelo externo ou decomposição densa.

## D-034 — HYBRID não usa ALL_DOMAIN automaticamente

- Status: aceito
- Data: 2026-08-07
- Decisão: novelty/OOD pode retornar NO_KNOWLEDGE; limited domain existe apenas como safety posterior.
- Evidência: ALL_DOMAIN 0/36, unknown e nearest-neighbor traps 0 páginas.

## D-035 — Confidence não governa cascade isoladamente

- Status: aceito
- Data: 2026-08-07
- Motivo: curva development pré-rescue não monotônica; coverage, novelty, contexto e provenance permanecem necessários.

## D-036 — Cache Policy separada de Physical Residency

- Status: aceito
- Data: 2026-08-07
- Decisão: Fase 4A só simula metadata; sem cópia, mmap controlado, mlock ou prefetch.
- Motivo: isolar causalidade da política do Linux page cache.

## D-037 — Adaptive 2Q em vez de ARC completo

- Status: aceito
- Data: 2026-08-07
- Decisão: recent/frequent com promoção no segundo acesso.
- Motivo: baseline adaptativo simples e validável; ARC completo fica futuro se houver necessidade.

## D-038 — Pesos Cognitive calibrados somente em development

- Status: experimental
- Data: 2026-08-07
- Decisão: conjunto `association`, grid de cinco candidatos e prioridade miss/regret/pollution.
- Limite: topic/transition quase neutros no holdout, sinal de transferência imperfeita.

## D-039 — 64 MiB como compromisso, não ótimo universal

- Status: recomendado para eventual experimento físico, aguarda Fase 4B
- Data: 2026-08-07
- Motivo: 128 MiB contém o universo e trivializa; 64 MiB produziu 53,9% menos miss bytes que LRU e ainda expôs decisões.

## D-040 — Não substituir políticas simples

- Status: aceito
- Data: 2026-08-07
- Decisão: qualquer Fase 4B deve manter LRU/LFU A-B e fallback.
- Evidência: LFU venceu 4 MiB, LRFU 32 MiB e Cognitive regrediu em A→B→A/16.
# D-4B-01 — Keep Linux page cache in control

**Decision:** KernelOnly is the physical-residency baseline. Keep Cognitive V0 in shadow mode; do not apply routine PAGEOUT evictions.

**Evidence:** Cognitive+PAGEOUT read 7.24% more than KernelOnly and 1.71% more than LRU+PAGEOUT at 64 MiB aggregate. PAGEOUT achieved exact logical/physical fidelity but destroyed useful ghost residency. COLD/DONTNEED hints did not evict in the unconstrained Codespace. Revisit only under isolated real memory pressure.

# D-4B-02 — Do not materialize 4 GiB corpus

**Decision:** Reuse the 1 GiB corpus.

**Reason:** it provides the full 1,024 × 1 MiB physical-page universe required by the authorized cardinality matrix. A 4 GiB corpus would not answer an additional question without a delegated child cgroup.
# D-4C-01 — KernelOnly remains default; pressure-aware COLD remains experimental

**Decision:** do not enable static Cognitive residency hints by default.

**Evidence:** at hard 512 MiB, static Cognitive+COLD saved 2.15% versus KernelOnly but only 0.07% versus LRU+COLD. Pressure-aware hints saved 3.73% and reduced faults/stalls, but STABLE_TOPIC regressed 1.85%. At 1 GiB hints had no benefit. Native TARGET_8GB replication is required.

# D-4C-02 — Opportunistic residency is beneficial state

Pages outside logical HOT may remain resident when Linux has capacity. They are Kernel Bonus opportunities, not pollution by definition. No routine PAGEOUT or forced budget fidelity will be used.

# D-4D-01 — KnowledgeRecord separado da página física

**Decisão:** Records variáveis (~1,4 KiB alvo) são recuperados semanticamente; páginas mmap permanecem 1 MiB e extents 4 MiB. Nunca criar mmap por Record.

**Evidência:** chunks anteriores maiores reduziram precisão. Packing semântico reduziu Active Brain holdout em 25% contra random, mas densidade de 0,2432% recomenda reavaliar granularidade somente em fase futura controlada.

# D-4D-02 — Primeiro MVP real aprovado sem declarar vitória sobre RAG

**Decisão:** marcar `FIRST_REAL_END_TO_END_TEST = PASS`, manter KernelOnly e congelar resultados. Brain-SSD melhorou contra Core-only, empatou RAG padrão e permaneceu abaixo do Oracle. Fase 5 não iniciada.

# D-V2-01 — Redefinir Brain-SSD como arquitetura cognitiva seletiva

**Status:** aceito documentalmente; runtime inalterado.

**Decisão:** Brain-SSD é uma arquitetura cognitiva esparsa, hierárquica, dinâmica e seletiva. Não será definido como RAG em SSD; SSD é somente uma camada física.

**Consequência:** a pergunta principal inclui trabalho computacional, não apenas memória e I/O.

# D-V2-02 — Fase 4E permanece o próximo teste

**Status:** aceito.

**Decisão:** executar Physical TARGET_8GB Validation do V0 congelado antes de implementar qualquer hipótese V2.

**Motivo:** novas otimizações precisam de baseline real de CPU, RAM, SSD, cold/warm, temperatura, throttling e qualidade.

# D-V2-03 — Brain Work Vector sem score único

**Status:** aceito como especificação de telemetria.

**Decisão:** registrar ativação, retrieval, contexto, CPU, I/O, latência, memória e qualidade como vetor. Campos indisponíveis são `null` com justificativa.

**Motivo:** Active Brain pequeno pode coexistir com prompt compute alto; uma dimensão não representa o trabalho completo.

# D-V2-04 — Context Reduction é prioridade provisória pós-4E

**Status:** planejado, não autorizado.

**Decisão:** avaliar primeiro Record Distillation e Required Context Minimization baratos. Não usar segundo LLM pesado por query como baseline.

**Evidência:** Fase 4D ativou ~2,6 MiB, mas enviou ~1.700 tokens e mediu TTFT ~11,7 s.

# D-V2-05 — Princípios biológicos viram hipóteses, não implementações literais

**Status:** aceito.

**Decisão:** Drosophila, C. elegans, MICrONS, organoides, neurociência humana e paleoneurologia fornecem abstrações limitadas. Benchmark decide manutenção ou rejeição.

**Proibições:** spiking por estética, milhões de objetos neurônio, ondas artificiais, bioquímica fictícia, connectoma artificial completo e alegações de consciência.

# D-V2-06 — Connectivity shadow antes de influência real

**Status:** planejado, não autorizado.

**Decisão:** futura CorticalConnectivityGraph prevê seeds, expansões e inibições sem alterar runtime. Somente após A/B poderá influenciar candidatura.

**Fronteiras:** excitação não é prefetch; conectividade não substitui HYBRID Router; expansão possui hops e budget explícitos.

# D-V2-07 — Similaridade semântica e conectividade funcional são distintas

**Status:** aceito como requisito futuro.

**Decisão:** links derivados de conteúdo e links aprendidos por coativação/transição serão armazenados e avaliados separadamente.

**Motivo:** coativação não implica causalidade e vocabulário semelhante não implica uso conjunto.

# D-V2-08 — Plasticidade somente em metadata controlada

**Status:** planejado, não autorizado.

**Decisão:** aprendizado exige versão, contador, suporte mínimo, confidence, decay, limites, logs, holdout e rollback. Nenhum repacking físico durante resposta.

# D-V2-09 — Inibição é reversível e subordinada à evidência atual

**Status:** planejado, não autorizado.

**Decisão:** links inibitórios nunca são verdade absoluta. Nova evidência pode aplicar override; Inhibitory False Negative Rate acompanha qualquer economia.

# D-V2-10 — Phased execution deve vencer always-on incluindo overhead

**Status:** planejado, não autorizado.

**Decisão:** CognitiveCycleScheduler só será mantido se reduzir CPU/duty cycle sem regressão de qualidade e depois de incluir custo de scheduling/sincronização.

# D-V2-11 — Não lutar contra o hardware

**Status:** aceito permanentemente.

**Decisão:** KernelOnly continua padrão e mecanismos do sistema operacional não serão reimplementados sem ganho físico demonstrado. V2 não reabre a decisão PAGEOUT nem autoriza prefetch.

# D-V2-12 — Registro não é autorização

**Status:** aceito.

**Decisão:** toda hipótese recebe ID e estado, mas somente uma hipótese principal é implementada por fase após aprovação explícita. Fases históricas e baseline pós-4E permanecem comparadores para impedir regressões acumuladas.

# D-HUD-01 — Observabilidade não entra no caminho crítico

**Status:** aceito.

**Decisão:** eventos são copiados para um buffer limitado e projetados por uma camada desconectável. O navegador não participa de Router, Gate, Storage, Context ou Core. O MVP não injeta chamadas nos algoritmos congelados; integrações live futuras usarão o contrato de eventos somente após autorização própria.

**Motivo:** explicabilidade não pode mudar a decisão cognitiva, bloquear uma resposta ou converter ausência de observador em falha do sistema.

# D-HUD-02 — Ausência de telemetria permanece explícita

**Status:** aceito.

**Decisão:** replay mostra `null`, `UNKNOWN` ou justificativa quando a Fase 4D não registrou uma medida. Demo recebe selo global e `demo_data=true`. O microbenchmark de overhead não é apresentado como benchmark do Qwen.
