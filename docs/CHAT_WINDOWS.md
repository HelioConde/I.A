# Brain-SSD Chat — primeiro objetivo no Windows

## Objetivo

Chat visual em português: caixa de mensagem, Enter para enviar, Shift+Enter
para quebrar linha, indicador de processamento, histórico da sessão,
nova conversa e painel de métricas experimentais.

**As respostas vêm do Qwen3-0.6B local em CPU**, não de respostas falsas ou
de uma API externa. Perguntas não triviais consultam a base de conhecimento
armazenada em SSD usando a recuperação já existente.

A interface de conversa é **experimental** e preserva os benchmarks
congelados das Fases 1–4D, sem reivindicar a validação física 4E.

## Iniciar no Windows

Requisitos: Windows 10/11 x64; Python 3.11+; o projeto completo; runtime
llama.cpp CPU-only e modelo Qwen3-0.6B-Q8_0.gguf locais. O corpus/índice
Brain-SSD é opcional para conversar, mas necessário para retrieval SSD.

1. Dê dois cliques em **INICIAR-CHAT-WINDOWS.bat**, na raiz do projeto.
2. O terminal inicia o servidor em loopback e abre o navegador.
3. Acesse **http://127.0.0.1:8766**. Quando aparecer "Modelo encontrado",
   digite "Olá" e pressione Enter. A resposta virá da IA local.
4. Mantenha o terminal aberto. Ctrl+C encerra a aplicação.

PowerShell: python tools/run_chat.py

Sem abrir automaticamente o navegador: python tools/run_chat.py --no-open-browser

Se faltarem o GGUF, executável llama-completion ou corpus/índice, prepare
o runtime seguindo [WINDOWS_NATIVE_RUNTIME.md](WINDOWS_NATIVE_RUNTIME.md),
incluindo python tools/setup_windows_runtime.py. Nem todos os binários
e dados locais são distribuídos neste repositório.

O código do launcher .NET inclui a opção Chat. Para reconstruir
**dist/windows/BrainSSD.exe** com a nova opção é necessário .NET 8 e executar:
powershell -ExecutionPolicy Bypass -File tools/build_windows_launcher.ps1

**O executável já versionado não é automaticamente atualizado** por mudanças
em Program.cs. Até recompilar, use o arquivo .bat.

## Privacidade e limites

- Frontend e API: apenas 127.0.0.1:8766; POST exige Origin local. Não
  exponha a porta por túnel ou encaminhamento.
- Histórico SQLite local persistente, salvo fora do GitHub. O servidor inclui
  até 8 mensagens recentes no prompt. Nenhuma conversa vai para a nuvem.
- O Core executa CPU-only com --device none. RAM e velocidade reais
  dependem da máquina e da pergunta. GPU dedicada não é necessária.
- O modo subprocesso recarrega o modelo por pergunta (mais lento).
  --core-mode persistent é experimental e depende de llama-server local.
- Medidas de working set não comprovam leitura física do SSD.
- Se o runtime estiver ausente, a tela informa a falha; não simula respostas.
- O chat tem streaming incremental e botão Parar. Ainda não possui
  instalador autônomo, nem medição validada de desempenho em hardware alvo.

## Arquivos e teste

- tools/run_chat.py: inicialização Windows.
- src/brain_ssd/chat/server.py: API e adaptação do Core / SSD.
- chat/: HTML, CSS e JavaScript offline.
- tests/test_chat_windows.py: testes sem GPU ou modelo.

Execute: python -m unittest discover -s tests -p "test_chat_windows.py" -v

## Próximo marco

Validar no Windows real uma conversa com "Olá", aferir tempo, RAM e qualidade,
e comparar o modo persistente com o modo de processo por consulta.

## Melhorias do chat Windows (10/10/2026)

O chat simples não exige mais os arquivos opcionais do cérebro SSD para
responder a uma saudação. Exige o modelo GGUF local e um binário de inferência
CPU-only. Para recuperação seletiva de conhecimento, manifesto, índice e
brain.dat precisam estar presentes. Caso contrário, o Core ainda conversa
sem inventar fontes SSD.

Perfis disponíveis:

- Economia: 2 threads, janela de 2048, Core descarregado entre perguntas.
- Equilibrado: 4 threads, janela de 4096, Core descarregado entre perguntas.
- Rápido: 4 threads, janela de 4096, Core persistente na RAM; requer llama-server.exe.

O arquivo INICIAR-CHAT-WINDOWS.bat escolhe Economia por padrão.
Para trocar: python tools/run_chat.py --profile equilibrado
ou python tools/run_chat.py --profile rapido.
Esses nomes não prometem quantidades fixas de RAM: faça medições reais.

Validação de verdade em Windows (não simulada):

    python tools/validate_chat_windows.py --profile economia

O relatório local é salvo em results/chat_validation/latest-local-windows.json.
A mensagem inicial de modelo encontrado significa apenas preflight de arquivos;
a confirmação de inferência aparece depois da primeira resposta verdadeira.
A Action de Windows executa testes simulados e compila o launcher .NET,
mas não contém Qwen/llama.cpp; ela não substitui o teste real.
O instalador autônomo permanece pendente.


## Histórico persistente e conversas locais

