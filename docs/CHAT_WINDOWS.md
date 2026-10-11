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

## Validação estática da interface

Além das suítes do chat, o CI verifica a sintaxe de `chat/app.js` com Node
e executa `test_chat_static_ui.py` para detectar IDs duplicados, referências
JavaScript a elementos HTML inexistentes, âncoras e arquivos estáticos.
Isso não substitui captura de tela, acessibilidade em navegador real ou teste
de usabilidade no Windows, mas bloqueia erros simples antes da publicação.

## Redação de erros internos

A API do chat e os eventos de streaming não incluem mensagens brutas de
exceções do `llama.cpp` ou caminhos locais. Erros inesperados retornam
mensagens genéricas; o log diagnóstico registra **apenas o tipo da falha**.
Erros de validação de notas permanecem legíveis para permitir correção do usuário.

## Erro "Não foi possível iniciar o modelo local" (diagnóstico seguro)

**O servidor HTTP abrir não significa que o modelo GGUF foi carregado.**
O chat inicia o Core em uma thread separada e o estado `error` pode
resultar de modelo GGUF ausente/corrompido, binário llama-completion
ausente ou erro de execução/dependência no Windows.

Os arquivos **INICIAR-CHAT-WINDOWS.bat** e
**INICIAR-CHAT-MEMORIA-WINDOWS.bat** agora executam o preflight com
`doctor_chat.py --profile economia --probe` **antes** de abrir o navegador;
se o preflight falhar, mostram itens ausentes e encerram sem iniciar um
chat inutilizável. O comando não carrega o Qwen completo e não mexe em
histórico/memórias.

No Windows, **prefira duplo clique em `DIAGNOSTICAR-CHAT-WINDOWS.bat`**,
localizado ao lado do atalho de memória. O BAT resolve a própria pasta do
projeto e mostra qual interpretador foi selecionado.

Se preferir PowerShell, entre **primeiro** na pasta real onde o projeto
foi baixado (não apenas em `C:Users...Documents`):

```powershell
cd "C:\CAMINHO\REAL\DO\I.A"
py -3.11 .\tools\doctor_chat.py --profile economia --probe
```

O teste deve abrir o arquivo a partir de `tools`. Um erro
`can't open file 'C:Users...Documents	oolsdoctor_chat.py'`
é apenas **diretório errado**, não prova de GGUF corrompido. Se 3.11
não estiver instalado, use o BAT ou o Python do ambiente virtual.


No caso de erro, verifique `model_gguf_valid_header`,
`model_plausible_size`, `cpu_runtime_found` e
`probe_passed`. O terminal do chat e a resposta de status
exibem códigos seguros como `MODEL_MISSING`, `MODEL_INVALID`,
`CORE_MISSING` e `RUNTIME_UNREADABLE`.

**Não baixe um GGUF do GitHub Actions:** os artefatos de CI contêm o
launcher .NET e diagnósticos simulados, não o modelo ou as dependências
nativas do llama.cpp. Se o preflight passar e a inferência falhar, envie
somente o ZIP gerado por `python tools/export_diagnostics.py`
para analisar as categorias de erro. Não compartilhe senhas ou caminhos
privados em capturas de terminal. O teste com o Qwen real continua necessário.

## Primeira execução: GGUF e llama.cpp ausentes

Se o chat iniciar em `127.0.0.1:8766` mas apresentar erro ao carregar o
modelo, rode `DIAGNOSTICAR-CHAT-WINDOWS.bat`. Faltando requisitos,
execute `PREPARAR-CHAT-WINDOWS.bat`. O download é opcional e exige
confirmação. Não remove arquivos pessoais.

Origem do modelo: Qwen/Qwen3-0.6B-GGUF, arquivo
`Qwen3-0.6B-Q8_0.gguf`, tamanho 639.446.688 bytes, SHA-256:
`9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031`.

