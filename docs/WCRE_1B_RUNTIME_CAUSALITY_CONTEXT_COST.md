# WCRE-1B — Runtime Causality Control + Context Cost Characterization

## Motivo

O WCRE-1 demonstrou vantagem do Core persistente, mas comparou simultaneamente um `llama-completion.exe` do build original com um `llama-server.exe` de outro build. O WCRE-1B preserva esse resultado e introduz um controle intermediário para estimar separadamente os efeitos de build e lifecycle.

Este é um experimento Windows de engenharia. Não é Fase 4F, não modifica retrieval, contexto, prompt, sampling ou arquitetura cognitiva, e não altera o modo padrão subprocess-per-query.

## Matriz causal

- A — `llama-completion.exe` original, processo novo por query.
- B — `llama-completion.exe` compilado no mesmo `build-win-persistent` de C, processo novo por query.
- C — `llama-server.exe` do build experimental, modelo persistente e uma única vaga de inferência.

A→B é a estimativa controlada do efeito de build. B→C é a estimativa controlada da persistência. A→C mantém comparabilidade com WCRE-1. Como os executáveis completion/server ainda têm caminhos internos distintos, o relatório não afirma causalidade perfeita.

São usados 4 threads, CPU-only, temperatura 0, contexto máximo 4096 e ordem intercalada com seed `20260821`. Cada condição executa tiny/short/medium cinco vezes na matriz canônica.

## Curva de custo de contexto

O Core C é aquecido antes da coleta. Prompts sintéticos neutros usam aproximadamente 0, 128, 256, 512, 768, 1024, 1536, 2048 e 3072 tokens adicionais, com saída curta e fixa. O valor analisado é `actual_prompt_tokens`, reportado pelo backend após tokenização. Há cinco repetições canônicas por ponto, em ordem determinística randomizada.

O resumo apresenta prompt eval, TTFT, CPU e memória, regressão linear apenas descritiva, R² calculado e custos marginais em quatro regiões. Nenhuma linearidade é presumida. Outliers são marcados com 1,5×IQR dentro de cada ponto e nunca removidos.

## Referência Brain-SSD real

Um conjunto pequeno de queries reais passa pelo pipeline congelado em A/B/C. Page IDs, record IDs, ordem, source IDs, Active Brain, hash de contexto e hash de configuração devem permanecer idênticos. O contexto real não é cortado.

A referência histórica de aproximadamente 1963 tokens é posicionada na curva. Qualquer comparação com 512 tokens é rotulada `THEORETICAL_ONLY`: não testa nem promete preservação de qualidade.

## Imutabilidade e ruído

Digests de Fase 4D, Fase 4E, Fase 4E-W, Windows Native e WCRE-1 são registrados antes e depois. Carga de CPU e RAM disponível são amostradas antes da matriz; temperatura permanece `NOT_MEASURED`. Todos os raws são imutáveis e os summaries derivados ficam separados.

## Execução

```powershell
.\.venv\Scripts\python.exe tools\run_windows_core_runtime_1b.py --all
```

Para validar rapidamente a implementação, sem produzir resultado canônico:

```powershell
.\.venv\Scripts\python.exe tools\run_windows_core_runtime_1b.py --all --quick
```

Os resultados ficam exclusivamente em `results/windows_core_runtime_1b/`. Os valores medidos e a decisão final são publicados em `SUMMARY.md` e `summary.json` nesse diretório.

## Limitações

- Executáveis completion e server não são internamente idênticos; a atribuição é uma estimativa controlada.
- Contadores de transferência de processo Windows não equivalem a leituras físicas do SSD.
- Temperatura não é medida.
- A curva sintética isola o Core, mas não substitui a validação com prompts reais.
- O experimento não testa compressão, qualidade após redução de contexto, Fase 4F, Fase 5 ou prefetch.

## Resultado canônico — 21 de agosto de 2026

