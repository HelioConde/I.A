## Evolução J.A.R.V.I.S. — funções adicionadas após a bateria de 75 perguntas

Os relatórios anteriores apresentaram **18 GAPs** relacionados a
aplicativos instalados e processos ativos. A branch recebeu implementações
locais para consulta do registro Uninstall (HKCU/HKLM, visualizações
32 e 64 bits), leitura de processos por nome/PID e filtro por nome.
Essas ferramentas são **opt-in** e as respostas agora diferenciam registros
confirmados de informações ausentes.

Adicionalmente há propostas de abertura do Bloco de Notas e Calculadora
por comandos em linguagem natural, com token aleatório, confirmação
humana no frontend, validade de 90 segundos e proteção de uso único.
**O Qwen nunca executa o programa durante a geração de resposta.**
Foi adicionado modo opcional de leitura automática de respostas
com voz portuguesa marcada como `localService` pelo navegador,
sem ativar microfone.

A regressão automatizada das permissões, da rota do chat e da confirmação
foi incorporada em `tests/test_jarvis_apps.py`. O teste real de
inventário roda no Windows CI e não publica os nomes encontrados.

**Limites do novo estado:** a bateria das 75 perguntas não foi repetida
na sessão física do usuário após instalar essas alterações.
Não se deve converter automaticamente os 18 GAPs anteriores em PASS
antes dessa nova execução. Abertura efetiva de janelas no desktop,
reconhecimento de voz e OCR ainda não foram verificados/implementados.

Arquitetura e fases seguintes: `docs/JARVIS_ROADMAP_WINDOWS.md`.

# Relatório de testes — Brain-SSD Copilot Windows

## Atualização V2 — 2026-10-11

Branch auditada: `feat/copilot-local-windows` (base `f53f722`; correção desta
atualização pendente de reinício do servidor já aberto). Ambiente real:
Windows 11, AMD64, 12 threads lógicas, 15,8 GiB de RAM, Python 3.14 e
`Qwen3-0.6B-Q8_0.gguf` em CPU, perfil `economia`.

Uma bateria sequencial de 20 perguntas reais foi enviada pelo transporte SSE,
sem pesquisa externa e com uma conversa isolada por pergunta. Dezoito respostas
foram concluídas (90%). As duas falhas ocorreram depois de o Qwen finalizar com
sucesso: a classificação de resposta possivelmente truncada emitia o evento
seguro `inference.truncated`, que não constava na lista permitida do logger e
lançava `ValueError`. A lista agora aceita o evento, com teste de regressão.
Não houve evidência de queda do `llama.cpp`, timeout ou pressão de memória:
as duas execuções tinham código de retorno zero e picos aproximados de 958–964
MB de working set e 676–677 MB de memória privada.

| Área V2 | Resultado | Evidência |
| --- | --- | --- |
| Suíte completa após correção | APROVADO | 334 testes, 7 ignorados conscientemente |
| Regressão da falha Qwen | APROVADO | `inference.truncated` é evento seguro e não interrompe a resposta |
| Inferência real Windows | APROVADO | `validate_chat_windows --profile economia`: 2,932 s; TTFT 2,317 s; 26,92 tokens/s; pico 955 MB |
| 20 perguntas reais SSE | APROVADO APÓS CORREÇÃO | 18/20 chegaram ao fim na bateria original; as duas perguntas que falharam foram repetidas no servidor atualizado e ambas retornaram resposta, sem `LOCAL_CHAT_ERROR` |
| Computador do usuário | APROVADO | rota local retornou dados atuais de Windows, arquitetura, CPU, RAM e discos autorizados; não foi resposta inventada pelo Qwen |
| Copilot | APROVADO | Qwen respondeu sobre o recurso; o status confirmou Copilot, arquivos e captura autorizados |
| Monitores 1 e 2 | APROVADO/PARCIAL | capturas efêmeras foram solicitadas e a API Windows listou janelas visíveis; não foi feita leitura de pixels |
| Erro Godot no monitor 2 | LIMITAÇÃO CONFIRMADA | o fluxo informa que não pode ler texto/erro nem inferir arquivo sem OCR/visão; não alucinou diagnóstico |
| Arquivos de teste autorizados | APROVADO | leitura/listagem de fixture `.gd` e nome com acento; traversal para `win.ini` bloqueado com HTTP 400 |
| Sem permissão | APROVADO | testes cobrem Copilot desativado, captura sem permissão e rota que não afirma acesso não concedido |
| Segurança HTTP | APROVADO | origem atacante recebe HTTP 403; servidor restrito a loopback e valida Host/Origin |
| Pesquisa externa | NÃO EXECUTADA | sem autorização por pergunta nem credenciais; testes mantêm fontes e instruções externas sob controle |
| Interface visual | APROVADO/PARCIAL | `uv` e BrowserAct instalados com autorização; navegador isolado renderizou chat e painel Copilot, validou controles e `POST /api/copilot` de captura com HTTP 200 |