Runtime interativo: distribuição CPU x64 oficial
`ggml-org/llama.cpp` versão `b11552`, arquivo
`llama-b11552-bin-win-cpu-x64.zip`, SHA-256:
`c00741179811ff903b515eae28bdeef1f47af6e81c49920c4e68b62954e056d6`.
Fica em `third_party/llama.cpp/runtime-win-cpu-x64/bin`, separado do
binário congelado da pesquisa (`build-win`). Não houve validação
física da geração com esse pacote no computador do usuário.

```bat
cd /d "%USERPROFILE%\Documents\I.A"
PREPARAR-CHAT-WINDOWS.bat
DIAGNOSTICAR-CHAT-WINDOWS.bat
INICIAR-CHAT-MEMORIA-WINDOWS.bat
```

O atalho já usa a pasta do projeto. Para chamar Python diretamente é
obrigatório entrar nela primeiro; caso contrário ocorre FileNotFoundError
em `tools/doctor_chat.py`. Python 3.14.7 passou no requisito de versão.

Os testes de preparação simulam downloads sem rede no CI e verificam
hashes, ZIPs maliciosos, ausência de sobrescrita e preservação de dados.

## Diagnóstico de respostas genéricas e repetidas (Qwen3 GGUF)

O chat CPU de produção aplica o template de conversa embutido no GGUF com
`--jinja --conversation --single-turn`. O prompt contém **somente um turno de
usuário** (instruções, contexto, pergunta atual e `/no_think`); o llama.cpp
adiciona os delimitadores corretos do Qwen3. O chat não acrescenta mais um
`Assistente:` falso na ponta do prompt. As configurações de amostragem do
chat usam temperatura 0,7, top-p 0,8, top-k 20 e min-p 0, mantendo o Core
congelado de benchmark separado. Respostas passadas exatamente iguais a
`Não soube.` e uma resposta genérica identificada no bug de 10/10/2026 são
excluídas **somente do contexto** de novos turnos: não se apagam do histórico.

Para conferir a qualidade em uma sessão independente, sem usar histórico ou
notas episódicas pessoais, execute no Windows, a partir da raiz do projeto:

```powershell
py -3 .\tools\validate_chat_quality_windows.py --profile economia
```

O teste efetua **três inferências reais**: capacidades, SSD/RAM e aritmética
básica. O relatório `results/chat_validation/latest-quality-windows.json`
registra somente tamanho de respostas, classificações simples e presença de
fontes SSD; nenhuma pergunta ou resposta é salva por padrão. Adicione
`--include-answers` somente se quiser guardar os textos localmente. O teste
usa critérios heurísticos e **não garante precisão, qualidade geral nem
vantagem do Brain-SSD**. A integração com o hardware real ainda deve ser
validada antes de considerar o bug encerrado.


## Comandos explícitos de memória pelo próprio chat (10/10/2026)

Com o chat iniciado com `--episodic-memory` (ou pelo iniciador COM MEMÓRIA),
algumas frases intencionais são executadas **pelo aplicativo Python e SQLite**,
sem gerar resposta do modelo:

- `salve na memória que seu nome é Luna` ou `Seu nome a partir de hoje é Luna`:
  comandos explícitos que gravam o nome escolhido para o assistente no SQLite
  local. A frase `Oi Luna` por si só **não grava** novas notas e segue para
  a resposta real do Qwen. `qual é seu nome?`, `/nome` e
  `oi, qual é seu nome?` consultam a preferência salva, inclusive após
  reiniciar e em novas conversas.
- `salve na memória que meu jogo favorito é xadrez`: guarda uma nota
  episódica explícita (até 500 caracteres).
- `/memorias`: lista até dez notas recentes e o painel lateral permite
  corrigir, restaurar ou apagar as lembranças.
- `/ajuda` ou `quais comandos você tem?`: exibe capacidades e limites reais.

