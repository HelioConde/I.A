# Brain-SSD — Logs para diagnóstico e comparação de testes

**Status:** módulo local de observabilidade (2026-10-10). Os logs
ajudam a comparar falhas e uso de recursos; **não** fornecem por si só
comprovação de qualidade do Qwen, ganhos reais de RAM ou aprendizado cerebral.

## Como coletar e enviar para análise

### 1. Executar os testes em Windows

Dê dois cliques em **GERAR-LOGS-WINDOWS.bat**. O teste roda localmente e mostra
ao final o caminho do ZIP em:

`%LOCALAPPDATA%\BrainSSD\exports\brain-ssd-latest-diagnostics.zip`

Anexe **esse ZIP** na conversa para que eu possa examinar o resumo, os
tipos de falha, duração e eventos por sessão. Não existe acesso automático
ao seu computador nem envio automático para GitHub ou ChatGPT.

Pelo terminal:

```powershell
# Testes de chat e mecanismos cognitivos, sem GGUF
python tools/run_diagnostics.py

# Incluir também testes do núcleo de armazenamento/roteamento/cache
python tools/run_diagnostics.py --core

# Somente Windows configurado com Qwen real:
python tools/run_diagnostics.py --real-windows

# Reexportar os eventos do chat, sem rodar testes
python tools/export_diagnostics.py
```


O chat comum, quando executado pelo `INICIAR-CHAT-WINDOWS.bat`, já
gera logs automaticamente; os comandos acima consolidam as medições.

### 2. Executar o chat normalmente

```powershell
python tools/run_chat.py --profile economia
```


O histórico privado dos eventos é gravado em:

`%LOCALAPPDATA%\BrainSSD\diagnostics\events.jsonl`

O processo de logging não chama APIs externas; o arquivo é escrito fora do
repositório. Há rotação por tamanho: 1 MiB por arquivo e quatro cópias
antigas por padrão. O JSONL é **um evento por linha**, com schema versionado.
Em Windows, as proteções de acesso dependem das permissões do usuário; em
Linux a pasta e os arquivos são privados (0700/0600). Para não gravar
eventos: `python tools/run_chat.py --no-diagnostics`.

### Quais informações ficam nos logs

- **Sessão:** timestamp UTC, UUID aleatório, Windows/Linux, versão Python, revisão GitHub quando presente e início/fim.
- **Inicialização:** perfil Economia/Equilibrado/Rápido, tipo de backend,
  contagem de threads e categoria do erro (caso falhe).
- **Consulta:** UUID, tamanho da mensagem (caracteres), número de turnos,
  tamanho do prompt (bytes UTF-8), tempo de recuperação SSD, fontes e páginas.
- **Memória:** tempo de recall e quantidade de episódios (sem texto).
- **Inferência:** duração, TTFT, tokens/s, working set e private bytes se o
  backend conseguir medi-los; código de saída. O chat também registra RSS do processo Python e tempo de CPU do processo, separados da RAM do modelo.
- **Testes:** nome fixo da suíte, PASS/FAIL, duração e código de saída.

Campos dinâmicos inesperados são descartados **antes da escrita e durante
a exportação**. Não gravamos mensagens, respostas, histórico, textos de
memórias, nomes de arquivos, endereços de pessoas, chaves, stack traces ou
mensagens brutas de erro. Mesmo assim, inspecione o pacote antes de compartilhar.

### Onde ver os resultados automáticos do GitHub

Os workflows [Chat Smoke](https://github.com/HelioConde/I.A/actions/workflows/chat-smoke.yml)
e [Windows Chat Build](https://github.com/HelioConde/I.A/actions/workflows/windows-chat.yml)
incluem ao fim os artefatos `BrainSSD-diagnostics-Linux` e
`BrainSSD-diagnostics-Windows`, com ZIP sanitizado (retenção 14 dias).
No workflow, somente **simulações e testes sem Qwen GGUF** são executados.
Os testes reais do seu Windows não aparecem no GitHub a menos que você
os compartilhe intencionalmente.

### Sobre o pacote exportado

O ZIP contém:

| Arquivo | Conteúdo |
| --- | --- |
| `summary.json` | Sessões, contagem de eventos, falhas por classe e estatísticas |
| `events.jsonl` | Até 1000 eventos recentes após filtragem de segurança |
| `LEIA-ME.txt` | Origem e limitações do pacote |

**Importante:** os logs não incluem conteúdo textual das respostas, então
não são suficientes para avaliar a *correção* da IA. A avaliação de qualidade
precisará de exemplos autorizados separadamente.

## Próximas medições a validar no PC real

Coletar sessões antes/depois por perfil, observar memória em repouso e
sob inferência, latência mediana, TTFT, retorno de erros, cancelamento,
recall episódico e efeito no contexto. Ainda falta comparar esses registros
com **Qwen puro**, sob as mesmas perguntas e hardware, sem atribuir ganhos
de RAM ao Brain-SSD antecipadamente.

## Métricas separadas (evita resultados enganosos)

O relatório `summary.json` separa `chat_latency_ms` (tempo de ponta a ponta),
`inference_latency_ms` (geração no Core), `time_to_first_token_ms`,
`native_peak_working_set_bytes` e `python_working_set_bytes`.
A chave legada `latency` representa **apenas chamadas de chat concluídas**;
não mistura inferência e duração total como se fossem amostras independentes.
Essas contagens ainda não representam RAM física total nem bytes reais lidos
do SSD. Valores ausentes significam medição indisponível, não zero.