### Notas V2

- Perguntas de tela foram tratadas por ferramentas locais; títulos de janelas e
  capturas não foram enviados ao Qwen para interpretação.
- Capturas não foram persistidas como artefatos deste relatório. A capacidade
  atual é prévia local; `vision_enabled` permanece `false`.
- Não foram lidos documentos pessoais fora de uma pasta de fixtures nem feitas
  alterações em histórico, memórias ou dados do usuário.
- A interface exibiu corretamente os avisos de privacidade, o escopo da pasta
  autorizada, a exigência de clique para capturar e o aviso de que o Qwen não
  interpreta pixels. A captura sob demanda respondeu HTTP 200 e exibiu
  “Captura local pronta”; a imagem não foi exibida nem registrada no relatório.

| Dimensão | Nota V2 |
| --- | ---: |
| Inferência e estabilidade | 8,0/10 |
| Ferramentas locais/Copilot | 8,5/10 |
| Arquivos e segurança | 9,0/10 |
| Captura de tela | 5,0/10 |
| Visão/OCR | 0,0/10 |
| Pesquisa web | 7,0/10 |
| Interface visual | 7,5/10 |
| Desempenho CPU | 7,0/10 |

Para tornar o resultado 20/20 verificável na API real, reinicie o servidor
local após esta atualização e repita a bateria SSE; a correção não pode ser
injetada no processo Python que já estava aberto durante a auditoria.

Data da auditoria: 2026-10-11  
Branch: `feat/copilot-local-windows` (`8b4746c` antes das correções desta auditoria)  
Ambiente: Windows 11, AMD64, 12 threads lógicas, 15,8 GiB de RAM, Python 3.14.  
Runtime real validado: `Qwen3-0.6B-Q8_0.gguf`, perfil `economia`, CPU-only.

## Resumo executivo

O Copilot local inicia e atende pelo servidor restrito a `127.0.0.1`. A leitura de arquivos foi comprovada com uma pasta já autorizada, utilizando apenas fixtures fictícias. O Qwen respondeu uma pergunta real via API HTTP; não foi usado mock para essa evidência.

A auditoria identificou e corrigiu três problemas: conexões SQLite temporárias não eram fechadas no Windows, uma raiz explicitamente autorizada abaixo de `AppData`/`Temp` era indevidamente bloqueada pelo filtro de arquivos protegidos e módulos de residência POSIX impediam a descoberta da suíte no Windows. A regressão final passou com 324 testes e 7 ignorados por recursos exclusivamente POSIX ou por criação de symlink bloqueada pelo próprio Windows.

O projeto ainda não está pronto para afirmar capacidade de interpretação visual: captura de tela é somente prévia de imagem, e o Qwen textual não recebe pixels. Também não foram realizadas pesquisas reais nesta auditoria, pois não houve consentimento por consulta nem chave Serper/Brave fornecida.

## Testes e evidências

