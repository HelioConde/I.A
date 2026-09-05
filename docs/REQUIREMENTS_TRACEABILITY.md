# Brain-SSD — Matriz de rastreabilidade

Status permitidos: **IMPLEMENTAR AGORA**, **PLANEJADO**, **EXPERIMENTAL**, **FORA DO MVP**. “Implementar agora” não significa validado; a evidência aparece na coluna Teste.

| ID | Requisito | Componente | Fase | Status | Teste | Métrica | Observações |
|---|---|---|---:|---|---|---|---|
| R-001 | Linux x86-64 como plataforma principal | Platform | 0 | IMPLEMENTAR AGORA | auditoria | kernel/ISA | Ubuntu auditado |
| R-002 | CPU-only funcional | Inference | 1 | IMPLEMENTAR AGORA | geração com `--device none` | conclusão, TTFT, tok/s | referência obrigatória |
| R-003 | GPU opcional, nunca necessária | Inference | 1+ | IMPLEMENTAR AGORA | baseline sem GPU | sucesso CPU | aceleração futura |
| R-004 | 8 GB como alvo normal | Resource Manager | 1+ | IMPLEMENTAR AGORA | orçamento/RSS | RSS máximo | alvo do processo 4–5 GB |
| R-005 | Degradação funcional abaixo de 8 GB | Resource Manager | 2+ | PLANEJADO | matriz de limites | conclusão/latência | 4 GB é cenário prioritário |
| R-006 | Detectar recursos e adaptar cache/threads/buffers/prefetch | Resource Manager | 2+ | PLANEJADO | perfis de hardware | RAM/CPU/I/O | baseline detecta; adaptação futura |
| R-007 | SSD é cérebro frio, não swap/VRAM lenta | Storage | 2 | IMPLEMENTAR AGORA | corpus 1 GiB/mmap esparso | physical I/O/residência | V0 validado fisicamente; sem semântica |
| R-008 | RAM é cérebro ativo HOT/WARM | Cache | 2–4 | PLANEJADO | working-set limitado | Active Brain Size | margem obrigatória |
| R-009 | Custo proporcional ao cérebro ativo | System | 2+ | EXPERIMENTAL | variar cérebro total/ativo | custo vs ABS | hipótese central a refutar |
| R-010 | Consulta comum busca ~<100 MB quando possível | Storage | 2+ | EXPERIMENTAL | suite comum | Knowledge I/O/answer | meta, não promessa |
| R-011 | Cortical Pages em vez de leituras por neurônio | Storage | 2 | IMPLEMENTAR AGORA | 232 runs por página | IOPS/latência | validado em V0 |
| R-012 | Comparar páginas 4/8/16/32 MiB | Storage benchmark | 2 | IMPLEMENTAR AGORA | matriz 216 runs | throughput/amp/p95 | nenhum vencedor universal |
| R-013 | Router barato por intenção/domínio/tópico | Router | 3 | PLANEJADO | suite de roteamento | custo/recall | Tálamo Digital |
| R-014 | Gating inicia OFF e ativa só relevantes | Gating | 3 | PLANEJADO | sem/com gating | activation rate | excitação e inibição |
| R-015 | Inibir módulos irrelevantes | Gating | 3 | PLANEJADO | negativos por domínio | módulos evitados | mesma prioridade da ativação |
| R-016 | Histerese, dwell, decay e persistência de tópico | Cognitive State | 3–4 | PLANEJADO | conversa alternada | reloads/cache hit | evitar thrashing semântico |
| R-017 | Reflex Core para tarefas triviais | Reflex | 3+ | PLANEJADO | suite trivial | bypass/custo/qualidade | não chamar Core sem necessidade |
| R-018 | Pensamento repetido vira skill barata | Skills | 7 | PLANEJADO | comparação Core/skill | custo/qualidade | somente com benefício |
| R-019 | Skills testadas, versionadas, sandboxed e reversíveis | Skills/Security | 7 | PLANEJADO | falha/rollback | pass rate | nunca executar cegamente |
| R-020 | Separar working, episodic, semantic e skill memory | Memory | 6–7 | PLANEJADO | testes por tipo | recall/contaminação | fronteiras explícitas |
| R-021 | Pattern separation episódica | Hippocampus | 6 | PLANEJADO | episódios similares | precisão | manter eventos distintos |
| R-022 | Pattern completion por pista parcial | Hippocampus | 6 | PLANEJADO | consultas incompletas | recall@k | não só string exata |
| R-023 | Novelty/surprise controla memorização | Memory | 6 | PLANEJADO | trivial vs novidade | precision/retention | inclui confiança/utilidade |
| R-024 | Esquecimento por descarte/resumo/compressão | Consolidation | 8 | PLANEJADO | políticas A/B | qualidade/bytes | função, não falha |
| R-025 | Sleep/Consolidation somente idle | Consolidation | 8 | PLANEJADO | carga interativa | interferência/tempo | replay, poda, reorganização |
| R-026 | Mudanças persistentes auditáveis/versionadas/reversíveis | Integrity | 2+ | PLANEJADO | recovery/rollback | integridade | sem autoaprendizado solto |
| R-027 | Homeostase: confiança/estabilidade/plasticidade/importância | Memory | 8+ | PLANEJADO | contradição isolada | drift | episódio antes de conceito |
| R-028 | Glia/Resource Manager monitora saúde | Resources | 2+ | PLANEJADO | pressão induzida | RAM/CPU/I/O | prioriza interação |
| R-029 | Reagir à pressão sem thrashing | Resources | 2+ | PLANEJADO | níveis alta→crítica | faults/I/O/latência | descartar WARM antes de HOT |
| R-030 | Estado resumido e delta processing | Cognitive State | 3+ | EXPERIMENTAL | full vs delta | custo/qualidade | não perder informação necessária |
| R-031 | Core pequeno 1B–3B, CPU-friendly | Inference | 1+ | IMPLEMENTAR AGORA | prova 0.6B e futuras 1–3B | RSS/tok/s/qualidade | 0.6B só prova de vida |
| R-032 | mmap/quantização/Linux no Core | Inference | 1 | IMPLEMENTAR AGORA | GGUF CPU | RSS/faults | mmap padrão do runtime |
| R-033 | BitNet/1.58/2-bit/ternário | Inference | 10 | EXPERIMENTAL | modelo compatível A/B | bytes/qualidade/tok/s | não quantizar cegamente |
| R-034 | Core recorrente/RWKV/Mamba/SSM | Inference | 9 | EXPERIMENTAL | backend substituível | RAM/qualidade/latência | não obrigatório no MVP |
| R-035 | Evitar KV cache enorme/offload como solução | Inference | 1+ | PLANEJADO | contexto crescente | RAM/I/O | estado seletivo preferido |
| R-036 | Especialização barata (LoRA/adapters/tools) | Experts | 3+ | EXPERIMENTAL | Core vs adapter | bytes/qualidade | sem MoE gigante inicial |
| R-037 | Separar raciocínio, conhecimento, experiência, skills, docs | Architecture | 0+ | IMPLEMENTAR AGORA | revisão de fronteiras | acoplamento | documentado |
| R-038 | Drosophila inspira topologia, não cópia | Research | futuro | EXPERIMENTAL | hipótese específica | eficiência/robustez | sem números inventados |
| R-039 | C. elegans inspira dinâmica eficiente; connectoma não basta | Research | futuro | EXPERIMENTAL | hipótese específica | eficiência/comportamento | pesos/estado importam |
| R-040 | Conectividade modular, esparsa e inibitória | Architecture | 3+ | PLANEJADO | dense vs sparse | ativação/qualidade | evitar tudo-com-tudo |
| R-041 | Princípio dendrítico sem simulação biológica cara | Experts | futuro | EXPERIMENTAL | branches especializados | custo/qualidade | subentradas limitadas |
| R-042 | Cache L0/L1/L2/L3(/L4) | Cache/Storage | 2–4 | PLANEJADO | transições | hit/bytes/latência | GPU só L0 opcional |
| R-043 | LRU como primeiro baseline | Cache | 4 | PLANEJADO | trace replay | hit/latência | nunca remover baseline |
| R-044 | Comparar LFU/ARC/hot score cognitivo | Cache | 4 | EXPERIMENTAL | A/B mesmo trace | hit/custo | sofisticado pode perder |
| R-045 | Prefetch cognitivo penaliza erros | Prefetch | 5 | PLANEJADO | predictor on/off | hit/waste/latência | não saturar SSD |
| R-046 | Leituras coalescidas | Storage | 2/5 | PLANEJADO | pequenas vs agrupadas | IOPS/bytes/latência | medir locality |
| R-047 | Localidade hebbiana física com journal/rollback | Consolidation | 8 | EXPERIMENTAL | layout A/B + recovery | I/O/latência | adaptação, não biologia literal |
| R-048 | Começar por mmap/page cache/madvise/readahead | Storage | 2 | IMPLEMENTAR AGORA | cold/warm/hot | faults/I/O/residência | mmap+fadvise V0; demais continuam futuros |
| R-049 | io_uring e O_DIRECT só como experimentos | Storage | 2+ | EXPERIMENTAL | A/B com mmap | latência/CPU/I/O | não presumir superioridade |
| R-050 | Pesos read-only descartáveis, não swapados como estratégia | Storage | 1+ | IMPLEMENTAR AGORA | mmap e sem swap | RSS/faults | arquivo é fonte canônica |
| R-051 | Python para protótipo; caminho crítico migrável | Engineering | 1+ | IMPLEMENTAR AGORA | interfaces/processo | acoplamento | C/C++/Rust futuros |
| R-052 | Backends modulares | Architecture | 1+ | IMPLEMENTAR AGORA | fake + llama backend | testes de contrato | inference/storage/etc. |
| R-053 | Auditoria completa de hardware | Platform | 0 | IMPLEMENTAR AGORA | script + JSON | campos presentes | ambiente virtual anotado |
| R-054 | Telemetria TTFT, tok/s e latência | Telemetry | 1 | IMPLEMENTAR AGORA | geração local | ms, tok/s | tok/s do runtime |
| R-055 | Telemetria CPU/RAM/faults | Telemetry | 1 | IMPLEMENTAR AGORA | amostragem `/proc` | avg/max/RSS/faults | processo + filhos quando possível |
| R-056 | Telemetria bytes/operações/latência I/O | Telemetry | 1+ | IMPLEMENTAR AGORA | `/proc/io` | bytes/syscalls | latência I/O pode ser indisponível |
| R-057 | Cache/prefetch/ABS/activation/Knowledge I/O | Telemetry | 2+ | PLANEJADO | Storage Brain | métricas próprias | `null`, nunca zero falso na Fase 1 |
| R-058 | Temperatura/energia/throttling quando possível | Telemetry | futuro | EXPERIMENTAL | sensores disponíveis | °C/J/eventos | ambiente pode negar acesso |
| R-059 | Qualidade junto com desempenho | Evaluation | 1+ | IMPLEMENTAR AGORA | prompts canônicos | checks/score | suite ampla cresce depois |
| R-060 | Baseline antes/depois/delta para toda otimização | Method | todas | IMPLEMENTAR AGORA | registro A/B | X/Y/% | sem número, sem ganho alegado |
| R-061 | Experimentos negativos são preservados | Method | todas | IMPLEMENTAR AGORA | log de resultados | melhor/pior/neutro | tentar refutar hipóteses |
| R-062 | Integridade por checksum/versionamento/atomicidade/manifest | Storage | 2 | IMPLEMENTAR AGORA | truncamento/corrupção/reopen | 0 erros; falha detectada | journal futuro |
| R-063 | Knowledge data frio maior que RAM ativa | Storage | 2+ | IMPLEMENTAR AGORA | corpus 1 GiB vs páginas tocadas | total vs residente | 4/8 GiB suportados, não medidos |
| R-064 | Uma pergunta comum não lê vários GB | Storage | 2+ | PLANEJADO | suite comum | bytes/answer | ligado a R-010 |
| R-065 | Modelo/runtime existentes antes de treinar do zero | Inference | 1 | IMPLEMENTAR AGORA | Qwen/llama.cpp | prova de vida | treino do zero fora do MVP |
| R-066 | Não implementar muitas técnicas simultaneamente | Method | todas | IMPLEMENTAR AGORA | revisão por milestone | uma variável | incremental/A-B |
| R-067 | Não inventar dados; separar medido/hipótese/futuro | Documentation | todas | IMPLEMENTAR AGORA | revisão de relatórios | provenance | fontes e ambiente registrados |
| R-068 | Segurança de aprendizado contínuo e código | Security | 7+ | PLANEJADO | adversarial/rollback | incidentes | logs e limites |
| R-069 | Resposta experimental gera registro de métricas | Benchmark | 1+ | IMPLEMENTAR AGORA | JSON por run | completude | indisponível = null + motivo |
| R-070 | Checklist do prompt antes de milestone | Governance | todas | IMPLEMENTAR AGORA | checklist documentada | itens pendentes | pendente não pode sumir |
| R-071 | Reflex/router não processam pesado | Reflex/Router | 3 | PLANEJADO | perfil isolado | CPU/latência | custo pequeno obrigatório |
| R-072 | Dados carregados são reutilizados e I/O previsto | Cache/Prefetch | 4–5 | PLANEJADO | sessão temática | hit/Knowledge I/O | meta >90% hit é experimental |
| R-073 | Módulos inativos consomem ~zero CPU | Gating | 3 | PLANEJADO | perfil módulos OFF | CPU/activation | verificar empiricamente |
| R-074 | Margem de RAM; não consumir tudo disponível | Resource Manager | 1+ | IMPLEMENTAR AGORA | RSS vs orçamento | headroom | perfil default conservador |
| R-075 | Manter resultados brutos, reproduzíveis e checksummed | Benchmark | 1+ | IMPLEMENTAR AGORA | artefatos JSON | checksum/config | seeds e versões |
| R-076 | Modelo de páginas extensível | Storage | 2 | IMPLEMENTAR AGORA | 4 KiB–32 KiB em testes; MiB em matriz | compatibilidade | qualquer múltiplo 4 KiB que divida corpus |
| R-081 | Preservar baseline Fase 1 | Governance | 2 | IMPLEMENTAR AGORA | checks de arquivos | hashes/tamanhos | resultados em `results/phase2` separados |
| R-082 | Medir RSS/PSS/anônimo/file-backed/private/shared | Telemetry | 2 | IMPLEMENTAR AGORA | smaps_rollup/status | bytes/peaks | implementado; ausência vira null |
| R-083 | Medir cgroup v2 current/peak/stat/faults | Telemetry | 2 | IMPLEMENTAR AGORA | snapshot por run | bytes/faults | representa cgroup inteiro |
| R-084 | Corpus determinístico por seed sem regeneração | Corpus | 2 | IMPLEMENTAR AGORA | dois diretórios + reuse | igualdade/mtime | testado |
| R-085 | Suportar corpus 1/4/8 GiB progressivamente | Corpus | 2 | IMPLEMENTAR AGORA | CLI choices | tamanhos | 1 GiB medido; 4/8 apenas suportados |
| R-086 | StorageBackend open/close/get/release/stats | Storage | 2 | IMPLEMENTAR AGORA | contrato/reopen | correção | implementado |
| R-087 | Seis workloads determinísticos | Benchmark | 2 | IMPLEMENTAR AGORA | teste por enum/matriz | sequência/seed | 216 runs |
| R-088 | Separar cold/warm/hot com evidência | Benchmark | 2 | IMPLEMENTAR AGORA | mapping RSS/fadvise/I/O | residência/bytes | cold chamado best-effort |
| R-089 | Não confundir Brain Cache/Linux cache/physical miss | Telemetry | 2 | IMPLEMENTAR AGORA | campos separados | managed/resident/read_bytes | hit exato Linux indisponível |
| R-090 | `--memory-budget-mib` explícito | Resources | 2 | IMPLEMENTAR AGORA | CLI/config JSON | bytes | lógico, não hard cgroup |
| R-091 | Physical Read Amplification formal | Benchmark | 2 | IMPLEMENTAR AGORA | read_bytes/logical bytes | razão | implementado |
| R-092 | checksum_errors=0 e corrupção falha | Integrity | 2 | IMPLEMENTAR AGORA | 232 runs + teste negativo | erros | satisfeito |
| R-093 | Restart/reopen preserva manifest/páginas | Integrity | 2 | IMPLEMENTAR AGORA | open-close-open | sucesso | testado |
| R-094 | Sem cache inteligente/prefetch/io_uring/O_DIRECT | Scope | 2 | IMPLEMENTAR AGORA | revisão de árvore | componentes ausentes | satisfeito |
| R-095 | Benchmark Storage isolado do LLM | Benchmark | 2 | IMPLEMENTAR AGORA | processo storage puro | ausência de Core | satisfeito |
| R-096 | Working sets 64/256/512/1024 MiB | Benchmark | 2 | IMPLEMENTAR AGORA | curva 16 runs | RSS/I/O/p95 | universo amostrado por 256 MiB lógicos |
| R-097 | Detectar thrashing/reclaim | Telemetry | 2 | IMPLEMENTAR AGORA | pgscan/pgsteal | deltas | zero observado; sem pressão forte |
| R-098 | Não usar drop_caches global | Safety | 2 | IMPLEMENTAR AGORA | revisão de comandos | violações | somente fadvise no arquivo |
| R-099 | Parar antes da Fase 3 | Governance | 2 | IMPLEMENTAR AGORA | revisão de componentes | escopo | obrigatório |
| R-100 | Preservar Fase 2 e separar resultados 2.5 | Governance | 2.5 | IMPLEMENTAR AGORA | checksums/paths | integridade | `results/phase2_5` exclusivo |
| R-101 | Modo integrity com SHA completo | Integrity | 2.5 | IMPLEMENTAR AGORA | sweep 8.064 páginas | erros | 0 erros |
| R-102 | Modo performance sem SHA por acesso | Benchmark | 2.5 | IMPLEMENTAR AGORA | touch 4 KiB + sink | I/O/faults | leitura real confirmada |
| R-103 | Verificação opcional na primeira ativação | Storage | 2.5 | IMPLEMENTAR AGORA | policy matrix | p50/p95/CPU | IDs verified cacheados por open |
| R-104 | Testar 256/512 KiB e 1/2/4/8 MiB | Benchmark | 2.5 | IMPLEMENTAR AGORA | 324 runs | p50/p95/p99 | concluído |
| R-105 | Medir faults/CPU/metadata por acesso | Telemetry | 2.5 | IMPLEMENTAR AGORA | analysis JSON | taxas/bytes | concluído |
| R-106 | Definir LogicalCorticalPage | Storage | 2.5 | IMPLEMENTAR AGORA | schema/protótipo | logical bytes | definido |
| R-107 | Definir StorageExtent 4/8/16 MiB | Storage | 2.5 | IMPLEMENTAR AGORA | 9 combinações | extent bytes | definido |
| R-108 | Comparar logical/full/group-required | Storage benchmark | 2.5 | IMPLEMENTAR AGORA | 216 runs | p95/I/O/CPU | full extent regrediu |
| R-109 | Layout associativo random vs colocated | Layout | 2.5 | IMPLEMENTAR AGORA | sequence SHA | I/O/latência | sequências idênticas |
| R-110 | Topic switch A→B→A segmentado | Layout | 2.5 | IMPLEMENTAR AGORA | A1/B/A2 | physical bytes/faults | concluído |
| R-111 | Useful Byte Ratio | Telemetry | 2.5 | IMPLEMENTAR AGORA | useful/physical | razão | pode superar 1 com reuse |
| R-112 | Activation Cost por página lógica | Telemetry | 2.5 | IMPLEMENTAR AGORA | vetor + screening score | ms/MiB/CPU | definido e medido |
| R-113 | Linux page cache continua único cache | Scope | 2.5 | IMPLEMENTAR AGORA | revisão de árvore | cache próprio | zero |
| R-114 | Não implementar Fase 3/io_uring/O_DIRECT | Scope | 2.5 | IMPLEMENTAR AGORA | revisão de componentes | ausências | satisfeito |
| R-115 | Integridade 100% | Integrity | 2.5 | IMPLEMENTAR AGORA | full sweep | 8.064/8.064 | satisfeito |
| R-116 | Baseline recomendado para Fase 3 | Architecture | 2.5 | IMPLEMENTAR AGORA | análise multiobjetivo | trade-offs | 1 MiB logical/4 MiB extent/logical-only |
| R-117 | Preservar Fases 1/2/2.5 e baseline físico | Governance | 3 | IMPLEMENTAR AGORA | checksums/config | hashes/valores | 1 MiB/4 MiB/logical-only; resultados separados |
| R-118 | Metadados cognitivos e queries determinísticos | Dataset | 3 | IMPLEMENTAR AGORA | regenerate equality | seed/ground truth | 9 domínios, 39 tópicos, 25 queries |
| R-119 | Oracle/ALL_DOMAIN/RANDOM_K/LEXICAL | Router benchmark | 3 | IMPLEMENTAR AGORA | matriz canônica | recall/precision/custo | Oracle só benchmark |
| R-120 | RouterBackend separado do Storage | Router | 3 | IMPLEMENTAR AGORA | testes/contrato | acoplamento | RouteResult estruturado |
| R-121 | Gate separado, threshold/top-k/MiB/páginas | Gating | 3 | IMPLEMENTAR AGORA | unit tests/matriz | orçamento | IDs inválidos falham |
| R-122 | Excitação e inibição explícitas | Gating | 3 | IMPLEMENTAR AGORA | motivos/blocked pages | candidatos removidos | sem simulação biológica |
| R-123 | Cognitive State V0, decay, dwell e histerese | State | 3 | IMPLEMENTAR AGORA | A→B→A | churn/recall | estado lógico pequeno |
| R-124 | Recall/precision/miss/activation/ABS/churn | Telemetry | 3 | IMPLEMENTAR AGORA | summary JSON | razões/bytes/páginas | fórmulas documentadas |
| R-125 | Custo Router e índice residente | Telemetry | 3 | IMPLEMENTAR AGORA | 31 repeats/cardinality | p50/p95/p99/CPU/bytes | Python + postings compactos |
| R-126 | Net benefit como vetor, sem ocultar recall | Evaluation | 3 | IMPLEMENTAR AGORA | relatório | latency/bytes/pages/recall | nenhum score único |
| R-127 | Orçamentos 4/8/16/32/64 MiB | Benchmark | 3 | IMPLEMENTAR AGORA | 500 records | curva qualidade/custo | concluído |
| R-128 | Índices 1K/10K/100K/1M sem materializar TB | Benchmark | 3 | IMPLEMENTAR AGORA | compact postings | bytes/lookup/build | corpos excluídos explicitamente |
| R-129 | Route→Gate→Storage opcional isolado | Integration | 3 | IMPLEMENTAR AGORA | mmap touch | latency/CPU/physical bytes | best-effort cold |
| R-130 | Sem cache/prefetch/LLM Router/Fase 4 | Scope | 3 | IMPLEMENTAR AGORA | tree review | componentes ausentes | satisfeito |
| R-131 | Preservar hashes Fases 1–3 e resultados 3.5 separados | Governance | 3.5 | IMPLEMENTAR AGORA | sha256 antes/depois | integridade | `results/phase3_5` |
| R-132 | LEXICAL_PROGRESSIVE sem alterar LEXICAL | Router | 3.5 | IMPLEMENTAR AGORA | A/B mesmo holdout | recall/custo | módulo novo |
| R-133 | Early stop 4→8→16→32 e budget não preenchido | Retrieval | 3.5 | IMPLEMENTAR AGORA | unit/matriz | expansions/utilization | budget é teto |
| R-134 | Sinais transparentes e Query Coverage | Confidence | 3.5 | IMPLEMENTAR AGORA | JSON/calibration | coverage/gap/unknown/conflict | nenhum score isolado |
| R-135 | Decomposição e multi-domínio | Router | 3.5 | IMPLEMENTAR AGORA | holdout multi-domain | recall/precision/MiB | round-robin de conceitos |
| R-136 | Contextual expansion e partial cue | State | 3.5 | IMPLEMENTAR AGORA | multi-turn A/B | recall/bytes | máximo quatro termos |
| R-137 | Adaptive hysteresis e topic switch | State/Gate | 3.5 | IMPLEMENTAR AGORA | unit/switch | fraction/new-topic | switch forte zera reserva |
| R-138 | Unknown seguro e falha explícita | Safety | 3.5 | IMPLEMENTAR AGORA | unknown holdout | pages/status | zero páginas/NO_KNOWLEDGE |
| R-139 | False confidence/Recall per MiB/escalation/fallback | Telemetry | 3.5 | IMPLEMENTAR AGORA | summary JSON | taxas/distribuições | concluído |
| R-140 | Development/holdout e paráfrases disjuntos | Evaluation | 3.5 | IMPLEMENTAR AGORA | IDs/templates | split | 5 dev/21 holdout |
| R-141 | Typos/ruído e aliases A/B | Evaluation | 3.5 | IMPLEMENTAR AGORA | aliases on/off | recall/precision/custo | alias table pequena |
| R-142 | Stateless/hysteresis/contextual | Evaluation | 3.5 | IMPLEMENTAR AGORA | mesmo holdout | recall/MiB/precision | contexto tem ganhos e regressões |
| R-143 | Integração Route→Gate→mmap sem cache/prefetch | Integration | 3.5 | IMPLEMENTAR AGORA | 42 runs | TTFA/I/O/faults/CPU | best-effort cold |
| R-144 | Não iniciar Fase 4 ou componentes proibidos | Scope | 3.5 | IMPLEMENTAR AGORA | tree review | ausências | obrigatório |
| R-145 | Congelar LEXICAL e Progressive baselines | Governance | 3.75 | IMPLEMENTAR AGORA | hashes/A-B | integridade | módulos anteriores inalterados |
| R-146 | Cascade exact/fuzzy/context/semantic/budget/fallback | Router | 3.75 | IMPLEMENTAR AGORA | level trace | custo/stop | HYBRID_RETRIEVAL_V0 |
| R-147 | Context modulation vs gated expansion | Context | 3.75 | IMPLEMENTAR AGORA | full/partial/adversarial | helpful/contamination | no máximo um conceito |
| R-148 | Estado/decay por conceito e context budget | Context | 3.75 | IMPLEMENTAR AGORA | unit/multi-turn | confidence/age/support | implementado |
| R-149 | Provenance e Evidence per Page | Explainability | 3.75 | IMPLEMENTAR AGORA | JSON/unit | origens/scores | toda ativação explicável |
| R-150 | Alias universal/contextual e métricas | Router | 3.75 | IMPLEMENTAR AGORA | A/B/provenance | useful/false/count | 29/26/8 |
| R-151 | Fuzzy edit distance + character n-gram index | Router | 3.75 | IMPLEMENTAR AGORA | typo/unit | latency/index/hits | índice 21.328 B |
| R-152 | Comparar TF-IDF e char n-gram semantic | Semantic | 3.75 | IMPLEMENTAR AGORA | development grid | recall/precision/MiB/custo | TF-IDF venceu |
| R-153 | Semantic só rescue/rerank, não decisão cega | Gate | 3.75 | IMPLEMENTAR AGORA | evidence | recall/bytes | Gate diverso por conceito |
| R-154 | Concept-first/diversity/redundancy penalty | Gate | 3.75 | IMPLEMENTAR AGORA | multi-domain test | coverage/precision | round-robin 2 páginas |
| R-155 | Pre/post confidence e calibração development-only | Calibration | 3.75 | IMPLEMENTAR AGORA | grid/curvas | raw confidence/recall | holdout não escolhe thresholds |
| R-156 | False Early Stop/Semantic Rate/Rescue Success | Telemetry | 3.75 | IMPLEMENTAR AGORA | summary | taxas | 0%/30,56%/63,64% |
| R-157 | OOD e nearest-neighbor trap seguros | Safety | 3.75 | IMPLEMENTAR AGORA | 4 holdout cases | status/pages | NO_KNOWLEDGE/0 |
| R-158 | Fast/slow/expected weighted cost | Performance | 3.75 | IMPLEMENTAR AGORA | timers | p50/p95/mean | 0,069/0,284; 0,400/0,705; 0,226 ms |
| R-159 | Integração HYBRID→mmap sem cache/prefetch | Integration | 3.75 | IMPLEMENTAR AGORA | 108 runs | TTFA/I/O/faults | logical-only best-effort cold |
| R-160 | Não iniciar Fase 4/componentes proibidos | Scope | 3.75 | IMPLEMENTAR AGORA | tree review | ausências | obrigatório |
| R-161 | CachePolicy separada de residência física | Architecture | 4A | IMPLEMENTAR AGORA | interface/review | ausência de page data | simulação pura |
| R-162 | Trace v1 reproduzível sem ground truth como input | Trace | 4A | IMPLEMENTAR AGORA | round-trip/manifest | eventos/seed | 36 traces gzip |
| R-163 | Sessões 100/500/1K/5K e nove workloads | Benchmark | 4A | IMPLEMENTAR AGORA | trace manifest | turns/events | concluído |
| R-164 | Budgets 4/8/16/32/64/128 MiB | Benchmark | 4A | IMPLEMENTAR AGORA | matrix | miss curve | concluído |
| R-165 | NO_CACHE/LRU/LFU/LRFU/Adaptive2Q | Policies | 4A | IMPLEMENTAR AGORA | unit/replay | hits/misses | implementados |
| R-166 | Cognitive V0 interpretável sem ML | Cache | 4A | IMPLEMENTAR AGORA | score/ablation | componentes | association weights |
| R-167 | Associação/coativação somente para retenção | Cache | 4A | IMPLEMENTAR AGORA | tree review | admissions | sem antecipação |
| R-168 | Decay/hysteresis/context hygiene | Cache | 4A | IMPLEMENTAR AGORA | unit/workloads | pollution/churn | implementado |
| R-169 | Hit/byte hit/miss/cold/eviction | Telemetry | 4A | IMPLEMENTAR AGORA | matrix JSON | contagens/bytes | concluído |
| R-170 | Regret 1/2/4/8/16, pollution/useful residency | Telemetry | 4A | IMPLEMENTAR AGORA | replay | rates/bytes/turns | concluído |
| R-171 | Churn/reactivation/transition/return | Telemetry | 4A | IMPLEMENTAR AGORA | A-B-A/long gap | pages/bytes | concluído |
| R-172 | Decision p50/p95/p99 e CPU proxy | Telemetry | 4A | IMPLEMENTAR AGORA | timers | µs | concluído |
| R-173 | Metadata 1K e projeção 100K/1M | Resources | 4A | IMPLEMENTAR AGORA | synthetic metadata | bytes | linear, limitada |
| R-174 | Belady offline e gap LRU→Oracle | Oracle | 4A | IMPLEMENTAR AGORA | unit/matrix | miss bytes/gap | concluído |
| R-175 | Development/holdout e grid pequeno | Calibration | 4A | IMPLEMENTAR AGORA | paths/config | pesos | cinco candidatos |
| R-176 | Ablation topic/frequency/transition/reload/hysteresis/provenance | Evaluation | 4A | IMPLEMENTAR AGORA | 16 MiB holdout | deltas | concluído |
| R-177 | Unknown não altera cache | Safety | 4A | IMPLEMENTAR AGORA | unit/trace | resident delta | zero evento |
| R-178 | Sem cache físico, mlock, prefetch ou Fase 4B | Scope | 4A | IMPLEMENTAR AGORA | tree review | ausências | obrigatório |
| R-077 | PC fraco lento ainda é prova válida | Evaluation | 1 | IMPLEMENTAR AGORA | conclusão CPU limitada | resposta válida | velocidade baixa não é falha |
| R-078 | Nenhuma simulação biológica desnecessária | Architecture | todas | IMPLEMENTAR AGORA | revisão de escopo | custo evitado | roubar princípios úteis |
| R-079 | Documentos obrigatórios atualizados | Governance | todas | IMPLEMENTAR AGORA | verificação de arquivos | atualização | inclui requisitos e decisões |
| R-080 | Escritas restritas a Brain-SSD | Operations | todas | IMPLEMENTAR AGORA | inspeção de paths | violações | repositório pai fora do escopo |

