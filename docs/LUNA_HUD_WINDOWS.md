# Luna HUD v1 — central de comando local

A Luna é a interface visual do Brain-SSD. O modelo de linguagem continua sendo o Qwen local escolhido pelo iniciador; não há novo modelo ou serviço externo.

## Entregue

- Núcleo animado com estados de conexão, escuta local e resposta.
- Painel de contexto com modelo, perfil, projeto informado manualmente e permissões.
- Ações rápidas seguras: Copiloto, métricas e sugestões que apenas preenchem o chat.
- Atividade da interface efêmera, sem gravação em disco.
- Interface responsiva com painel recolhido em telas até 900 px.
- Preferência por movimento reduzido e estados acessíveis.

## Executar no PowerShell

```powershell
Set-Location "C:\Users\helio\Documents\I.A"
git fetch origin
git switch feat/ssd-weight-streaming-lab
git pull --ff-only origin feat/ssd-weight-streaming-lab
.\INICIAR-COPILOTO-WINDOWS.bat
```

Se o servidor local já estiver aberto, reinicie-o para ler os novos arquivos. Atualize o navegador com Ctrl+F5 caso veja a interface antiga.

## Arquivos

| Arquivo | Responsabilidade |
| --- | --- |
| chat/index.html | Marca e layout Luna |
| chat/luna-hud.css | Tema, animações, responsividade |
| chat/luna-hud.js | Estados observáveis e ações rápidas |
| chat/app.js | Eventos reais de conexão, chat, mic e permissões |
| src/brain_ssd/chat/server.py | Servir CSS e JS pelo mesmo servidor local |
| tests/test_chat_static_ui.py | Contratos estáticos de segurança e interface |

## Privacidade e limites

O HUD não lê arquivos, não captura tela, não liga microfone e não executa comandos automaticamente. Essas ações permanecem atrás de consentimento e permissões do Copiloto.

Projeto é somente um rótulo derivado do caminho que o usuário digitar; não é uma identificação automática da janela ativa. O painel não inventa medições de RAM/CPU. As métricas reais seguem disponíveis no botão Métricas.

Esta é uma interface web local, não um overlay do Windows sempre visível. Ainda faltam testes de screenshot no PC Windows e revisão visual com o usuário. A branch main e o runtime Qwen não foram alterados.

## Permissões e caminhos persistentes: LUNA.ini

O launcher INICIAR-COPILOTO-WINDOWS.bat agora não faz perguntas interativas a cada abertura.
Na primeira inicialização, tools/launch_luna.py cria **LUNA.ini** na raiz do projeto a partir de **LUNA.exemplo.ini**.
O arquivo real é pessoal e está no `.gitignore`: suas escolhas não são enviadas ao GitHub por padrão.
Cada inicialização lê novamente o INI. Se o arquivo já existir, ele **não é sobrescrito**.

Abra o arquivo com `notepad .\LUNA.ini` no PowerShell e ajuste:

```ini
[luna]
profile = economia
; vazio = usa a estrategia do perfil existente
core_mode =
model_file =
port = 8766
open_browser = true
episodic_memory = true
cognitive_shadow = true
memory_aliases = false
web_search = true
web_provider = auto

[copilot]
; A pedido do usuario, o exemplo usa C:/ como root.
root = C:/
extra_roots =
screen = true
apps = true
launch = true
edit = true
godot_validate = true
godot_path = C:\godot
```

Use `true` ou `false`. Para autorizar mais pastas, separe os caminhos em `extra_roots` com `;` (por exemplo: `D:/Projetos;E:/Jogos`).
Não inclua aspas ao redor de caminhos. Se `model_file` for preenchido, use somente o nome do arquivo GGUF na pasta `models/`.

**Aviso:** `root = C:/` abrange o disco inteiro, exceto caminhos protegidos pelo Copiloto. Recomendamos trocar por uma pasta de projetos se esse acesso amplo não for necessário.

### Godot

`godot_path` aceita o caminho completo de um executável como `C:\godot\Godot_v4.5-stable_win64.exe`,
ou uma pasta como `C:\godot` que contenha **um** executável `Godot*.exe` em sua raiz ou em `bin/`.
Se o executável não existir ou houver múltiplos candidatos, **somente a validação Godot é desativada com um aviso**.
O Chat, o Copiloto, a leitura de pastas e o editor continuam disponíveis.
Para desligar explicitamente: `godot_validate = false`.
Mesmo quando ativo, cada verificação de scripts Godot exige confirmação individual.