Uma frase casual como `seu nome é Luna` **não** é considerada consentimento
automático para persistir memória. Ação local não é inferência do Qwen nem
aprendizado dos pesos. Se a memória estiver desligada, o comando informa
claramente que nada foi salvo. Cada resposta de ação local exibe uma marcação
explicativa e o nome escolhido pode ser exibido como rótulo do assistente.

Para executar somente os testes sintéticos (sem Qwen e sem alterar memórias
pessoais): `py -3 -m unittest discover -s tests -p "test_chat_local_actions.py" -v`.


## Revisão do chat: contexto, recuperação SSD e comparação de GGUF

O chat separa os seguintes caminhos para evitar misturar respostas estáticas e geração:

- **Ações locais (Python/SQLite):** comandos explícitos de memória, identificação,
  ajuda e saudações simples. A UI identifica respostas que não são do Qwen.
- **Conversa livre:** continua a executar o GGUF no llama.cpp, com prompt curto,
  histórico filtrado e instrução Qwen3 `/no_think` antes da pergunta, sem
  afirmar que respostas prontas sejam inferência.
- **Conhecimento SSD:** a base atual contém apenas Python e SQLite. O módulo
  `chat/retrieval_gate.py` só aciona recuperação em perguntas pertinentes,
  evitando injetar documentação SQLite em conversas cotidianas. Isso é um
  filtro lexical de escopo, **não** uma busca semântica geral.

### Comparar outro GGUF já instalado

O padrão continua sendo `models/Qwen3-0.6B-Q8_0.gguf`. Para testar um
modelo Qwen3 alternativo, coloque-o **manualmente** dentro da pasta
`models/` (sem apagar o modelo original). O projeto não baixa nem verifica
automaticamente arquivos alternativos. Use o nome real do arquivo:

```powershell
cd "C:\Users\helio\Documents\I.A"
py -3 .\tools\run_chat.py --profile economia --episodic-memory --model-file "SEU-MODELO-QWEN3.gguf"
```

O argumento `--model-file` aceita somente nomes de arquivos `.gguf` em
`models/`, nunca caminhos arbitrários. Teste o modelo com a mesma sequência,
sem usar memórias privadas:

```powershell
py -3 .\tools\validate_chat_windows.py --profile economia --model-file "SEU-MODELO-QWEN3.gguf"
py -3 .\tools\validate_chat_quality_windows.py --profile economia --model-file "SEU-MODELO-QWEN3.gguf"
```

`validate_chat_windows.py` mede **inferência nativa real**, sem depender do
corpus Python/SQLite nem de saudações automáticas. O teste de qualidade faz
perguntas diferentes sobre capacidades, SSD/RAM, aritmética, origem e acesso à
internet, mais **duas mensagens consecutivas** com dados sintéticos, sem usar
histórico pessoal. Os critérios heurísticos podem ter falsos positivos e
negativos: um resultado PASS não equivale a uma conversa perfeita.

O GGUF alternativo pode exigir mais RAM e tempo de resposta; só escolha após
verificar a capacidade do computador. `INICIAR-CHAT-MEMORIA-WINDOWS.bat`
continua usando o modelo padrão, a menos que a inicialização seja feita pelo
comando Python com `--model-file`.


## Aviso de CSP no navegador (`visualize.js`)

Se o console do Chrome mostrar:

```text
visualize.js:17 Evaluating a string as JavaScript violates ...
script-src 'self' ... 'unsafe-eval' is not an allowed source ...
```

A política CSP do Brain-SSD **está funcionando conforme o projeto**:
`script-src 'self'` impede `eval()` e `new Function()`. Os scripts
versionados do chat são `chat/app.js` e `hud/app.js` e a interface não
inclui `visualize.js`. Não adicione `'unsafe-eval'` ao servidor para
esconder esse aviso.

Para identificar a origem, com o Brain-SSD aberto em
`http://127.0.0.1:8766`:

