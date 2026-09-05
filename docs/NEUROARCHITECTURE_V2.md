# Brain-SSD — Neuroarchitecture V2

Status: realinhamento arquitetural documental. Nenhum componente V2 está implementado. A Fase 4E continua sendo o próximo experimento canônico.

## Definição oficial

Brain-SSD é uma arquitetura cognitiva esparsa, hierárquica, dinâmica e seletiva. O sistema procura ativar apenas os circuitos necessários para a tarefa atual e combinar roteamento, inibição, memória, associação, previsão e automatização para reduzir memória, movimentação de dados e computação sem sacrificar qualidade.

Brain-SSD não é “RAG armazenado em SSD”. O SSD é uma camada física de capacidade fria. O princípio arquitetural é:

```text
capacidade total grande >> atividade instantânea pequena
```

A pergunta central passa a ser:

> Quanto do cérebro e quanto do computador precisaram trabalhar para produzir esta resposta?

## Objetivo operacional

Um computador com aproximadamente 8 GB de RAM e CPU comum deve conseguir executar uma IA útil com:

- CPU-only funcional e GPU opcional;
- grande capacidade de conhecimento persistente;
- pequena fração ativa por tarefa;
- contexto reduzido;
- memória controlada;
- trabalho computacional proporcional à dificuldade;
- caminhos rápidos para tarefas simples;
- expansão somente quando necessária.

Eficiência nunca é avaliada isoladamente. Toda redução de CPU, RAM, I/O, tokens ou latência deve ser acompanhada por qualidade de retrieval, fatos requeridos, correção, groundedness e segurança para unknown/OOD.

## Baseline congelado

As Fases 1–4D permanecem históricas e intactas. A identidade operacional congelada inclui:

- Qwen3-0.6B Q8_0, CPU-only;
- LogicalCorticalPage de 1 MiB;
- StorageExtent de 4 MiB;
- acesso `logical-only` por `mmap` read-only;
- Linux page cache como controlador físico padrão;
- HYBRID Router com TF-IDF Semantic Rescue;
- Cognitive Cache em shadow mode;
- nenhuma cópia persistente de páginas em cache anônimo;
- `MADV_PAGEOUT` rejeitado como política rotineira;
- `MADV_COLD` somente experimental sob pressão;
- KnowledgeRecords reais de Python/SQLite integrados ao Core;
- `FIRST_REAL_END_TO_END_TEST = PASS`.

Esse baseline não deve ser reescrito para acomodar a V2. Novos experimentos serão adicionados em fases separadas e comparados tanto com a fase imediatamente anterior quanto com o baseline pós-4E congelado.

## Próximo passo obrigatório

A Fase 4E — Physical TARGET_8GB Validation — continua sendo o próximo teste executável. Ela deve medir o V0 congelado em hardware Debian físico antes de qualquer implementação neuroarquitetural nova.

O baseline físico deve registrar CPU, RAM, SSD, cold/warm, TTFT, prompt processing, geração, I/O físico, faults, temperatura, throttling e qualidade. Os dados da máquina física podem alterar a prioridade das hipóteses V2.

## Princípios estruturais

### Ativação esparsa

`TOTAL BRAIN >> ACTIVE BRAIN` permanece central. Active Brain Rate mede bytes, páginas ou circuitos ativados sobre capacidade elegível total. Uma ativação menor que reduz qualidade não representa ganho.

### Hierarquia coarse-to-fine

O sistema deve decidir com a representação mais barata suficiente:

1. intenção/domínio;
2. tópicos;
3. circuitos/páginas;
4. KnowledgeRecords;
5. conteúdo detalhado.

Metadata deve permitir decisões sem ler o conteúdo integral da página. Detalhe só é materializado quando necessário.

### Cascade condicional

O padrão validado na Fase 3.75 deve ser reutilizado: caminho barato primeiro, seguido por níveis progressivamente mais caros apenas quando faltarem evidência ou cobertura. Todo componente futuro deve registrar `WhyWasIActivated`.

### Estado compacto e activity-silent

Estado cognitivo recente pode sobreviver de forma compacta sem manter o circuito computacional executando. Tópico, confiança, idade e páginas recentes não implicam residência física nem atividade contínua.

### Separação lógico-física

Roteamento, gating, cache lógico e conectividade não controlam automaticamente residência física. O sistema operacional permanece soberano enquanto não houver evidência de que uma intervenção melhora o computador real.

## Fluxo conceitual de longo prazo

```text
INPUT
  -> REFLEX / STEM
  -> THALAMIC ROUTER
  -> BASAL GATING
  -> SEED CORTICAL CIRCUITS
  -> EXCITATORY / INHIBITORY CONNECTIVITY
  -> COGNITIVE STATE
  -> SELECTIVE KNOWLEDGE / MEMORY
  -> COGNITIVE CYCLE SCHEDULER
  -> SMALL CORE
  -> PREDICTION / ERROR
  -> expansão somente se necessária
  -> ANSWER

Em paralelo:
  GLIA / RESOURCE MONITOR
  Cognitive Cache shadow
  Hippocampus
  Cerebellum / Skills
  Consolidation
```

Esse fluxo é direção de pesquisa, não descrição do runtime atual.

## Risco de reduzir o projeto a RAG