## Regra de mudança

Toda alteração declara hipótese antes, mede depois e registra `ANTES`, `DEPOIS`, `DELTA` e resultado (`melhorou`, `piorou`, `neutro` ou `inconclusivo`). Requisitos só ficam validados com evidência reproduzível; código existente não basta.
# Phase 4B traceability

| ID | Requirement | Component | Status | Evidence |
|---|---|---|---|---|
| P4B-01 | Separate policy, residency, storage | `residency.py` | IMPLEMENTED | Layered interfaces; policy selects victims |
| P4B-02 | No duplicate page cache/prefetch/mlock | physical replay/tests | VERIFIED | anon growth max 2.25 MiB; no payload store |
| P4B-03 | KernelOnly and shadow baselines | controllers/benchmark | VERIFIED | 48 shadow runs |
| P4B-04 | COLD/DONTNEED/FADV/PAGEOUT behavior | calibration | VERIFIED | `calibration.json` |
| P4B-05 | mincore and fidelity metrics | physical replay | VERIFIED | residency matrix, ghost, false-hot |
| P4B-06 | physical I/O/fault/latency metrics | physical replay | VERIFIED | 356 runs, performance track |
| P4B-07 | 128/256/512/1,024 cardinality | trace expansion | VERIFIED | cardinality track |
| P4B-08 | 8/16/32/64 MiB budgets | matrix | VERIFIED | main track |
| P4B-09 | child cgroup investigation | calibration | UNAVAILABLE | hierarchy not delegated/writable |
| P4B-10 | preserve Router quality | frozen trace replay | VERIFIED | Router not invoked or modified |
| P4B-11 | stop before prefetch | project scope | VERIFIED | no WILLNEED/speculative access |
# Phase 4C traceability

