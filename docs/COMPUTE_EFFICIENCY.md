# Brain-SSD — Compute Efficiency

Status: especificação de métricas e protocolo. Nenhuma nova otimização de runtime é implementada por este documento.

## Pergunta central

> Quanto trabalho completo foi necessário para produzir uma resposta correta e fundamentada?

Memória e I/O continuam importantes, mas não bastam. Um sistema pode ativar poucos MiB e ainda gastar CPU excessiva processando candidatos, contexto ou etapas redundantes.

## Computational Activation

Computational Activation representa o trabalho executado pela consulta. Registrar, quando tecnicamente possível:

- wall time;
- CPU user/system e CPU total;
- utilização média e máxima de CPU;
- instructions e cycles;
- context switches voluntários/involuntários;
- prompt tokens processados;
- generation tokens;
- módulos/circuitos executados;
- etapas cognitivas executadas;
- temperatura, frequência e throttling;
- energia, quando disponível e confiável.

Campo indisponível deve ser `null` com motivo e fonte de indisponibilidade. Nunca converter ausência em zero.

## Brain Work Vector

Não condensar inicialmente as dimensões em um score único.

```text
BrainWork = {
  quality: {
    required_fact_score,
    retrieval_recall,
    retrieval_precision,
    groundedness,
    unknown_safe
  },
  activation: {
    active_pages,
    active_bytes,
    active_brain_rate,
    modules_activated,
    cognitive_steps
  },
  retrieval: {
    candidate_count,
    inhibited_candidates,
    retrieved_records,
    retrieved_record_bytes,
    discarded_records
  },
  context: {
    context_tokens,
    useful_context_tokens,
    redundant_context_tokens,
    prompt_tokens_processed
  },
  compute: {
    router_cpu_ms,
    semantic_cpu_ms,
    graph_cpu_ms,
    storage_cpu_ms,
    context_builder_cpu_ms,
    prompt_eval_cpu_ms,
    generation_cpu_ms,
    total_cpu_ms,
    instructions,
    cycles,
    context_switches
  },
  storage: {
    logical_bytes,
    physical_read_bytes,
    major_faults,
    minor_faults
  },
  timing: {
    ttft_ms,
    prompt_eval_ms,
    generation_ms,
    total_latency_ms
  },
  system: {
    rss_peak_bytes,
    pss_peak_bytes,
    temperature_c,
    throttling,
    energy_j
  }
}
```

O schema físico poderá diferir, mas não deve perder a separação entre dimensões.

## Active Brain Rate

```text
Active Brain Rate = activated eligible bytes / total eligible capacity
```

Reportar numerador, denominador e unidade. A métrica é inválida como objetivo isolado: deve aparecer ao lado de qualidade e trabalho computacional.

## Compute Avoided

Para uma otimização `candidate` contra baseline congelado:

```text
CPU ms avoided            = baseline CPU ms - candidate CPU ms
Context tokens avoided    = baseline context tokens - candidate context tokens
Page bytes avoided        = baseline active bytes - candidate active bytes
Physical bytes avoided    = baseline read bytes - candidate read bytes
Core invocations avoided  = baseline calls - candidate calls
Latency avoided           = baseline total latency - candidate total latency
```

Sempre registrar `ANTES`, `DEPOIS`, `DELTA` absoluto e percentual. Delta negativo é regressão e não deve ser ocultado por outra dimensão.

## Useful Compute Ratio

Useful Compute Ratio é experimental. Não é possível identificar perfeitamente cada ciclo útil. Uma aproximação inicial pode separar trabalho com contribuição observável de desperdício identificável:

```text
Useful Compute Ratio = contributing measured work / total measured work
```

Possíveis fontes de desperdício observável:

- Records recuperados e não usados;
- sentenças/contexto sem relação com fatos requeridos;
- candidatos descartados após etapa cara;
- reprocessamento idêntico entre turnos;
- módulos ativados sem alterar candidatos, contexto ou resposta;
- expansão de grafo que não adiciona página relevante;
- Skills candidatas que chamam o Core de qualquer forma.

Essa razão deve ser acompanhada pela definição operacional usada em cada experimento. Não comparar razões construídas com fronteiras diferentes.

## Inhibition Savings

Para experimentos futuros:

```text
Inhibition Savings = {
  candidates_eliminated,
  pages_not_activated,
  context_tokens_avoided,
  cpu_ms_avoided
}
```

Registrar junto:

- Inhibitory False Negative Rate;
- recall e required-fact score;
- overrides por evidência atual;
- custo de calcular a inibição.

Inibição que economiza trabalho mas destrói recall é rejeitada.

