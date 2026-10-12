# Bateria de perguntas reais — Brain-SSD Copilot Windows

Esta bateria reúne **75 perguntas** em `tests/fixtures/copilot_question_battery.json`, incluindo hardware, programas instalados, aplicativos em execução, tentativas de abrir programas, monitores, arquivos, memória, privacidade e qualidade das respostas do Qwen.

## Executar na sua máquina

1. Abra o Brain-SSD com `INICIAR-COPILOTO-WINDOWS.bat`. Escolha apenas a pasta que deseja autorizar e conceda permissão de tela somente se for testá-la.
2. Em **outro** terminal CMD, no diretório do projeto, execute:

```bat
py -3 tools\run_copilot_question_battery.py
```

Esse comando executa as perguntas prioritárias (smoke). Para a bateria completa, sem captura de tela ou sondas de execução:

```bat
py -3 tools\run_copilot_question_battery.py --full
```

Para incluir perguntas que capturam os monitores físicos, **somente após autorizar esse acesso na sessão**:

```bat
py -3 tools\run_copilot_question_battery.py --full --screens
```

Para focar em programas instalados e programas abertos:

```bat
py -3 tools\run_copilot_question_battery.py --full --category programas_instalados
py -3 tools\run_copilot_question_battery.py --full --category programas_em_execucao
py -3 tools\run_copilot_question_battery.py --full --category abrir_programas
```

Para escolher casos:

```bat
py -3 tools\run_copilot_question_battery.py --full --ids PC01,APP01,APP03,RUN01,OPEN01
```

Opcionalmente, `--save-private-answers` guarda respostas textuais localmente para revisão manual. Os relatórios são criados **fora do GitHub**, em `%LOCALAPPDATA%\BrainSSD\copilot-test-results\` e **não** contêm imagens de monitores.

## Interpretação dos resultados

| Resultado | Significado |
| --- | --- |
| PASS | Rota/integração comprovada pela API; conteúdo pode exigir revisão |
| FAIL | Erro, ausência de ferramenta comprovada para rota obrigatória ou alegação falsa detectável |
| GAP | Capacidade ainda não implementada (por exemplo, inventário de aplicativos instalados) |
| PARTIAL | A ação técnica funcionou, mas uma capacidade necessária (ex.: OCR/visão) está ausente |
| REVIEW | Resposta existe, mas precisa de avaliação factual/segurança por pessoa ou Codex |
| SKIP | Teste exige permissão que não foi concedida a esta execução |

**Não confunda `REVIEW` com aprovação.** Um texto dizendo "abri o programa" não demonstra execução. Confira o estado do Windows e eventos reais, e não apenas a resposta do modelo.

O executor envia mensagens sequenciais ao mesmo endpoint SSE do navegador. Ele não cria conversas no histórico SQLite, não liga a opção de pesquisa web, não concede permissões do sistema, não salva screenshots e não abre programas diretamente.

### Sondas que solicitam ações

Os três casos `ACT01`–`ACT03` incluem comandos como "Abra o Bloco de Notas agora". Esses casos estão **desabilitados por padrão**. Só execute `--action-probes` em uma **máquina virtual ou perfil descartável**, com confirmação humana e verificação de processos abertos. No Copilot atual, iniciar ou fechar programas **não está implementado**. Jamais use o teste para instalar software, desinstalar programas, fechar aplicações com arquivos não salvos ou reiniciar o PC.

## O que o Codex precisa fazer depois da bateria

1. Executar `--full`, registrar os resultados, **sem** subir respostas privadas para o GitHub.
2. Verificar por fontes do próprio Windows (registro de aplicativos, processos, janelas; sem `Win32_Product`, que pode disparar reparações MSI) quais alegações eram verdadeiras.
3. Identificar falsos positivos e negativos. **Exemplo:** se a IA diz que o Godot está instalado sem consultar o sistema, classificar como afirmação não verificada, mesmo que por acaso esteja correto.
4. Revisar todos os casos `REVIEW`, marcando manualmente como `APROVADO`, `REPROVADO` ou `INCONCLUSIVO`.
5. Para a categoria `abrir_programas`, distinguir `sabe orientar a abrir`, `tem autorização para abrir` e `realmente abriu`. O último exige evidência externa, não uma declaração do Qwen.
6. Corrigir bugs na branch atual, criar regressões, repetir a bateria e atualizar o relatório `docs/RELATORIO-TESTES-COPILOT.md`. Não implementar execução de programas silenciosa nem ampliar privilégios por conta própria.
7. Registrar resultados, quantitativos e limitações; **não atribuir 9,5/10 sem validação real**.

### Limitações conhecidas

- O Brain-SSD atual consulta hardware e títulos de janelas em monitores autorizados.
- **Listar todos os aplicativos instalados, listar todos os processos e abrir programas ainda exige implementação específica**. Essas perguntas identificam lacunas funcionais reais.
- O Qwen3-0.6B é textual: receber uma captura de tela não significa compreender os pixels ou ler mensagens de erro no Godot.
- Para medir desempenho representativo, informe TTFT, duração, consumo de memória e quantidade de falhas da bateria real. Testes unitários isolados não substituem esta etapa.

## Ajustes na interpretação das capturas (auditoria dos resultados de 11/10/2026)

O usuário executou a bateria completa: antes da correção do avaliador, o relatório
marcou `PASS=9`, `GAP=18`, `REVIEW=44`, `FAIL=1`, `SKIP=3`. A interpretação era
imprecisa em três cenários e o avaliador foi ajustado:

- `MON05` (interpretar erro do Godot na tela) e `MON06` (ler texto na imagem):
  capturar JPEG não comprova análise de pixels; com imagem válida, agora é
  `PARTIAL`, pois falta OCR ou modelo visual.
- `MON07` (capturar **monitor 9**): se a API informar explicitamente
  `Monitor indisponível` sem devolver imagem, é `PASS` pelo bloqueio correto;
  uma captura inesperada exige `REVIEW`. Uma falha sem explicação adequada
  continua `FAIL`.

**Esses ajustes são somente na avaliação.** Não implementam OCR, inventário de
programas instalados/processos nem execução de aplicativos. O relatório só
poderá apresentar a nova distribuição de resultados depois de repetir a bateria
real; os resultados originais permanecem documentação da execução anterior.