| ID | Requirement | Status | Evidence |
|---|---|---|---|
| P4C-01 | Docker/runtime and hard-limit proof | VERIFIED | Docker 29.6.1, cgroup v2, finite memory.max |
| P4C-02 | File cache charged to cgroup | VERIFIED | corrected 256 MiB file_mapped probe |
| P4C-03 | Never alter parent cgroup | VERIFIED | disposable containers only |
| P4C-04 | 512 MiB/1 GiB isolated profiles | VERIFIED | 97-run matrix |
| P4C-05 | KernelOnly/Cognitive Shadow/LRU+COLD/Cognitive+COLD | VERIFIED | frozen policies, identical traces |
| P4C-06 | Reclaim/refault/restore/scan/steal/PSI | VERIFIED | worker cgroup telemetry |
| P4C-07 | ResourcePressureMonitor Glia V0 | IMPLEMENTED | read-only parser/classifier |
| P4C-08 | Pressure-aware hint screening | VERIFIED | 12 additional runs |
| P4C-09 | OOM/swap safety | VERIFIED | 0 OOM, swap max 0 |
| P4C-10 | No copied data/prefetch | VERIFIED | anon growth max 1.47 MiB |
| P4C-11 | Portable Debian runner/profiles | IMPLEMENTED | tool plus native profile guide |
| P4C-12 | Stop before Phase 5 | VERIFIED | no WILLNEED/speculative loading |