O matrix ID `matrix-20260821T163229Z-98276e299d` terminou `PASS`. Foram preservados 45 runs causais, 45 runs sintéticos, 15 runs reais e 23 queries durante 308,89 segundos de sanity sustentado. Não houve erro de execução.

### Causalidade

| Mediana | A original | B build experimental | C persistente |
|---|---:|---:|---:|
| TTFT (ms) | 1034,32 | 1032,48 | 146,23 |
| Latência total (ms) | 1446,94 | 1447,35 | 344,50 |
| Prompt tokens/s | 132,63 | 129,41 | 191,05 |
| Generation tokens/s | 35,18 | 35,58 | 40,56 |
| CPU (s) | 3,078 | 3,125 | 1,359 |
| Working Set (bytes) | 1.176.162.304 | 1.176.137.728 | 1.206.415.360 |
| Private Bytes | 913.416.192 | 913.367.040 | 620.486.656 |

A→B alterou a latência em apenas `+0,41 ms` (`+0,03%`). B→C reduziu `1102,84 ms` (`-76,20%`) e o TTFT em `886,26 ms` (`-85,84%`). A estimativa controlada atribui aproximadamente `100,04%` do ganho total de latência A→C à persistência; o valor passa ligeiramente de 100% porque B foi marginalmente mais lento que A. `ENG-CORE-002 = SUPPORTED`.

### Custo de contexto

| Rótulo aproximado | Tokens reais | Prompt eval (ms) | TTFT (ms) | CPU (s) |
|---:|---:|---:|---:|---:|
| 0 | 39 | 211,47 | 221,88 | 1,109 |
| 128 | 180 | 872,15 | 882,85 | 3,766 |
| 256 | 322 | 1623,73 | 1650,88 | 6,813 |
| 512 | 603 | 3122,74 | 3134,33 | 12,797 |
| 768 | 883 | 4723,27 | 4734,61 | 19,188 |
| 1024 | 1165 | 6649,24 | 6661,29 | 26,891 |
| 1536 | 1729 | 10625,43 | 10637,80 | 42,891 |
| 2048 | 2290 | 14994,69 | 15007,59 | 60,203 |
| 3072 | 3418 | 25629,75 | 25644,59 | 102,781 |

A regressão linear descritiva de prompt eval tem inclinação de `7,3946 ms/token` e R² `0,98769`; a forma observada fica progressivamente mais cara, portanto a linearidade não é assumida. O custo marginal medido foi 516,18, 627,49, 741,82 e 942,82 ms por 100 tokens nas quatro regiões sucessivas. `ENG-CORE-003 = SUPPORTED` e `PHASE_4F_CONTEXT_REDUCTION_PRIORITY = SUPPORTED_BY_MEASUREMENT`, sem iniciar a Fase 4F.

### Contextos reais e estabilidade

A mediana real foi 2083 tokens em A/B e 2087 em C; a diferença de quatro tokens vem do envelope de chat do endpoint server, enquanto o contexto Brain-SSD, IDs e configuration hash permaneceram idênticos. Page IDs, record IDs/ordem, source IDs, Active Brain e context SHA-256 foram equivalentes em 5/5 queries.

O comportamento de qualidade e `NO_KNOWLEDGE` também foi equivalente entre os runtimes, mas o sanity absoluto do baseline congelado passou somente em 2/5 queries: três falhas já pertencem ao pipeline/modelo congelado e não foram corrigidas neste experimento de runtime.

O Core persistente terminou classificado `STABLE`, com Working Set mediano de 1.207.795.712 bytes, crescimento de 2.060.288 bytes e Private Bytes mediano de 620.986.368 bytes, crescimento de 1.323.008 bytes. A estimativa de `10.302,41 ms` entre o prompt real mediano e o ponto sintético 512 está rotulada `THEORETICAL_ONLY`; preservação de qualidade não foi testada.

Os digests antes/depois de Fase 4E-W (`baf5863a...8713`) e WCRE-1 (`241eb6b3...e1ce`) coincidiram. O WCRE-1 permaneceu com o SHA-256 de summary `25e26288...9c6b`.
