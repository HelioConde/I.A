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
