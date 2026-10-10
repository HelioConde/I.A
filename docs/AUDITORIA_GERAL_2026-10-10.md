# Brain-SSD — Auditoria geral e prioridades (10/10/2026)

> Revisão do código-fonte, documentação, matrizes históricas e GitHub Actions. Não é certificação de hardware, qualidade do modelo ou segurança de produção.

## Objetivo prioritário do usuário

1. Rodar localmente no Windows 10/11, com UI simples semelhante a chat.
2. Receber mensagens como 'Olá' e responder de verdade por CPU, sem API externa.
3. Reduzir RAM e dispensar GPU dedicada (VRAM não obrigatória), usando SSD seletivamente.
4. Demonstrar as melhorias com medição reprodutível, sem piorar respostas.

## Mapa do que está comprovado

| Subsistema | Evidência | Estado/limite |
| --- | --- | --- |
| Chat Windows | Interface, SSE, histórico SQLite, Parar, testes mock | Implementado em código; diálogo real no PC do usuário não validado aqui |
| Launcher Windows | Actions compilam BrainSSD.exe | Executável é launcher, não instalador autônomo nem pacote de modelo |
| Modelo CPU-only | Baseline Qwen3-0.6B Q8_0 via llama.cpp | Modelo e binários ausentes do repositório; dependem do PC local |
| Storage | mmap, páginas 1 MiB, 4 MiB extent, manifests com hashes | brain.dat físico não está versionado; é necessário para retrieval SSD |
| Router/Gate | HYBRID + TF-IDF; testes determinísticos | Roteamento seletivo de registros; não equivale à V2 implementada |
| Cache | Testes de políticas, benchmarks físicos anteriores | Medição lógica não significa liberar RAM física automaticamente |
| Windows 4E-W | PASS_WITH_WARNINGS documentado | Não certifica 8 GiB e não substitui 4E Debian |
| Windows 4F-W | Matriz PASS com decisão CONDITIONAL | Pruning ganha TTFT mas perde um fato: não é default |
| Neuroarchitecture V2 | Documentos/contratos de componentes | Planejada; não implementada |
| Testes do núcleo | 49 testes Linux de backend, storage, router, cache, hybrid, progressive | PASS na execução 38032997094, sem modelo GGUF |

## Destaques quantitativos (históricos, não novas medições)

- WCRE-1B: mediana de latência do Core em subprocesso 1447,35 ms; persistente 344,50 ms, com Working Set persistente ~1,206 GiB. Não representa RAM do sistema todo nem RAM do chat atual.
- 4F-W: prompt V0 mediano de 1917 tokens, pruning-only 1040. TTFT mediana de 11.430,85 ms para 5.351,63 ms; ganho condicionado por queda de Context Fact Recall de 92,86% a 85,71%. Não ativar pruning por padrão.
- 4F-W: correctness do V0 neste conjunto foi 28,57%; qualidade factual limitada é um gargalo maior do que apenas o visual do HUD.
- Meta TARGET_8GB / Debian físico continua pendente. Não divulgar meta de RAM como resultado alcançado.

## Ajustes aplicados nesta auditoria

- Economia libera o índice SSD entre perguntas e evita retenção de estruturas grandes na sessão; há custo potencial de reabertura e latência, ainda não medido.
- Prompt conversacional limitado por bytes UTF-8, preservando pergunta atual e turnos de histórico completos. Isso não é contagem exata de tokens.
- Métrica TTFT passa do Core ao painel de diagnóstico quando fornecida.
- Adicionada regressão automatizada do núcleo sem dependência de modelo: 49 testes aprovados no Linux.
- Launcher .NET, BAT e run_chat.py iniciam com perfil Economia; Rápido exige escolha explícita.
- Diagnóstico rejeita GGUF manifestamente pequeno ou truncado (<64 MiB) antes de declarar pré-requisitos presentes.

## Falhas abertas, priorizadas

### P0 — bloqueios antes de marcar Windows como pronto

1. **E2E Windows com modelo real:** rodar `python tools/validate_chat_windows.py --profile economia` em Windows nativo com GGUF correto e llama.cpp, salvar resposta verdadeira, status, tempo, memória e comportamento offline.
2. **Medição de RAM comparável:** medir Working Set, Private Bytes, pico e repouso do processo Core + Python + sistema, separando RAM física de cache de arquivos e de leituras lógicas. Comparar Economia, Equilibrado, Rápido e llama.cpp puro (mesmo prompt/modelo).
3. **Qualidade do português:** conjunto fixo com saudações, memória de múltiplos turnos, perguntas factuais, questões OOD e instruções. Exigir qualidade não inferior à referência antes de reduzir mais contexto.
4. **Distribuição sem atrito:** documentação passo a passo de obtenção/verificação do GGUF e compilação do llama.cpp; depois pacote/instalador licenciado, com checagens de versão e integridade.

### P1 — depois do E2E

5. Avaliar um modelo quantizado alternativo com mais capacidade em A/B, somente se couber no orçamento de RAM/latência e melhorar a qualidade; manter Qwen0.6B como baseline.
6. Refinar o cancelamento quando ocorre antes de o stream confirmar início; testar interrupção na carga do Core persistente, timeouts, quedas de conexão e limpeza de processos.
7. Melhorar qualidade do chat: renderização Markdown segura, busca no histórico, exportação local, mensagens de erro orientadas a ações, status RAM/CPU de processo inteiro.
8. Validar retrieval corrompido/ausente e recuperação sem respostas inventadas; manter falha visível, sem esconder problemas de integridade.

### P2 — pesquisa científica, após benchmarks

9. Executar 4E física no Debian 8 GB e Low 4 GB, com cold/warm, swap/OOM, I/O físico e qualidade. Não homologar 8 GB por simulação.
10. Priorizar compressão de contexto condicionada ao quality gate antes de cache/prefetch mais sofisticado; V2 só com autorização de fase, baselines preservados.
11. Considerar modularização do repositório em 'app Windows', 'runtime', 'experimentos' e 'dados/resultados' sem quebrar resultados congelados. Não refatorar 1.700+ entradas sem testes A/B.

## Critérios de aceite para a primeira versão realmente pronta

- Um usuário consegue instalar e abrir no Windows 10/11 sem acesso a cloud e sem GPU obrigatória.
- Uma pergunta 'Olá' produz saída não simulada; dez trocas consecutivas preservam contexto e não deixam processos órfãos.
- Comandos Parar, Nova conversa, histórico e diagnóstico funcionam em sessões repetidas.
- Consumo de RAM e TTFT são registrados em hardware alvo; benchmark contra llama.cpp puro mostra se Brain-SSD de fato trouxe ganho.
- Não há falsa alegação de redução de RAM, I/O físico SSD, VRAM ou qualidade que não tenha sido medida.
- Qualidade, segurança OOD e integridade não regridem para alcançar melhora de latência.

## Referências internas

- `docs/ARCHITECTURE.md` e `docs/NEUROARCHITECTURE_V2.md` — arquitetura/limites.
- `docs/PHASE_4EW_WINDOWS_VALIDATION.md` — validação Windows.
- `docs/PHASE_4FW_CONTEXT_EFFICIENCY.md` — quality gate e pruning.
- `docs/WCRE_1B_RUNTIME_CAUSALITY_CONTEXT_COST.md` — modo persistente e custo de contexto.
- `docs/CHAT_WINDOWS.md` — operação do chat; `tools/doctor_chat.py` e `tools/validate_chat_windows.py` — diagnósticos.

**Status atual:** base de engenharia promissora, produto Windows em beta experimental; não anunciar como aplicativo acabado até o E2E real.