### Verificar sem abrir a Luna

```powershell
Set-Location "C:\Users\helio\Documents\I.A"
py -3 .\tools\launch_luna.py --check
py -3 -m unittest discover -s tests -p "test_launch_luna_ini.py" -v
```

Depois execute `.\INICIAR-COPILOTO-WINDOWS.bat` normalmente.
Se aparecer erro de INI, ajuste a opção indicada. Não há leitura de `%VAR%`, shell ou execução de comandos a partir dos valores do INI.

## Microfone: reconhecimento de fala local

O botão `Falar (local)` só é habilitado quando o navegador confirma
reconhecimento **no dispositivo** para `pt-BR` via Web Speech API.
Permissões do Copiloto em `LUNA.ini` (`screen`, `apps`, `launch`) não
habilitam o microfone do navegador.

Se não houver pacote, a interface informa a causa e apresenta `Instalar pt-BR offline`
**apenas quando** o próprio navegador declarar o pacote como `downloadable`.
O clique pede confirmação explícita: a instalação pode baixar componentes
pela internet, porém as transcrições posteriores continuam configuradas
com `processLocally = true`. Não há fallback automático para speech-to-text remoto.

Se o navegador declarar `unavailable` ou não implementar esta API
experimental, a fala permanece indisponível. O botão `Verificar novamente`
permite reavaliar após uma atualização ou mudança de permissão.
Confira o microfone nas permissões do site `http://127.0.0.1:8766`
(a porta pode variar com a configuração).

Alternativa futura: integrar um motor speech-to-text local próprio, independente
do suporte de idioma no navegador, com instalação e permissões explícitas.

## Revisão do chat real (12/10/2026)

Após capturas de tela e histórico real do usuário, a interface recebeu correções
de confiabilidade. Respostas do Qwen **não são evidência de que uma ferramenta
do Windows tenha executado uma ação**.

- Abas de Chrome/Edge: Luna informa que não as enumera e não inventa títulos/URLs.
- Pastas principais: lista subpastas realmente permitidas na primeira raiz autorizada; sem diagnóstico de CPU no lugar da listagem.
- Programas abertos: quando permitido, consulta títulos de janelas visíveis do Windows (não os confunde com processos de segundo plano).
- Jogos instalados: não confunde o registro de programas com uma lista completa de jogos.
- Monitor/tela: pergunta de capacidade não é uma captura; `Mostre o monitor 2` solicita a prévia. O Qwen textual não interpreta pixels.
- Downloads: a primeira imagem é escolhida **por nome em ordem alfabética entre até 100 itens listados**; a prévia local depende de autorização/Pillow e não é reconhecimento visual.
- Escrita em `.txt`: ainda não é ferramenta disponível; Luna diz claramente que **nenhum arquivo foi criado**. Edição de CÓDIGO permanece com diff e confirmação.
- Google via Serper: sem `SERPER_API_KEY` ou se o provedor não usa Serper, não afirma que fez pesquisa Google. A caixa `Pesquisar na web` continua autorização por mensagem.
- Notícias recentes em geral: sem permissão, provedor adequado ou resultados verificáveis, não inventa fatos. Os roteadores específicos já existentes para Brasil e atualizações de jogos foram preservados.
- Legibilidade do painel direito: fontes maiores, área de rolagem independente e cartões mais compactos em altura.

Testes de regressão: `tests/test_luna_real_world_regression.py` e
`tests/test_chat_web_search.py`, com chamadas locais simuladas sem leitura
do PC do usuário. O GitHub Actions ainda precisa executar os testes
com logs para confirmarmos aprovação, além de revisão visual em Windows.

Para validar após atualizar/reiniciar a Luna:

```powershell
py -3 -m unittest discover -s tests -p 'test_luna_real_world_regression.py' -v
py -3 -m unittest discover -s tests -p 'test_copilot_queries.py' -v
py -3 -m unittest discover -s tests -p 'test_chat_web_search.py' -v
```

## Ajustes a partir dos screenshots: painel e respostas da Luna