O runtime atual possui um caminho semelhante a RAG porque recupera documentação e a envia ao Core. Esse caminho foi necessário para validar conhecimento real, mas não esgota a arquitetura. Há risco de desvio se o projeto:

- otimizar apenas retrieval, ranking e chunking;
- tratar Active Brain como simples quantidade de documentos recuperados;
- medir somente bytes de SSD/RAM sem CPU e prompt processing;
- adicionar cada vez mais contexto para comprar recall;
- ignorar estado, inibição, temporalidade, memória episódica e caminhos rápidos;
- chamar qualquer expansão de retrieval de “circuito cortical” sem nova evidência;
- confundir metadata ou grafo documental com cognição.

O antídoto é manter Brain Work Vector, comparação física, modularidade, hipóteses separadas e quality guardrails. Context Compression é a primeira oportunidade de reduzir o custo RAG-like já observado; Connectivity, Scheduler, Hipocampo e Skills permanecem hipóteses posteriores.

## Componentes futuros e fronteiras

### Context Compression — provável primeira prioridade pós-4E

A Fase 4D ativou em média cerca de 2,6 MiB, mas enviou aproximadamente 1.700 tokens e mediu TTFT próximo de 11,7 s. A hipótese prioritária é que o próximo ganho venha de reduzir contexto, não de otimizar SSD.

Começar com métodos baratos de Record Distillation e Required Context Minimization. Um segundo LLM pesado por consulta não é baseline aceitável.

### CorticalConnectivityGraph — shadow first

O grafo poderá armazenar relações semânticas estáticas e relações funcionais aprendidas separadamente. Links excitativos alteram candidatura/score; não carregam páginas. Links inibitórios removem candidatos apenas com confiança, decay e override por nova evidência.

Metadata proposta, sujeita a benchmark:

- `excitatory_links`;
- `inhibitory_links`;
- `coactivation_links`;
- `transition_strength`;
- `functional_similarity`;
- `activation_frequency`;
- `last_coactivation`;
- `confidence`;
- `age`.

Não criar grafo ingênuo, expansão ilimitada ou repacking online. O primeiro experimento será shadow-only e comparará retrieval direto com seed + expansão de 0/1/2 hops sob budget explícito.

### Excitação e inibição

Excitação melhora ranking de candidatos relacionados; não é prefetch. Inibição deve ocorrer antes de expansão quando essa ordem reduzir trabalho sem criar falsos negativos. Toda inibição é reversível e vencida por evidência atual mais forte.

### Plasticidade controlada

Coativação funcional e transições podem ser aprendidas somente em metadata, com versão, contador, suporte mínimo, confidence, decay, logs, limites e rollback. Poucas sessões não podem definir verdade global. Layout físico só poderá ser proposto por consolidação offline.

### CognitiveCycleScheduler

O scheduler futuro investiga quando e por quanto tempo módulos executam. Deve ser comparado com pipeline `ALWAYS_ON`; será rejeitado se o overhead exceder a computação evitada. Não simula frequências ou ondas biológicas.

### ReflexCore e Skills

ReflexCore poderá resolver tarefas triviais sem invocar o pipeline completo. Skills poderão transformar raciocínio repetido e validado em execução barata. Nenhuma Skill entra automaticamente: candidato, testes, sandbox, versão e rollback são obrigatórios.

### Hipocampo

Memória episódica permanece separada de conhecimento semântico/documental. Pattern separation e completion serão testados por colisão, false retrieval e recuperação por pista parcial.

### Glia / Resource Manager

Glia observa recursos, não raciocina linguisticamente. Pode fornecer RAM, PSI, reclaim, I/O, CPU, temperatura, cache e throttling ao scheduler. Adaptação de orçamento deve preservar um piso de qualidade.

## Proibições permanentes sem hipótese específica

Não implementar por estética biológica:

- spiking neurons em Python;
- milhões de objetos “neurônio”;
- ondas theta/gamma artificiais;
- neurotransmissores ou bioquímica fictícia;
- sincronizações artificiais caras;
- connectoma artificial completo;
- alegações de consciência;
- repacking físico durante resposta;
- prefetch disfarçado de excitação;
- proxies isolados como verdade ou causalidade.

## Regra experimental

Toda hipótese segue:

```text
HYPOTHESIS
  -> BASELINE
  -> IMPLEMENTATION
  -> A/B TEST
  -> QUALITY CHECK
  -> RESOURCE CHECK
  -> KEEP / REJECT / CONDITIONAL
```

Apenas uma hipótese principal por fase, salvo dependências inevitáveis. Nenhuma proposta V2 altera a arquitetura oficial antes de produzir ganho mensurável no PC Debian físico.

## Métricas centrais

Além de Active Brain Rate, todo experimento deve produzir um Brain Work Vector com memória, I/O, contexto e computação. A especificação está em [COMPUTE_EFFICIENCY.md](COMPUTE_EFFICIENCY.md). Hipóteses e estados estão em [HYPOTHESIS_REGISTRY.md](HYPOTHESIS_REGISTRY.md), e a tradução cautelosa da biologia está em [BIOLOGICAL_PRINCIPLES.md](BIOLOGICAL_PRINCIPLES.md).

## Estado deste documento

Este documento realinha definição, linguagem e ordem experimental. Ele não autoriza Cortical Connectivity, Scheduler, Skills, Prefetch, mudanças de retrieval, Qwen, page size ou runtime da Fase 4D.