As mensagens completas são armazenadas exclusivamente neste computador usando
SQLite (biblioteca padrão do Python). No Windows, o banco padrão é
%LOCALAPPDATA%\BrainSSD\chat-history.sqlite3.
O histórico permanece após fechar a janela, é exibido na barra lateral,
pode ser reaberto ou excluído pelo usuário e nunca é enviado à nuvem.
O backend monta o contexto a partir das mensagens salvas, e não de texto
arbitrário enviado pelo navegador. Apenas as 8 mensagens recentes são usadas
para montar o prompt; isso evita crescimento descontrolado de contexto.
Se desejar outro local, inicie com --history-db "C:\meus-dados\brain.sqlite3".
A exclusão remove a conversa do banco, mas não garante eliminação forense
dos blocos físicos no SSD. Não sincronize nem versiona este arquivo por engano.

O streaming de tokens está implementado na interface. Ainda não existe instalador independente.


## Diagnóstico de instalação em um clique

Abra DIAGNOSTICAR-CHAT-WINDOWS.bat na raiz do projeto para verificar Python,
arquivo GGUF, runtime de inferência e corpus SSD opcional. A verificação é
rápida e não carrega o modelo inteiro. O código Python também aceita
python tools/doctor_chat.py --profile economia --json e --probe.

Se os arquivos necessários estiverem presentes, execute o teste de resposta
real: python tools/validate_chat_windows.py --profile economia.
O teste de instalação não substitui uma inferência verdadeira.


## Streaming de tokens e Parar (10/10/2026)

O chat usa POST /api/chat/stream com Server-Sent Events (SSE). A interface
mostra os pedaços da resposta à medida que o Core os envia e oferece **Parar**.
O perfil Economia e Equilibrado usam stdout incremental do llama-completion,
sem manter o modelo carregado entre consultas. O perfil Rápido encaminha
os eventos do llama-server persistente. Nos dois casos a resposta é produzida
pelo modelo local, não por animação de texto fictícia.

Parar solicita cancelamento ao backend: o subprocesso é encerrado; no perfil
persistente, interromper mata o processo llama-server para evitar inferência
em segundo plano (o próximo prompt o reinicia). Uma resposta interrompida não
é salva no SQLite. Se a CLI acumular stdout antes de escrever, os tokens podem
chegar em blocos maiores; essa granularidade depende do binário.

O streaming não afirma maior velocidade nem menos RAM. Os testes automatizados
usam um Core simulado apenas para verificar transporte, cancelamento e
persistência; a validação real ainda exige Windows + Qwen GGUF + llama.cpp.


### Validação de cancelamento de processos

A suíte test_chat_stream.py agora inicia um processo Python local como
substituto de um binário de inferência. Ela comprova que a leitura da saída
do sistema operacional funciona progressivamente e que um processo que
ficaria em execução é interrompido ao cancelar. Esse teste de I/O não
substitui uma medição Windows de Qwen, latência ou economia de RAM.


## Revisão de memória e contexto — 10/10/2026

O perfil Economia passa a abrir o índice SSD somente durante a recuperação de
conhecimento de cada pergunta e a fechá-lo em seguida; Equilibrado e Rápido
retêm a estrutura de retrieval durante a sessão. Isso prioriza RAM em repouso
em troca de mais trabalho de leitura/CPU por pergunta. O tamanho do ganho
deve ser medido em máquinas físicas.

Há um limite conservador no tamanho UTF-8 do prompt completo:
Economia = 3.600 bytes; Equilibrado/Rápido = 7.600 bytes. O chat prioriza a
pergunta atual, depois turnos recentes inteiros e evidências completas.
O limite é apenas uma aproximação segura de orçamento: **bytes não são tokens**
e cada runtime GGUF precisa de validação real para context overflow/qualidade.
O limite de saída atual permanece 180 tokens por resposta. Os resultados
do Core congelado e o experimento 4F-W não foram alterados.

O diagnóstico recebe agora também o tempo até o primeiro token (TTFT),
quando medido. Não confundir TTFT com latência total.

## Auditoria de inicialização (10/10/2026)

O launcher .NET, o BAT e run_chat.py iniciam no perfil Economia por
padrão. O perfil Rápido continua opt-in. O diagnóstico rejeita arquivos
GGUF com cabeçalho válido e menos de 64 MiB (limiar conservador para
detectar arquivos truncados, não validação do modelo inteiro).
Os resultados canônicos anteriores do Core permanecem inalterados.

## Memória episódica experimental (opt-in)

O chat possui um **módulo separado de notas episódicas** inspirado funcionalmente
na distinção hipocampo/neocórtex. Não é modelo neuronal nem treinamento do Qwen.
Para ativar, execute `python tools/run_chat.py --episodic-memory --profile economia`
ou abra `INICIAR-CHAT-MEMORIA-WINDOWS.bat` (opt-in explícito).
Por padrão a função continua desativada: o Brain-SSD NÃO grava fatos em memória
de longo prazo automaticamente. A pessoa precisa escolher Guardar uma lembrança
no painel lateral e digitar a nota; limite de 500 caracteres por nota.

As notas são salvas separadamente em
`%LOCALAPPDATA%\BrainSSD\episodic-notes.sqlite3` no Windows.
São usadas como **dados não confiáveis** no prompt, nunca como comandos.
A busca usa pistas lexicais, até 3 memórias retornadas por pergunta e abstém
quando não há evidências suficientes. Não tenta adivinhar lembranças ausentes.
Apagar pelo botão X remove logicamente uma nota do SQLite; backup, snapshots
ou blocos físicos podem continuar existindo no SSD.

Há apenas um plano de replay offline de leitura, não 'sono', consolidação real
ou atualização automática de redes neurais.
Veja `docs/NEUROCIENCIA_AUDITORIA_2026-10-10.md`.
