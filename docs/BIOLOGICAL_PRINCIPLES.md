# Brain-SSD — Biological Principles Matrix

Status: referências e abstrações para hipóteses computacionais. Este documento não afirma equivalência biológica nem autoriza implementação.

## Regra de linguagem

Brain-SSD é inspirado por princípios funcionais observados em sistemas biológicos. Não é uma simulação de cérebro, connectoma, organoide, neurônio ou consciência.

As relações desta matriz seguem:

```text
observação biológica
  -> abstração computacional limitada
  -> hipótese refutável
  -> componente proposto
  -> benchmark
```

Conectividade não implica causalidade; coativação não implica necessidade; frequência não implica importância; confidence não implica verdade; metadata não é o cérebro.

## Matriz principal

| Referência/observação | Abstração computacional | Hipótese | Componente | Benefício esperado | Risco | Benchmark obrigatório | Status |
|---|---|---|---|---|---|---|---|
| Drosophila: conectividade estruturada, modular e esparsa | Circuitos especializados e ativação seletiva | Modularidade reduz módulos e dados ativados por tarefa | Router, Gate, futura conectividade | Menos Active Brain e CPU | Fragmentação e misses entre módulos | Pipeline esparso vs baseline amplo, com qualidade | Parcialmente implementado em Router/Gate; generalização não provada |
| C. elegans: rede pequena produz comportamento complexo; conectoma isolado é insuficiente | Conectividade deve ser combinada com estado, dinâmica, pesos e feedback | Estado atual melhora seleção sem manter circuitos ativos | Cognitive State, activity-silent state | Menos churn e recomputação | Contaminação de contexto | Stateful vs stateless em topic switch/partial cue | Parcialmente implementado; resultados mistos |
| MICrONS: conectividade funcional não aleatória e like-to-like | Similaridade semântica e coativação funcional são sinais distintos | Links funcionais melhoram retrieval a partir de seeds | CorticalConnectivityGraph shadow | Mais recall/precision com menos busca direta | Grafo grande, overfit e expansão explosiva | Direct retrieval vs seed + 0/1/2 hops | Não implementado |
| Córtex: excitação altera probabilidade de ativação | Link excitativo ajusta candidatura, não residência | Excitação melhora ranking sem prefetch | Excitatory Gating | Menos candidatos avaliados e melhor cobertura | Confundir score com carregamento antecipado | Ranking com/sem link, mesmo budget | Não implementado |
| Córtex: inibição é seletiva, não apenas redução global | Evidência negativa elimina candidatos com confidence, decay e override | Inibição reduz trabalho sem perda de recall | Inhibitory Gating | Menos páginas, contexto e CPU | Falsos negativos | Inhibition Savings + Inhibitory False Negative Rate | Não implementado |
| Organoides: auto-organização e dinâmica coletiva temporal | Metadata funcional pode evoluir; módulos podem executar por fases | Coativação aprendida e phased execution reduzem trabalho | Coactivation learning; CognitiveCycleScheduler | Menos trabalho repetido e menor duty cycle | Instabilidade, custo de coordenação e alegações indevidas | Static vs learned metadata; always-on vs scheduled | Não implementado |
| Neurociência humana: memória de trabalho pode persistir sem atividade contínua de todo circuito | Estado compacto preserva contexto relevante | Activity-silent state reduz execução contínua | Cognitive State compacto | Menos CPU e módulos always-on | Estado desatualizado ou insuficiente | Estado compacto vs reexecução do módulo | Precursor implementado; compute saving não medido |
| Neurociência humana: processamento hierárquico e especialização | Decisão coarse-to-fine e cascade condicional | Representações pequenas evitam carregar detalhe | Router → tópico → página → Record | Menos I/O, contexto e CPU | Early stop incorreto | Custo e qualidade por nível da cascade | Parcialmente implementado |
| Hipocampo: separação e conclusão de padrões | Episódios semelhantes permanecem distintos; pistas parciais recuperam memória | Memória episódica separada reduz colisões | Futuro Hippocampus | Melhor memória contextual | Mistura de episódico e semântico | Collision/false retrieval/partial-cue recall | Memória episódica mínima opt-in no chat (notas explicitamente confirmadas); avaliação biológica e A/B ainda pendentes |
| Cerebelo: automatização de padrões praticados | Raciocínio repetido pode virar Skill validada | Skill reduz Core calls e CPU | Futuro Cerebellum/Skills | Menor TTFT e tokens | Automatizar erro ou executar código inseguro | Core vs Skill, sandbox e rollback | Não implementado |
| Glia/homeostase: suporte e resposta ao estado de recursos | Monitor de recursos informa política sem raciocínio linguístico | Adaptação sob pressão evita trabalho/risco | ResourcePressureMonitor/Glia | Menos reclaim, faults e throttling | Redução de qualidade ou controle excessivo | Perfis de recurso com piso de qualidade | Monitor implementado; adaptação ampla não |
| Paleoneurologia: representação observável é proxy incompleto da estrutura interna | Nenhuma métrica isolada autoriza decisão irreversível | Multi-evidence é mais robusta que proxy único | Cascade e decisões explicáveis | Menos overfit a metadata | Mais custo e complexidade | Ablation por evidência e custo marginal | Princípio documental; parcialmente refletido no HYBRID |