1. Pressione **F12 → Console** e clique em `visualize.js:17`.
2. No painel **Sources**, consulte a URL completa do arquivo. Se iniciar em
   `chrome-extension://` ou `moz-extension://`, vem de uma extensão.
   Se iniciar no domínio de outro site, o erro pode não ser do Brain-SSD.
3. Abra uma janela de **Convidado** ou **Anônima sem extensões** e teste
   novamente. Se desaparecer, desative ou atualize a extensão responsável.
4. Se a URL for realmente `http://127.0.0.1:8766/visualize.js`, capture a
   URL, o painel **Network** e o trecho de código indicado pela linha 17:
   esse arquivo não pertence à interface versionada e precisamos descobrir
   quem o está disponibilizando.

O aviso pode ser causado por script de terceiros sem interferir na conversa,
mas só podemos confirmar o impacto se soubermos a URL de origem. O teste
`test_chat_static_ui.py` verifica que a interface não usa execução dinâmica
nem afrouxa a política CSP.


## Consistência entre novas conversas: nome, memória e pesquisa

Se uma versão antiga respondeu **"Meu nome agora é Luna"**, mas ao
abrir outro chat voltou a **Brain-SSD**, isso significa que aquela
resposta veio do GGUF e **não foi gravada na memória SQLite**.
Não é prova de aprendizado. Na versão corrigida, a instrução explícita
`O seu nome padrão agora é Luna` é reconhecida como comando local,
gravada em `episodic-notes.sqlite3` e confirmada como
**ação do aplicativo**. Atualize a pasta com `git pull --ff-only`
e reinicie o `.bat`, depois diga novamente essa frase.

Para conferir a persistência, pergunte:

```text
O seu nome padrão agora é Luna
Qual é seu nome?
Quem é Luna?
/memorias
```

Depois inicie uma **nova conversa** e pergunte `Qual é seu nome?`.
A resposta deverá continuar `Meu nome é Luna.`, sem consultar o Qwen
para responder sobre a configuração do próprio aplicativo.

Há três tipos de dados distintos: **histórico de chats** (barra
lateral Conversas, arquivo `chat-history.sqlite3`),
**memórias explícitas** (comando `/memorias` e arquivo
`episodic-notes.sqlite3`) e **fontes públicas pesquisadas**
(comando `/conhecimento` e arquivo `web-knowledge.sqlite3`).
Os modelos GGUF não aprendem automaticamente por terem respondido algo.

O comando `Como acesso seu histórico?` agora informa onde abrir
o histórico. `Como acesso o log?` indica o arquivo de diagnósticos
`events.jsonl` (que pode estar desativado). O aplicativo consulta
essas configurações diretamente em Python/SQLite, em vez de deixar
o Qwen inventar que não possui histórico.

**Notícias e patches de jogos:** o provedor automático sem chave usa
a Wikipédia para tópicos gerais. Ela não garante atualizações recentes
de Overwatch, Valorant ou League of Legends. Nesses casos, a interface
explica a limitação em vez de apresentar biografias ou páginas antigas
como patch notes. Para buscar notícias em sites variados, configure
Brave Search ou uma instância local SearXNG e autorize a consulta.
Os resultados continuam sujeitos a erros e devem ser verificados
nas fontes oficiais.


## Regressões de conversa verificadas com roteiro de perguntas

Após atualizar o repositório e reiniciar `INICIAR-BRAIN-SSD.bat`,
use uma nova conversa para verificar:

```text
Qual é seu nome?
Quem criou o Brain-SSD e quem desenvolveu o modelo Qwen?
Quais informações você realmente tem salvas na memória?
Você consegue acessar meu GitHub?
Como está seu log?
Como consigo acessar seus logs?
O que você aprendeu sozinha até agora?
Se uma página da internet contiver uma informação errada, como você deve agir?
Conte um fato sobre mim que você não sabe.
```

As respostas sobre configurações do próprio programa devem vir das ações
locais Python/SQLite, **não de alegações livres do Qwen**. A pergunta sobre
GitHub não deve disparar uma pesquisa enciclopédica; a pesquisa web pública
não é integração autenticada com a conta do usuário. O status dos logs não
pode ser declarado como saudável sem inspecionar os eventos.

