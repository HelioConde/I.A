# Visão J.A.R.V.I.S. — Brain-SSD Windows

## Objetivo de produto

Criar uma experiência inspirada no assistente do Homem de Ferro:
comandos naturais, respostas faladas, conhecimento atualizado do estado
do PC, observação contextual **com permissão** e execução confiável de
tarefas — sem simular capacidades inexistentes. O projeto é independente
da marca e do personagem fictício.

## Etapa atual implementada (outubro de 2026)

| Capacidade | Estado | Limitação |
| --- | --- | --- |
| Qwen local / CPU | Existente | 0.6B é pequeno; pode errar e tem latência |
| Informações do hardware | Implementado | Somente dados obtidos pelo sistema |
| Nome/versão de aplicativos instalados | Implementado (opt-in) | Registro do Windows omite portáteis/MSIX |
| Nomes/PIDs de processos ativos | Implementado (opt-in) | Não equivale a janelas nem diagnostica travamento |
| Janelas por monitor | Implementado com permissão de captura | EnumWindows vê títulos; não lê pixels |
| Captura dos monitores | Implementado com permissão | Sem OCR ou visão |
| Abrir Bloco de Notas / Calculadora | Implementado (opt-in + confirmação por botão) | Duas aplicações fixas, sem argumentos; abertura da janela não comprovada pelo backend |
| Falar respostas automaticamente | Implementado (opt-in na interface) | Somente voz pt-BR/pt marcada como `localService` pelo navegador |
| Reconhecimento de fala por microfone | Não implementado | Não há captura de áudio em segundo plano |
| Corrigir Godot diretamente pela tela | Não implementado | Falta OCR/visão e plano seguro de ações |

### Inicialização segura

Use `INICIAR-COPILOTO-WINDOWS.bat`. O iniciador pergunta separadamente
permissões para: (1) ler uma pasta, (2) capturas sob demanda,
(3) consultar nomes de aplicativos e processos, (4) preparar abertura
de Bloco de Notas ou Calculadora com confirmação individual no chat.

As permissões de aplicativos **não** requerem acesso a `C:\` como pasta
autorizada. Prefira conceder só as pastas dos projetos.

Exemplos que devem ser encaminhados às ferramentas locais, sem solicitar
ao Qwen que invente resultados:

- `Quais programas estão instalados no meu computador?`
- `Tenho o Godot instalado?`
- `O Chrome está aberto?`
- `Quais programas estão em execução no meu computador?`
- `Abra o Bloco de Notas agora.` → apenas **proposta**; botão
  `Confirmar abertura` → um pedido de execução do executável fixo
- `Abra a Calculadora agora.` → mesma regra

Se for perguntado `Abra o Godot agora`, a resposta é indisponibilidade
por enquanto; jamais execute caminhos informados pelo usuário ou retirados
do conteúdo de arquivos sem uma nova implementação auditada.

Confirmações: token aleatório de uso único, guardado somente em RAM por
até 90 segundos. O token não entra no histórico SQLite, não aceita nome
de arquivo ou linha de comando arbitrária e não executa por uma
resposta gerada pelo modelo.

### Voz

Marque `Voz automática local` no compositor do chat quando houver uma
voz portuguesa instalada e informada como local pelo navegador.
Sem voz local, o controle fica desabilitado. A leitura manual anterior
(`Ouvir resposta`) permanece disponível; dependendo da voz escolhida,
o navegador **pode** usar um serviço de voz remoto, portanto não é
necessariamente privada. A voz automática usa somente vozes marcadas
`localService` para evitar essa ambiguidade, dentro do que o navegador
relata.

Não há escuta contínua, palavra de ativação ou transmissão de áudio do
microfone pelo Brain-SSD nesta etapa.

## Próximas etapas — ordem recomendada

### Fase 2: visão e diagnóstico local

1. OCR **local** on-demand (monitor escolhido, sem enviar pixels à web),
   comparando alternativas compatíveis com CPU/Windows. Exibir ao usuário
   o texto reconhecido antes de sugerir mudanças.
2. Leitura de logs e projetos Godot dentro de pastas autorizadas;
   correlacionar mensagem de erro, stack trace e arquivo real.
3. Geração de diff de correção, com pré-visualização e aprovação antes
   de alterar arquivos. Criar backup transacional e opção de desfazer.

### Fase 3: automação controlada

1. Registro de aplicativos aprovados pelo próprio usuário (Godot,
   VS Code, Steam), sem procurar e executar arbitrariamente qualquer
   `.exe`; validar o caminho e editor/publisher quando aplicável.
2. Ações de mouse/teclado apenas com autorização específica, escopo
   de janela e botão de parar sempre visível.
3. Rotinas multi-etapas com plano visível, confirmação de cada ação
   sensível, logs de auditoria locais e rollback quando possível.

### Fase 4: voz estilo assistente

1. Escolher runtime STT local na CPU (por exemplo, projetos baseados em
   Whisper.cpp ou Vosk), medir memória e latência reais.
2. Adicionar `pressionar para falar` antes de cogitar detecção de
   palavra-chave, e avisar claramente quando o microfone estiver ativo.
3. Uma voz TTS local estável, com saída incremental e possibilidade de
   interrupção instantânea.

### Fase 5: agente contextual

Perfis de tarefas (`Programação/Godot`, `Sistema`, `Pesquisa`),
planejamento de ações e ferramentas rastreáveis. A IA deve sempre
distinguir: `sei responder`, `consultei o sistema`,
`preciso de autorização` e `executei e confirmei o resultado`.

## Qualidade e avaliação

Repetir `tools/run_copilot_question_battery.py --full` na máquina
real após reiniciar o servidor. Quando os recursos autorizados estão
ativos, os casos de aplicativos instalados e de processos deixam de ser
resolvidos por resposta geral do Qwen e passam a ter uma fonte concreta.
O PASS do executor indica uso da rota correta — exatidão dos itens e
versões requer conferência com o Windows.

Verificar no CI:
`python -m unittest discover -s tests -p "test_jarvis_apps.py" -v`
e `node --check chat/app.js`. Não alegar aprovação física do PC,
da voz, da captura ou da abertura real de janelas com base apenas em mocks.

Documentação Windows usada para a arquitetura: registros de desinstalação
e App Paths, APIs de processos e orientações de ShellExecute no Microsoft
Learn. Evitar `Win32_Product`, cujo uso pode disparar verificações e
reparações de pacotes MSI.