# Phase 4D traceability

| ID | Requirement | Status | Evidence |
|---|---|---|---|
| P4D-01 | fontes reais, legais, versionadas e offline | VERIFIED | source manifest + SHA-256 Python/SQLite |
| P4D-02 | KnowledgeRecord separado de página | IMPLEMENTED | `real_knowledge.py`, offsets/hashes |
| P4D-03 | 1 MiB page / 4 MiB extent / logical-only | VERIFIED | manifests e result configuration |
| P4D-04 | ingestão e packing determinísticos | VERIFIED | semantic/random seed e testes |
| P4D-05 | índice derivado somente do conteúdo | IMPLEMENTED | `record_retrieval.py` |
| P4D-06 | retrieval-only antes do Qwen | VERIFIED | `retrieval-only.json` |
| P4D-07 | dev/holdout sem runtime ground truth | VERIFIED | QA separado; Oracle benchmark-only |
| P4D-08 | ContextBuilder limitado e fontes preservadas | VERIFIED | 2.048-token budget + source IDs |
| P4D-09 | Qwen-only/Standard/Brain/Oracle | VERIFIED | 32 isolated CPU-only runs |
| P4D-10 | semantic vs random packing | VERIFIED | identical Records, holdout comparison |
| P4D-11 | integridade source/record/page | VERIFIED | 66 project tests passing |
| P4D-12 | unknown safety | VERIFIED | two OOD queries, zero pages |
| P4D-13 | FIRST_REAL_END_TO_END_TEST | PASS | query→mmap→context→Qwen→answer |
| P4D-14 | no prefetch/custom physical cache | VERIFIED | KernelOnly; no WILLNEED/COLD/PAGEOUT |