| Área | Teste executado | Resultado | Evidência |
| --- | --- | --- | --- |
| Baseline | `unittest discover -s tests` | APROVADO | 324 testes aprovados; 7 ignorados conscientemente |
| Dependências | `mss`, `Pillow` | APROVADO | já instaladas em Python 3.14 |
| Runtime | `doctor_chat --profile economia --probe` | APROVADO | GGUF e runtime CPU encontrados |
| Inferência real | `validate_chat_windows --profile economia` | APROVADO | 3,472 s; TTFT 2,614 s; 17,62 tokens/s; RSS pico 955 MB |
| Chat real do Copilot | API `/api/chat` | APROVADO | Qwen3 0.6B respondeu sobre API REST; 5,905 s; TTFT 2,829 s; 21,83 tokens/s |
| Arquivo autorizado | API `/api/copilot`, ação `read` | APROVADO | leu `work/copilot-fixtures/erro_exemplo.gd`, 70 bytes |
| Caminho com acento | API `/api/copilot`, ação `list` | APROVADO | listou `nota com acento.md` na raiz de fixture |
| Traversal/fora da raiz | tentativa `C:\Windows\..\Windows\win.ini` | APROVADO | bloqueado com HTTP 400; conteúdo não retornado |
| Origem HTTP | regressão `TestCopilotHttp` | APROVADO | origem atacante recebe HTTP 403 |
| Sistema | API `/api/copilot`, ação `system` | APROVADO | Windows 11, AMD64, 12 threads, 15,8 GiB retornados |
| Captura | status do Copilot | PARCIAL | habilitada, intervalo de 2 s; nenhuma captura pessoal foi feita |
| Visão | inspeção de status e código | INDISPONÍVEL | `vision_enabled: false`; Qwen atual é textual |
| Pesquisa web | testes automatizados de provedores | APROVADO/PARCIAL | consentimento por mensagem, SSRF e ausência de chave cobertos; sem consulta externa real |
| Memória episódica/histórico | regressões SQLite | APROVADO | persistência, correção, exclusão e conflito cobertos por testes |
| Três modelos/perfis | execução física completa | BLOQUEADO | apenas o 0.6B foi executado nesta auditoria; 1.7B/4B e perfis rápido/equilibrado não foram repetidos |

## Correções aplicadas

1. `LearnedResponses` e `WebKnowledge` agora fecham a conexão SQLite após commit/rollback. Em Python no Windows, `with sqlite3.Connection` confirma transação, mas não fecha o handle; isso bloqueava a limpeza de bancos temporários e poderia reter locks entre sessões.
2. O Copilot valida nomes protegidos somente dentro da subárvore explicitamente autorizada. Uma pasta autorizada em `AppData\Local\Temp` agora funciona, sem permitir `.env`, chaves, symlinks externos ou saída da raiz.
3. Módulos de residência/replicação física agora importam no Windows. Medição `mincore`/`madvise` e contadores `resource` permanecem explicitamente POSIX; os testes correspondentes são ignorados no Windows, não simulados.

## Segurança e limitações

- O servidor aceita apenas `127.0.0.1` e valida `Host`/`Origin` nas mutações.
- O Copilot não escreve arquivos, não executa comandos vindos de arquivos e bloqueia extensões/diretórios sensíveis, binários, arquivos grandes, `..` resolvido fora da raiz e links simbólicos que escapem dela.
- Pesquisa é opt-in por pergunta; as regressões verificam que fontes não confiáveis não viram instruções e que chaves permanecem fora de resultados.
- Capturas não foram testadas contra monitores físicos, jogos, navegador ou Godot para evitar registrar tela pessoal. Essa validação ainda requer uma sessão de teste com conteúdo sintético.
- Não existe modelo multimodal. Para compreensão visual será necessário integrar um modelo visão-linguagem compatível com CPU/llama.cpp (ou um runtime separado), definir orçamento de RAM e criar testes com imagens sintéticas antes de alegar interpretação.

## Avaliação

| Área | Nota |
| --- | ---: |
| Chat e inferência | 7,5/10 |
| Memória SSD | 8,0/10 |
| Arquivos Windows | 8,5/10 |
| Captura de tela | 4,0/10 |
| Visão computacional | 0,0/10 |
| Pesquisa na internet | 7,0/10 |
| Interface | 6,0/10 |
| Desempenho | 6,5/10 |
| Segurança | 8,5/10 |
| Estabilidade | 7,5/10 |

As notas abaixo de 9,5 refletem ausência de testes físicos de múltiplos monitores, falta de visão multimodal, ausência de automação Playwright disponível e cobertura física incompleta dos três GGUF/perfis. Elas não foram elevadas com base apenas em testes unitários.

## Próximos passos recomendados

1. Executar em uma conta/sessão de teste com dois monitores e tela sintética: monitor 0/1/2, atualização periódica, desconexão e cancelamento de captura.
2. Instalar/configurar Playwright e registrar screenshots sintéticas nas quatro resoluções exigidas.
3. Repetir inferência real para Qwen 1.7B e 4B nos perfis economia/equilibrado/rápido, medindo TTFT, tokens/s, CPU e RAM.
4. Para web real, obter autorização explícita por consulta e configurar credenciais de Serper/Brave apenas se desejado; nunca registrar a chave.
5. Projetar visão multimodal como recurso novo e medi-lo separadamente de captura, mantendo capturas locais e efêmeras.