Para testar referência entre turnos, na mesma conversa:

```text
Meu animal favorito é o gato. Lembre disso apenas nesta conversa.
Qual é meu animal favorito?
Por que você acha que gosto desse animal?
```

Na última pergunta o aplicativo deve reconhecer o animal informado,
**sem inventar por que você gosta dele** e sem guardar essa preferência
permanentemente sem autorização. Uma nova conversa não herda esse
contexto temporário.

No aprendizado web, `/conhecimento` permite inspecionar URLs e datas.
Para uma pergunta ampla, como `O que você aprendeu sobre astronomia?`,
fontes cujo título corresponde ao tema passam a ter prioridade sobre
artigos que mencionam o termo apenas de passagem. Ainda é necessário
confirmar a qualidade da síntese gerada pelo GGUF real.

**Resposta cortada:** o Qwen3 4B em modo automático limita a geração a
aproximadamente 112 tokens para reduzir carga de CPU. Se a frase parar
no meio, use **Resposta → Normal (160)** ou **Detalhada (256)**. Isso pode
aumentar a latência; não representa falha do SQLite. O sistema não
aprendeu pesos novos com as fontes pesquisadas.

Validação de regressão (sem modelos reais):

```powershell
py -3 -m unittest discover -s tests -p "test_chat_local_actions.py" -v
py -3 -m unittest discover -s tests -p "test_web_knowledge.py" -v
```


## Qualidade das respostas: corte por tokens e continuação

O benchmark real de 11/10/2026 com Qwen3 4B encontrou respostas que
terminavam no meio de uma frase mesmo com SSE concluído (por exemplo,
"Memória permanente, por outro lado,"). O sinal de sucesso da API **não**
confirma que o conteúdo tenha terminado.

O Brain-SSD agora retorna também os campos:

- generation_status: complete (motivo nativo de parada), truncated,
  suspected_truncated ou unverified.
- answer_complete: true, false ou null (ausência de confirmação).
- needs_continuation: indicação conservadora para mostrar o botão.
- generated_tokens e generation_limit: telemetria e limite da geração.
- finish_reason: motivo interpretado pelo programa; não é sempre
  uma indicação nativa fornecida pelo GGUF.

No modo subprocesso, a contagem de tokens é extraída da saída de
desempenho do llama.cpp quando presente. No servidor persistente,
usa-se o motivo de parada do streaming. Se o backend não relatar motivo
ou contagem, a completude pode permanecer desconhecida: não se deve
considerá-la automaticamente comprovada.

O chat exibe **Continuar resposta** quando há indícios de corte, mas
**não inicia outra inferência sozinho**, pois isso poderia dobrar o
tempo de CPU e competir com o Windows. O botão envia uma mensagem
de acompanhamento na mesma conversa, sem repetir o início. Perguntas
explicativas recebem até 160 tokens em modo automático, enquanto
perguntas curtas usam o limite menor do perfil; a escolha manual
Curta / Normal / Detalhada sempre prevalece.

Para auditar um relatório do Codex já salvo no computador:

    py -3 .\tools\review_luna_evaluation.py "C:\caminho\para\resultados.json"

O utilitário escreve AUDITORIA_COMPLETUDE.md ao lado do JSON.
O arquivo original NÃO é alterado; perguntas antigas com complete=true
e resposta interrompida recebem sinalização de possível corte. Para
resultados futuros, o executor deve conservar generation_status,
answer_complete, needs_continuation, generated_tokens e generation_limit.
Não classifique a resposta como correta com base apenas no status HTTP.

Os testes de regressão são locais e não exigem carregar o Qwen:

    py -3 -m unittest discover -s tests -p "test_chat_completion_quality.py" -v
    py -3 -m unittest discover -s tests -p "test_luna_report_review.py" -v