# Neuroarchitecture V2 traceability

Esta seção adiciona requisitos documentais e futuros sem reclassificar nem reescrever fases históricas. `PLANEJADO` e `EXPERIMENTAL` não autorizam implementação.

| ID | Requisito | Componente | Fase | Status | Evidência/benchmark | Observações |
|---|---|---|---:|---|---|---|
| V2-001 | Definir Brain-SSD como arquitetura esparsa, hierárquica, dinâmica e seletiva | Architecture | docs | IMPLEMENTAR AGORA | `NEUROARCHITECTURE_V2.md` | Não definir como RAG em SSD |
| V2-002 | Preservar integralmente Fases 1–4D | Governance | todas | IMPLEMENTAR AGORA | checksums canônicos | Não reescrever resultados |
| V2-003 | Manter Fase 4E como próximo experimento | Governance | 4E | IMPLEMENTAR AGORA | roadmap/physical runner | Antes de qualquer V2 runtime |
| V2-004 | Computar Brain Work Vector multidimensional | Telemetry | 4E+ | PLANEJADO | `COMPUTE_EFFICIENCY.md` | Sem score único inicial |
| V2-005 | Medir Computational Activation | Telemetry | 4E+ | PLANEJADO | CPU time/utilization, tokens, módulos | instructions/cycles quando disponíveis |
| V2-006 | Qualidade acompanha toda eficiência | Evaluation | todas | IMPLEMENTAR AGORA | tabelas com recall/facts/groundedness/OOD | Economia com regressão relevante falha |
| V2-007 | `null` para métrica indisponível | Telemetry | todas | IMPLEMENTAR AGORA | schema/review | Nunca zero inventado |
| V2-008 | Registrar Compute Avoided contra baseline congelado | Evaluation | pós-4E | PLANEJADO | CPU/tokens/bytes/calls/latency deltas | Comparar também com baseline pós-4E |
| V2-009 | Investigar Useful Compute Ratio sem alegar ciclos úteis perfeitos | Evaluation | pós-4E | EXPERIMENTAL | definição por experimento | Fronteiras comparáveis obrigatórias |
| V2-010 | Priorizar Context Compression após 4E, sujeito aos dados físicos | Context | 4F | PLANEJADO | current vs distilled vs Oracle minimal | Sem segundo LLM pesado no baseline |
| V2-011 | Record Distillation seleciona apenas sentenças/fatos úteis | Context | 4F | EXPERIMENTAL | tokens/CPU/quality | Método barato primeiro |
| V2-012 | Required Context Minimization mede desperdício restante | Context | 4F | EXPERIMENTAL | Brain tokens / Oracle tokens | Oracle apenas offline |
| V2-013 | CorticalConnectivityGraph começa shadow-only | Connectivity | 5A | PLANEJADO | predicted vs required/future trace | Sem influência real inicial |
| V2-014 | Separar links semânticos e funcionais | Connectivity | 5A/5C | PLANEJADO | campos/provenance/ablation | Coativação não é causalidade |
| V2-015 | Graph metadata permanece compacta | Resources | 5A | PLANEJADO | RAM/page, 100K/1M projection | Proibido grafo ingênuo/denso |
| V2-016 | Retrieval direto vs seed + graph expansion | Connectivity | 5A | EXPERIMENTAL | Seed/Expanded Recall e Precision | HYBRID permanece baseline |
| V2-017 | Expansão limitada a 0/1/2 hops e budget | Connectivity | 5A | PLANEJADO | pages/MiB/CPU | Nunca expansão ilimitada |
| V2-018 | Excitação altera score, não carrega páginas | Gating | 5B | PLANEJADO | ranking A/B | Prefetch continua separado |
| V2-019 | Inibição possui confidence, decay e override | Gating | 5B | PLANEJADO | False Negative Rate | Evidência atual vence link antigo |
| V2-020 | Medir Inhibition Savings completo | Telemetry | 5B | PLANEJADO | candidates/pages/tokens/CPU | Sempre junto de recall |
| V2-021 | Inibição antes de expansão é hipótese A/B | Gating | 5B | EXPERIMENTAL | before/after ordering | Rejeitar se aumentar misses/custo |
| V2-022 | Coativação atualiza apenas metadata | Plasticity | 5C | PLANEJADO | logs/version/counters | Nenhum arquivo físico online |
| V2-023 | Plasticidade exige suporte, decay, limits e rollback | Plasticity | 5C | PLANEJADO | multi-session holdout | Anti-overfitting obrigatório |
| V2-024 | CognitiveCycleScheduler comparado com always-on | Scheduler | 6 | PLANEJADO | CPU/duty cycle/quality | Incluir overhead de scheduling |
| V2-025 | Medir Module e Compute Duty Cycle | Telemetry | 6 | PLANEJADO | tempo por subsistema | Router/Semantic/Graph/Memory/Core/Skills |
| V2-026 | Registrar `WhyWasIActivated` | Explainability | 5A+ | PLANEJADO | trigger por módulo | Detectar trabalho inútil |
| V2-027 | Activity-silent state não implica atividade/residência | State | 6 | EXPERIMENTAL | stateful vs reexecution | Estado compacto e decaído |
| V2-028 | Context Delta compara full vs delta | Predictive | 7 | EXPERIMENTAL | repeated tokens/CPU/quality | Dependente do Core/runtime |
| V2-029 | ReflexCore possui proteção contra false bypass | Reflex | 7 | PLANEJADO | Core calls avoided/false bypass | Tarefas triviais apenas |
| V2-030 | Memória episódica separada de KnowledgeRecords | Hippocampus | 8 | PLANEJADO | collision/false retrieval | Não misturar indiscriminadamente |
| V2-031 | Formalizar pattern separation/completion | Hippocampus | 8 | EXPERIMENTAL | collision e partial-cue recall | Context Gate é apenas precursor |
| V2-032 | Skills seguem candidate→test→sandbox→version→rollback | Skills | 9 | PLANEJADO | pass/incident/CPU saved | Nenhuma promoção automática |
| V2-033 | Repacking físico somente offline | Consolidation | 10 | PLANEJADO | I/O/layout A/B + recovery | Nunca durante resposta |
| V2-034 | Glia observa recursos sem raciocínio linguístico | Resources | 4C+ | IMPLEMENTAR AGORA | PressureMonitor existente | Expansão futura somente com ganho |
| V2-035 | Homeostase computacional preserva piso de qualidade | Resources | pós-4E | EXPERIMENTAL | perfis de hardware/budgets | PC fraco não justifica destruir recall |
| V2-036 | Não reimplementar mecanismo do SO sem ganho | Architecture | todas | IMPLEMENTAR AGORA | KernelOnly/PAGEOUT results | Não lutar contra hardware |
| V2-037 | Não simular biologia literalmente | Scope | todas | IMPLEMENTAR AGORA | `BIOLOGICAL_PRINCIPLES.md` | Sem spiking/ondas/bioquímica/connectoma artificial |
| V2-038 | Toda hipótese recebe ID/estado/protocolo | Governance | pós-4E | IMPLEMENTAR AGORA | `HYPOTHESIS_REGISTRY.md` | Registro não é autorização |
| V2-039 | Uma hipótese principal por fase | Governance | pós-4E | IMPLEMENTAR AGORA | phase review | Dependências inevitáveis documentadas |
| V2-040 | PC Debian físico é juiz final | Evaluation | 4E+ | IMPLEMENTAR AGORA | physical profiles | Codespaces continua laboratório |

