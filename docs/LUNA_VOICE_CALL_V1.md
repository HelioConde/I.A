# Luna — modo ligação local (V1)

## Estado

Primeiro modo de ligação implementado no commit `4b6a5f3`, com correções adicionais de ciclo de vida e interrupção na branch `feat/ssd-weight-streaming-lab`.

- O reconhecimento usa Web Speech API com `processLocally = true`, sujeito a pacote offline `pt-BR` instalado e permissão de microfone do navegador.
- O áudio sintetizado usa uma voz local de `speechSynthesis`, com preferência por `pt-BR`.
- A chamada é **half-duplex**, em turnos: ouvir → 1 s após fim da fala → transcrever → gerar resposta pelo Qwen via SSE → TTS → ouvir novamente.
- O microfone fica inativo durante a reprodução para evitar realimentação. Não há barge-in automático e ainda não existe garantia de supressão de eco em todas as configurações.
- A interrupção manual interrompe o TTS e solicita cancelamento da geração **da própria chamada** quando houver solicitação pendente. A escuta deve retomar depois que `app.sending` for liberado.
- Encerrar a ligação agora também solicita cancelamento de geração pendente iniciada pela ligação; callbacks tardios não reabrem microfone nem reproduzem uma resposta.
- Temporizador de silêncio é cancelado em `onspeechstart`, não em `onresult`: resultados finais de STT podem chegar após `onspeechend`.
- O painel não grava áudio no disco. O navegador pode utilizar seu próprio mecanismo interno de processamento de áudio e permissões.

## Testes

Testes determinísticos com microfone e Qwen simulados:

```powershell
Set-Location "C:\Users\helio\Documents\I.A"
node --check .\chat\luna-call.js
node --test .\tests\test_luna_call_state.cjs
py -3 -m unittest discover -s tests -p 'test_chat_static_ui.py' -v
```

Os testes simulam início, encerramento, interrupção manual durante TTS/geração, microfone silenciado, fala retomada antes do tempo de silêncio, transcrição final tardia e bloqueio de chamada enquanto um chat digitado está ativo.

**Ainda não é validação física.** É preciso testar o navegador, microfone, voz local, SSE e estado do Windows. O GitHub Actions pode estar indisponível mesmo quando testes locais passam.

## Teste manual Windows

1. Execute `git pull --ff-only origin feat/ssd-weight-streaming-lab` na pasta do projeto.
2. Feche o processo do servidor Luna anterior, depois execute `.\INICIAR-COPILOTO-WINDOWS.bat`.
3. Abra o endereço local configurado (por exemplo `http://127.0.0.1:8766`) e atualize com `Ctrl+F5`.
4. Confira `Falar (local)` para verificar o reconhecimento offline de `pt-BR` e autorize o microfone apenas para a página local.
5. Clique **Conversar por voz → Iniciar ligação** e diga `Luna, me conte o que é memória episódica`.
6. Aguarde a resposta falada e faça uma segunda pergunta, sem novo clique.
7. Interrompa o TTS com **Interromper resposta**, verifique se a Luna volta a escutar e tente outra frase.
8. Repita uma conversa longa, teste **Silenciar microfone** e **Encerrar ligação durante Pensando**; o processo de geração deve receber cancelamento.

## Limites e segurança ainda pendentes

**Importante: a chamada reutiliza o `send()` do chat.** Não há ainda sinalizador isolado de backend que proíba todas as ferramentas/copiloto para mensagens por voz. Portanto, não afirmar que comandos falados são incapazes de disparar ferramentas locais; confirmações sensíveis do backend permanecem em vigor. Antes de abrir comandos por voz como recurso confiável, implementar isolamento explícito `voice_only` no servidor e testes de negação de ações.

A opção `Pesquisar na web` pertence ao formulário do chat; não usar essa opção com fala até termos uma política específica e verificável de autorização por ligação.

Faltam testes reais de `getVoices()`, pausa longa do TTS, troca de microfone, perda de permissão, latência de ida/volta e uso de memória.

## Próximos passos

Implementar modo de voz isolado no backend sem acesso a ferramentas e sem web por padrão; instrumentar latência de STT, Qwen e TTS; configurar opções reais de áudio em `LUNA.ini` quando estiverem conectadas; estudar VAD e barge-in sem comprometer a segurança nem a execução local.
