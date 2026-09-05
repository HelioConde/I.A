# Phase 4F-W — Context Efficiency / Minimal Useful Context

## Escopo

Phase 4F-W é uma experiência Windows Native Functional, motivada pela curva WCRE-1B. Ela mede se o Brain-SSD pode enviar menos evidência ao Qwen sem perder qualidade. Não é a Phase 4F canônica: `phase4f_windows_experimental=true`, `phase4f_canonical=false` e `phase4e_valid=false`.

O Persistent Core permanece opt-in e congelado no SHA-256 `ecf6207498a81df80ac753c60243e9a2fbdf9f046c9e8195a61a83e507cc7dc0`. O Qwen3-0.6B Q8_0, commit llama.cpp, quatro threads, CPU-only, prompt de segurança e configuração de geração não mudam.

## Separação arquitetural

```text
Knowledge Activation
  → frozen Record Retrieval
  → experimental Attentional Distillation
  → Core Context
```

Knowledge Activation, Context Activation e Core Compute são métricas diferentes. Na primeira etapa, Router, Gate, Active Pages, Records recuperados e Active Brain permanecem idênticos ao V0.

## ContextBuilder V0

`ContextBuilder(2048)` e `build_prompt()` permanecem intactos. O V0 continua disponível e é reconstruído em cada query como baseline. Nenhuma variante experimental é default global.

## Oracle Minimal Context

O Oracle é uma aproximação offline de set cover sobre sentenças/trechos originais do corpus. Ele pode consultar required facts e ground truth, mas é marcado `evaluation_only=true` e `oracle_runtime_allowed=false`. Seu gap mostra oportunidade potencial, não ganho de produção garantido.

## ContextDistiller

O `ContextDistiller` é determinístico, barato e extrativo. Ele combina overlap lexical, score congelado do Record, relevância de heading, proteção estrutural de código e posição. Cada unidade preserva record ID, source ID, page ID, offsets, heading e tipo. Texto novo não é inventado.

Deduplicação usa similaridade lexical alta e mede tokens removidos. Blocos reconhecidos como código não são cortados. O budget escolhe unidades inteiras; nunca aplica truncamento de prefixo.

## Record pruning

O `RecordPruner` roda somente depois do retrieval congelado. Ele ranqueia contribuição e protege Records com termos de query que não aparecem nos demais (`contains_unique_evidence`). Pruning-only e pruning+extractive são ablations separadas.

## Matriz

- 14 queries congeladas: 6 DEV e 8 HOLDOUT.
- Budgets: 256, 384, 512, 768, 1024, 1280 e 1536, além do V0.
- Variantes: V0, Oracle evaluation, Extractive por budget, pruning-only e combined.
- O budget combinado é congelado usando somente Context Fact Recall DEV antes da inferência HOLDOUT.
- Ordem intercalada determinística com seed `20260822`.
- Core aquecido e `cache_prompt=false` por request.

## Métricas e quality gate

Context Fact Recall é separado de Answer Fact Recall. Também são medidos correctness, grounding, OOD safety, falso `NO_KNOWLEDGE`, records recuperados/mantidos/removidos, densidade, tokens por fato, composição do prompt, prompt eval, TTFT, CPU, latency e custo do Distiller.

A decisão segue qualidade → grounding → safety → tokens → velocidade. Um candidato não pode esconder uma regressão por query em uma média agregada.

## Runner e retomada

```powershell
$env:PYTHONPATH='src'
.\.venv\Scripts\python.exe tools\run_phase4fw_context_efficiency.py --dry-run
.\.venv\Scripts\python.exe tools\run_phase4fw_context_efficiency.py --all --quick
.\.venv\Scripts\python.exe tools\run_phase4fw_context_efficiency.py --all
```

Cada par query/variante é persistido imediatamente. Para retomar:

```powershell
.\.venv\Scripts\python.exe tools\run_phase4fw_context_efficiency.py --all --resume-matrix <matrix-id>
```

## Limitações

- Evidência de corpus real pequeno; não extrapolar diretamente para 20 GB.
- O Oracle não é runtime e pode localizar fatos fora do retrieval inicial.
- Componentes de composição do prompt são estimados; o total é reportado pelo tokenizer/backend.
- O corpus/ground truth congelado contém pelo menos um caso em que o Record esperado não carrega todos os fatos declarados.
- Temperatura e energia não são medidas.
- Nenhum segundo LLM, embedding neural novo, cache, Context Delta, Reflex, connectivity, prefetch ou Skill é usado.

