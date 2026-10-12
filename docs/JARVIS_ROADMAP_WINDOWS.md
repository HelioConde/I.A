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
| Captura dos monitores | Implementado com permissão | Captura JPEG, sem compreensão visual pelo Qwen |
| Abrir Bloco de Notas / Calculadora | Implementado (opt-in + confirmação por botão) | Duas aplicações fixas, sem argumentos; abertura da janela não comprovada pelo backend |
| Falar respostas automaticamente | Implementado (opt-in na interface) | Somente voz pt-BR/pt marcada como `localService` pelo navegador |
| Editar arquivos de código autorizados | Implementado (opt-in + diff/backup) | Substituição textual exata, confirmada manualmente; não é refatoração autônoma |
| Extrair texto da tela com OCR | Parcial | Tesseract e dependências locais opcionais; OCR pode errar |
| Reconhecimento de fala por microfone | Parcial (pressionar para falar) | Só em navegadores com reconhecimento pt-BR local; sem escuta contínua |
| Localizar erro Godot e analisar projeto | Implementado parcialmente | OCR opcional, referência res://, ainda sem validação em execução ou correção autônoma |
| Validar sintaxe de script Godot | Implementado (opt-in + confirmação) | Executa Godot headless --check-only no projeto confiável, não equivale a testar gameplay |
| Agent Core — investigações em etapas | Primeira versão implementada | Plano revisável e leitura real de Godot/código/PC; não gera patches ou executa tarefas arbitrárias |

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


### Entrega da etapa Godot

A inspeção de projetos e o diagnóstico vinculado a texto de erros estão em
`src/brain_ssd/chat/godot_diagnostics.py`, acessíveis pelo painel Copiloto e
pelos comandos `/projeto` e `/erro-godot`. A ferramenta não executa o
jogo nem afirma que encontrou a causa apenas por identificar arquivo/linha.

Use `docs/GODOT_COPILOT_DIAGNOSTICS.md` para testar e compreender limites.
A próxima prioridade é um ciclo de agente com **plano revisável, edição
confirmada e verificação de execução**, não uma automação irrestrita.

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

### Agent Core v1

O fluxo de investigação em etapas está no arquivo
`src/brain_ssd/chat/agent_core.py`, com controle no painel Copiloto e
comandos `/investigar-godot`, `/investigar-projeto`,
`/investigar-codigo` e `/investigar-pc`. O sistema separa plano,
confirmação da leitura, execução de ferramentas e relatório com
fontes. Ele **não** aplica alterações nem executa comandos gerados por IA.

Consulte `docs/AGENT_CORE.md` para instruções. A próxima etapa é
integrar geração de patches a partir das evidências com testes e rollback,
sem eliminar a confirmação humana.

### Estado do ciclo de programação

O sistema agora permite inspecionar o projeto, localizar um erro textual,
propor uma substituição exata com diff/backup e, separadamente, executar
uma verificação limitada do parser Godot com consentimento por execução.

**Ainda não existe agente autônomo multi-arquivo**: o Qwen pequeno não gera
nem aplica patches de forma geral, não roda testes independentes automaticamente,
não acompanha mudanças visuais por monitoramento contínuo e não confirma que
um bug foi corrigido. Para essa fase serão necessários planejamento,
verificação de artefatos, reversão, ferramentas mais robustas e validação no PC.

### Fluxo de edição reversível

Uma edição de trecho autorizada pode agora ser verificada por SHA-256
e desfeita pelo backup local após revisão do diff reverso e confirmação.
A proteção se limita à última edição nesta sessão e exige que o arquivo
permaneça inalterado desde a aplicação. O Agent Core pode selecionar
um arquivo real encontrado na investigação para o editor, mas não
produz patches de código por conta própria. A execução de testes
funcionais continua separada e ainda não existe agente programador
autônomo com ciclo de validação.
