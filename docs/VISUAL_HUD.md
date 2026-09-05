# Brain-SSD Visual HUD / Cognitive Observability

## Status e fronteira de segurança

O Visual HUD é uma camada local, read-only e desconectável sobre o Brain-SSD. Ele traduz eventos estruturados para um estado visual e uma narrativa determinística em português. Não altera Router, Gate, Storage Brain, Semantic Rescue, cache, pressão, Context Builder, Core ou critérios de qualidade.

O pipeline continua funcionando sem navegador e sem servidor HUD. A publicação usa uma fila limitada em memória; nunca aguarda o browser. Um consumidor lento pode perder eventos antigos, mas recupera o estado consolidado por `/api/state`. O contador `dropped_events` torna essa situação visível.

## Execução local

Requisitos: Python 3.11 ou superior. Não há dependências web ou Python adicionais.

### Executável principal no Windows

Abra `dist/windows/BrainSSD-HUD.exe`. O menu permite iniciar Demo, Replay da Fase 4D, modo live ou abrir a pasta do projeto para edição. O executável é apenas um launcher: Python, HTML, CSS e JavaScript continuam fora dele e qualquer alteração no código aparece na próxima execução.

Para reconstruir o launcher depois de editar seu código C# (requer .NET 8):

```powershell
powershell -ExecutionPolicy Bypass -File tools/build_windows_launcher.ps1
```

```bash
cd Brain-SSD
python tools/run_hud.py --demo
```

Abra `http://127.0.0.1:8765`. O modo demo usa dados sintéticos e mostra o selo `DEMO DATA` durante toda a execução.

Replay dos resultados canônicos da Fase 4D:

```bash
python tools/replay_hud.py results/phase4d/end-to-end.json
```

Para selecionar outra consulta presente em `results/phase4d/end-to-end.json`:

```bash
python tools/replay_hud.py --query-id real-q02
```

Replay por caminho explícito:

```bash
python tools/run_hud.py --result results/phase4d/end-to-end.json
```

No Codespaces, use a porta encaminhada 8765. Em Debian/Ubuntu o mesmo comando funciona; opcionalmente limite o bind à máquina local com `--host 127.0.0.1`.

## Privacidade

As opções abaixo removem conteúdo textual das respostas HTTP e do snapshot exportado:

```bash
python tools/replay_hud.py --hide-query --hide-records --hide-answer
```

- `--hide-query`: oculta a pergunta.
- `--hide-records`: mantém metadados, mas oculta os trechos recuperados.
- `--hide-answer`: oculta a resposta final.
- `--snapshot-output caminho.json`: grava o estado final de forma atômica.

Essas opções protegem a apresentação e a exportação. Elas não apagam os dados dos arquivos canônicos de origem.

## Modos da interface

O modo **Simples** é o padrão e explica o fluxo para uma pessoa não técnica: pergunta, pipeline, fração do cérebro acordada, contexto, Core, resposta, gargalo e trabalho evitado.

O modo **Técnico** acrescenta page IDs, scores, proveniência, PSS, faults, bytes lógicos e físicos, cache state, tokens de entrada/saída e caminhos dos artefatos de prova. A animação pode ser desligada e `prefers-reduced-motion` é respeitado.

## Contrato de eventos

`BrainEvent` é o envelope versionável de observabilidade. Campos principais:

| Campo | Uso |
|---|---|
| `timestamp`, `sequence` | ordenação temporal e recuperação SSE |
| `run_id`, `query_id`, `turn_id` | correlação sem dependência do navegador |
| `event_type`, `component`, `status` | estado do pipeline |
| `duration_ms` | latência observada daquela etapa |
| `metrics` | valores numéricos ou estados já medidos |
| `payload_summary` | resumo limitado e serializável, nunca objeto interno mutável |
| `demo_data` | separação explícita entre dados sintéticos e resultados reais |

Eventos desconhecidos são preservados e exibidos na timeline, permitindo evolução sem quebrar clientes antigos. Os eventos definidos incluem entrada, Reflex, Router, Semantic Rescue, Gate, páginas ativadas/inibidas, storage, records, contexto, Core, pressão, resposta, alertas e erros.

## Arquitetura

```text
pipeline ou replay
      |
      v
BrainEvent -> BrainEventBus (bounded, non-blocking)
      |                    |
      v                    v
HudStateStore          SSE /api/events
      |
      +--> /api/state, /api/history, /api/export
                                |
                                v
                      HTML + CSS + JavaScript
```

Componentes:

- `src/brain_ssd/observability/events.py`: schema e serialização segura.
- `src/brain_ssd/observability/bus.py`: stream limitado e fail-open.
- `src/brain_ssd/observability/narrator.py`: tradução determinística, sem LLM.
- `src/brain_ssd/observability/replay.py`: adaptador somente leitura dos JSONs da Fase 4D.
- `src/brain_ssd/hud/state.py`: projeção derivada para a interface.
- `src/brain_ssd/hud/server.py`: servidor HTTP/SSE local, GET-only.
- `hud/`: frontend sem build e sem CDN.

O MVP deliberadamente não injeta chamadas nos módulos cognitivos congelados. O contrato `HudRuntime.emit(event)` é o ponto de integração futura; por enquanto, a demo e o replay exercitam o fluxo completo sem mudar os resultados experimentais.

## Replay da Fase 4D

O adaptador combina apenas campos existentes em:

- `results/phase4d/end-to-end.json`
- `results/phase4d/retrieval-only.json`
- `brain_data/real_knowledge/semantic/manifest.json`

Ele não inventa scores ausentes, temperatura, pressure state ou residência não registrada. Valores indisponíveis permanecem `null`, `UNKNOWN` ou recebem uma explicação explícita. A resposta final é copiada do run canônico selecionado. O painel de fases confirma a existência do artefato citado; isso prova presença do arquivo, não reexecuta o experimento.

## Métricas e overhead

Execute o microbenchmark isolado:

```bash
python tools/benchmark_hud.py --iterations 250
```

O resultado vai para `results/hud/overhead.json`. Ele compara um loop sintético com observabilidade desligada e ligada, medindo tempo de parede, CPU Python, pico `tracemalloc` e custo médio/p95 por evento. Ele não executa Qwen e, portanto, não afirma deltas reais de TTFT, geração ou Router. Esses campos ficam nulos com a razão registrada; medi-los exigiria uma campanha OFF/ON separada e controlada.

## Testes

```bash
python -m unittest discover -s tests -p "test_hud_observability.py" -v
```

A suíte cobre serialização, eventos desconhecidos, ordenação, overflow da fila, isolamento da demo, projeção de métricas, privacidade, snapshot, replay canônico e start/stop do servidor.

## Limitações conhecidas

- O MVP não conecta eventos dentro do pipeline cognitivo congelado; live mode aguarda um produtor futuro.
- O replay representa uma execução registrada, não uma nova inferência.
- A Fase 4D não registrou todos os sinais desejados pelo HUD; ausências são mostradas sem preenchimento artificial.
- SSE é local e não oferece autenticação; não exponha a porta em rede não confiável.
- O histórico é volátil e limitado ao processo atual.
- O microbenchmark mede o custo da camada Python isolada, não o overhead end-to-end do modelo.