Os resultados canônicos Windows são registrados em `results/phase4fw/PHASE4FW_SUMMARY.md`. A Phase 4E Debian continua pendente e a Phase 4F canônica continua não iniciada.

## Resultado canônico Windows — 22 de agosto de 2026

O matrix ID `matrix-20260822T101155Z-c4de1dc8b4` terminou `PASS` com 154/154 runs, seis queries DEV e oito HOLDOUT. O budget combinado selecionado exclusivamente por Context Fact Recall DEV foi 1536.

### Baseline, Oracle e melhor variante

| Métrica mediana/agregada | V0 | Oracle evaluation | Pruning-only |
|---|---:|---:|---:|
| Actual prompt tokens | 1917 | 184 | 1040 |
| Context Fact Recall | 92,86% | 89,29% | 85,71% |
| Answer Fact Recall | 45,24% | 35,71% | 47,62% |
| Correctness | 28,57% | 28,57% | 35,71% |
| Grounding | 28,57% | 57,14% | 50,00% |
| OOD safety | 100% | 100% | 100% |
| False NO_KNOWLEDGE | 5 | 5 | 5 |
| Prompt eval | 11.415,67 ms | 811,90 ms | 5.339,05 ms |
| TTFT | 11.430,85 ms | 823,25 ms | 5.351,63 ms |
| CPU | 54,15 s | 5,66 s | 32,10 s |

O Oracle Gap mediano por query foi 1673,5 tokens. O Oracle permanece evaluation-only e não é candidato de produção.

Pruning-only reduziu 877 tokens (`45,75%`), prompt eval em 6076,62 ms (`53,23%`), TTFT em 6079,22 ms (`53,18%`), CPU em 22,05 s (`40,72%`) e latency total em 5486,92 ms (`40,32%`). Seu custo mediano foi 1,69 ms de wall; CPU ficou abaixo da resolução do contador Windows (`0,0 ms` mediano). Economia líquida de wall estimada: 6074,93 ms.

### Quality gate

Pruning-only recuperou medianamente 8 Records, manteve 3 e removeu 5. Context Density passou de 4,10% para 7,31%; Tokens Per Required Fact de 940,25 para 474,75. Nenhum token duplicado foi removido neste corpus.

Não houve regressão de correctness por query contra V0. `holdout_thread_modes` melhorou: os mesmos fatos permaneceram no contexto, grounding passou e o prompt caiu de 1792 para 891 tokens. O caso é marcado `CONTEXT_OVERLOAD_CANDIDATE`.

Entretanto, Context Fact Recall agregado caiu de 92,86% para 85,71% porque `holdout_busy_typo` perdeu o fato no contexto pruning. Essa query já era `RETRIEVAL_MISS` no V0 e continuou incorreta, mas a perda impede `KEEP_CANDIDATE`. A classificação final é `CONDITIONAL`.

### Budgets e Minimal Useful Context

Budgets 256/384/512/768/1024/1280/1536 produziram medianas reais de 385,5/530,5/673/948/1230,5/1526,5/1823 tokens. Nenhum budget extractive dominou o V0 em todo o quality gate.

Minimal Useful Context foi identificado em 5/14 queries, com mediana de 358 tokens entre os casos resolvidos: os dois OOD, JSON frames, WAL checkpoint e thread modes. Isso sustenta HYP-4FW-005 apenas condicionalmente.

A fronteira de Pareto contém `EXTRACTIVE_B256` e `PRUNING_ONLY`. Pruning-only é a melhor variante operacional, mas permanece opt-in experimental e condicional.

### Imutabilidade e conclusão

Active Brain foi equivalente, com mediana 3 MiB neste conjunto ampliado. O Distiller não cria índice ou metadata persistente adicional; working memory transitória não foi medida separadamente. Os digests de Phase 4D, 4E, 4E-W, Windows Native, WCRE-1 e WCRE-1B coincidiram antes/depois.

Resultado das hipóteses: HYP-4FW-001 `CONDITIONAL`; HYP-4FW-002 `SUPPORTED`; HYP-4FW-003 `SUPPORTED`; HYP-4FW-004 `SUPPORTED`; HYP-4FW-005 `CONDITIONAL`.

`PHASE_4F_W = PASS`, mas a recomendação arquitetural é `CONDITIONAL`. ContextBuilder V0 e default global continuam intactos. Phase 4E Debian segue `PENDING`; Phase 4F canônica, Phase 5 e prefetch continuam `NOT_STARTED`.
