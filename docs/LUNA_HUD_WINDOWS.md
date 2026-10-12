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