## Regra V2 de autorização

O ciclo obrigatório é `HYPOTHESIS → BASELINE → IMPLEMENTATION → A/B TEST → QUALITY CHECK → RESOURCE CHECK → KEEP/REJECT/CONDITIONAL`. Nenhum requisito futuro acima autoriza Cortical Connectivity, Scheduler, Skills, Prefetch, mudanças no retrieval, Qwen, page size ou runtime da Fase 4D.

# Visual HUD traceability

| ID | Requirement | Status | Evidence |
|---|---|---|---|
| HUD-01 | Observabilidade read-only e removível | IMPLEMENTED | `observability/bus.py`, `hud/state.py` |
| HUD-02 | Evento estruturado e forward-compatible | IMPLEMENTED | `observability/events.py` + testes |
| HUD-03 | Publicação limitada, não bloqueante e fail-open | IMPLEMENTED | bounded deque, dropped counter + testes |
| HUD-04 | UI responsiva Simples/Técnico e animação desligável | IMPLEMENTED | `hud/index.html`, `styles.css`, `app.js` |
| HUD-05 | Demo inequivocamente sintética | VERIFIED | `demo_data=true`, selo e resposta `[DEMO DATA]` |
| HUD-06 | Replay somente com artefatos canônicos da Fase 4D | VERIFIED | `replay.py` + teste contra `end-to-end.json` |
| HUD-07 | Narrativa determinística sem LLM | IMPLEMENTED | `observability/narrator.py` |
| HUD-08 | Privacidade e snapshot atômico | IMPLEMENTED | flags CLI, `snapshots.py` + testes |
| HUD-09 | Overhead medido sem alegar inferência não executada | IMPLEMENTED | `tools/benchmark_hud.py`, métricas indisponíveis nulas |
| HUD-10 | Nenhum algoritmo cognitivo congelado alterado | VERIFIED | HUD isolado em novos módulos/ferramentas |