## Equivalentes já implementados

### Esparsidade e modularidade

Router, Gate e HYBRID Retrieval já selecionam uma fração pequena do universo lógico. Isso implementa uma abstração de ativação seletiva, não um circuito biológico.

### Inibição explícita básica

Basal Gating possui candidatos bloqueados e domínios inibidos. Ainda não existe aprendizado de links inibitórios nem Inhibition Savings computacional.

### Estado e histerese

Cognitive State, context modulation/expansion e histerese são precursores de estado dinâmico. A evidência existente também contém regressões, portanto estado não é universalmente benéfico.

### Hierarquia e cascade

LEXICAL → fuzzy/alias → context → semantic rescue → budget/fallback demonstra o princípio cheap-first. A V2 estende esse princípio como direção, sem alterar o retrieval congelado.

### Homeostase física limitada

ResourcePressureMonitor observa cgroup/PSI e a Fase 4C testou hints sob pressão. KernelOnly permanece vencedor padrão; isso reforça “não lutar contra o hardware”.

### Localidade funcional parcial

Semantic packing coloca conteúdo relacionado próximo e melhorou ativação de páginas no MVP real. Isso não é aprendizado de coativação nem conectividade funcional.

## Inspirações ainda não implementadas

- CorticalConnectivityGraph;
- links excitativos/inibitórios aprendidos;
- coactivation learning com decay;
- CognitiveCycleScheduler;
- Module/Compute Duty Cycle operacional;
- ReflexCore;
- memória episódica hipocampal avançada, além de notas manuais do chat;
- compilação de raciocínio em Skills;
- Context Delta no Core;
- consolidação e repacking físico offline;
- auto-organização além de metadata experimental.

## Ideias que não devem ser implementadas literalmente

- neurônios spiking por estética;
- um objeto de software por neurônio ou sinapse;
- connectoma artificial completo;
- frequências theta/gamma simuladas;
- bioquímica e neurotransmissores fictícios;
- organoides como modelo de consciência;
- anatomia como justificativa sem benchmark;
- grafos densos que custem mais do que o retrieval evitado;
- sincronização temporal artificial sem economia mensurável.

## Proteções contra extrapolação

1. Toda abstração recebe hipótese com ID em [HYPOTHESIS_REGISTRY.md](HYPOTHESIS_REGISTRY.md).
2. Toda hipótese mantém baseline não biológico simples.
3. Ganho precisa sobreviver a holdout e ao PC Debian físico.
4. Resultados negativos são preservados.
5. Nenhum proxy isolado produz mutação irreversível.
6. Plasticidade exige suporte entre sessões, decay, logs e rollback.
7. Qualidade e unknown safety acompanham qualquer redução de trabalho.

## Critério de verdade

Linguagem permitida:

> Inspirado no princípio X, o componente Y reduziu a métrica Z no benchmark W sem regressão de qualidade além do limite declarado.

Linguagem proibida:

> O sistema funciona como um cérebro.