## Duty Cycle

Para Scheduler futuro:

```text
Module Duty Cycle = module execution time / total processing time
```

Medir separadamente Router, Semantic Rescue, Connectivity Graph, Memory, Context Builder, Core e Skills. `WhyWasIActivated` deve registrar o trigger de cada módulo.

O benchmark compara obrigatoriamente:

- `ALWAYS_ON_PIPELINE`;
- `CYCLE_SCHEDULED_PIPELINE`.

O scheduler é rejeitado se tempo de decisão, sincronização ou perda de paralelismo superar a economia.

## Repeated Context Processing

Para Delta Processing futuro, medir:

- tokens repetidos entre turnos;
- tempo/CPU de prompt eval repetido;
- bytes de contexto reconstruídos sem mudança;
- estado compacto reutilizado;
- diferença de qualidade entre full e delta.

```text
Context Delta = nova informação necessária + estado relevante alterado
```

O runtime atual pode limitar o quanto essa hipótese é testável; limitações devem ser explícitas.

## Required Context Minimization

Após a Fase 4E, Context Compression deve comparar:

- contexto Brain-SSD atual;
- Record Distillation barato;
- Oracle Minimal Context offline.

Métricas:

- context tokens;
- required-fact quality;
- groundedness;
- TTFT/prompt eval;
- CPU total;
- tempo e CPU do compressor;
- tokens removidos incorretamente.

Um segundo LLM pesado por query não é o baseline inicial, pois desloca o custo.

## Protocolo A/B obrigatório

1. Congelar dataset, split, seed, Core, modelo, page size e ambiente.
2. Declarar uma hipótese principal.
3. Executar baseline e candidato em ordem randomizada quando aplicável.
4. Separar cold/warm.
5. Preservar runs individuais e configuração.
6. Medir qualidade antes de eficiência.
7. Reportar mediana/faixa; percentis apenas com amostra adequada.
8. Comparar com a fase anterior e com o baseline pós-4E.
9. Classificar `SUPPORTED`, `REJECTED`, `CONDITIONAL` ou `INCONCLUSIVE`.
10. Preservar regressões por workload e perfil de hardware.

## Guardrails de qualidade

Toda tabela de eficiência inclui:

- retrieval recall/precision;
- fatos requeridos;
- answer correctness;
- groundedness/provenance;
- unknown/OOD safety.

Uma redução de recursos só é aceita dentro de um limite de qualidade declarado antes do experimento. O limite físico da Fase 4E continua definido em [PHYSICAL_END_TO_END.md](PHYSICAL_END_TO_END.md); fases posteriores devem declarar seus próprios limites sem reescrever esse critério.

## Instrumentação da Fase 4E

A Fase 4E deve estabelecer o primeiro Brain Work Vector físico do V0 congelado. Além dos campos já previstos, a análise deve separar quando disponíveis:

- retrieval/router CPU;
- ContextBuilder CPU;
- prompt eval e geração;
- tokens de prompt e geração;
- contexto por resposta;
- temperatura/frequência/throttling;
- cold/warm I/O e faults;
- memória do processo e do sistema/cgroup.

Adicionar observabilidade não autoriza alterar o algoritmo congelado. Se uma métrica exigir mudança funcional, ela fica `null` e é planejada para uma fase posterior.

## Critério final

Codespaces é laboratório. Uma otimização só entra na arquitetura quando melhora o vetor relevante no PC Debian físico e preserva qualidade. Eficiência deve existir no computador real, não apenas no diagrama.

## Evidência medida — Phase 4F-W Windows

A matriz canônica Windows `matrix-20260822T101155Z-c4de1dc8b4` comparou 14 queries em 11 condições com o Persistent Core congelado. O melhor resultado operacional foi pruning pós-retrieval, sem alterar Router/Gate:

- actual prompt tokens medianos: 1917 → 1040 (`-45,75%`);
- prompt eval: 11.415,67 → 5.339,05 ms (`-53,23%`);
- TTFT: 11.430,85 → 5.351,63 ms (`-53,18%`);
- CPU: 54,15 → 32,10 s (`-40,72%`);
- custo do selector: 1,69 ms wall mediano;
- correctness: 28,57% → 35,71%;
- OOD safety: 100% → 100%;
- Context Fact Recall: 92,86% → 85,71%.

O ganho líquido de compute é real, porém a queda de Context Fact Recall impede adoção. Resultado arquitetural `CONDITIONAL`, evidence scope `small_real_corpus_evidence`. Isso não conclui a Phase 4F canônica Debian nem muda o ContextBuilder V0.