- O painel direito estava comprimindo cada cartão (`flex-shrink: 1`) e
  ocultando textos como `Respondendo`, permissões e ações rápidas.
  Os cartões agora mantêm a altura do conteúdo e o painel rola
  verticalmente; a barra esquerda também pode rolar sem perder conteúdo.
- Perguntas sobre **as abas abertas** (inclusive `quais as minhas abas`
  e o acompanhamento `mas isso são programas, não abas`) recebem uma
  resposta honesta: os processos `chrome.exe` de `tasklist.exe` não são
  URLs nem nomes das abas do navegador.
- Se a transcrição de voz disser apenas `verifique o que está aberto
  no Google Chrome`, sem especificar abas ou processos, a Luna pede
  esclarecimento antes de executar o inventário de processos.
- Perguntas se consegue ver `o que está aberto no meu computador`
  descrevem as permissões/capacidades, sem alegar que já inspecionou a máquina.
- `Olá bom dia`/`Olá, bom dia` agora têm respostas locais de saudação;
  não recuperam páginas Wikipédia sobre a palavra `oi`.
- `Quais as informações de hoje?` pergunta qual assunto foi pretendido.
- `Qual vai ser o clima em Brasília hoje?` informa que ainda não há
  serviço de previsão meteorológica ao vivo integrado. Nem a caixa
  `Pesquisar na web` autoriza fabricar uma previsão.

Teste offline de regressão:

```powershell
py -3 -m unittest discover -s tests -p "test_luna_hud_trust_followups.py" -v
py -3 -m unittest discover -s tests -p "test_luna_real_world_regression.py" -v
py -3 -m unittest discover -s tests -p "test_chat_learning_news.py" -v
```

**Limitações ainda existentes:** a Luna não enumera abas do Chrome/Edge
sem uma integração de navegador com autorização explícita; não há
API meteorológica configurada nem OCR/vídeo inferido automaticamente.
Não foi realizada validação visual/screenshot no Windows nesta alteração.

## Perguntas básicas verificáveis — correção de 12/10/2026

Após a bateria real de perguntas ao Qwen local, a Luna passou a responder
**sem geração neural** quando a resposta depende exclusivamente de fatos
do computador ou do histórico salvo:

- **Data de hoje:** obtida pelo relógio/fuso local do processo Windows, nunca inferida do prompt nem da internet.
- **Modelo utilizado:** nome exposto pelo runtime ativo (por exemplo `Qwen3-0.6B-Q8_0.gguf`), separado do nome da interface (Luna) e do projeto (Brain-SSD).
- **Estado de conversa:** responde como assistente de software, sem simular emoções humanas.
- **Primeira pergunta da conversa:** recuperada da primeira pergunta identificável do usuário no SQLite, pulando cumprimentos iniciais. Aceita perguntas sem `?` quando reconhecidas pela abertura interrogativa, comum na transcrição por voz. Se não for possível identificá-la, explica a limitação.
- **Primeira mensagem da conversa:** recuperada literalmente do SQLite, incluindo um cumprimento inicial como `Olá, bom dia!`.
- **Últimas cinco mensagens:** extrato rotulado das mensagens efetivamente fornecidas pelo histórico recente, sem inventar turnos inexistentes.
- **Capacidade de memória:** distingue histórico local SQLite de lembranças episódicas salvas explicitamente.
- **Informações de hoje sem assunto:** pede que o usuário escolha notícias, previsão do tempo ou tarefas.

O nome Luna foi aplicado ao prompt de conversa. Isso não altera pesos do Qwen
nem garante que o modelo pequeno sempre compreenda acompanhamentos complexos.

Limitações: se não houver `conversation_id` válido e histórico SQLite
acessível, a Luna não inventará a primeira pergunta; ela explicará
que não conseguiu verificá-la. Os extratos de cinco mensagens não são
um resumo semântico gerado pelo Qwen. As previsões e notícias continuam
dependendo de provedores específicos e autorização por mensagem.

**Verificação no Windows:**

```powershell
Set-Location "C:\Users\helio\Documents\I.A"
git pull --ff-only origin feat/ssd-weight-streaming-lab
py -3 -m unittest discover -s tests -p 'test_luna_session_facts.py' -v
py -3 -m unittest discover -s tests -p 'test_luna_real_world_regression.py' -v
py -3 -m unittest discover -s tests -p 'test_chat_history.py' -v
```

Reinicie a Luna para atualizar o servidor Python, inclusive no modo ligação.
