# Brain-SSD — Copiloto de programação (versão experimental)

Objetivo: avançar em direção a um assistente local capaz de analisar código,
propor modificações, executar tarefas explicitamente aprovadas, reconhecer
texto na tela e interagir por voz.

## O que foi implementado

1. **Inspeção estática de código**: no painel Copiloto, escolha um arquivo
   dentro da pasta autorizada e clique **Inspecionar código**. A inspeção
   apresenta tamanho, linhas, TODO/FIXME, linhas muito longas e erros de
   sintaxe Python. Não executa o projeto.
2. **Recomendações pela IA local**: escolha um arquivo e clique
   **Recomendações no chat**. Um trecho do arquivo será incluído no
   compositor com instruções de não confiar no conteúdo como comandos.
   Revise e envie voluntariamente; o Qwen é textual e limitado.
3. **Editor com confirmação**: escolha um arquivo, abra
   **Editar código com prévia e backup**, forneça o trecho original e a
   substituição. A prévia mostra o diff. Somente o clique em **Confirmar
   edição no disco**, seguido de confirmação do navegador, aplica a
   substituição e salva um backup privado em
   `%LOCALAPPDATA%\BrainSSD\code-edit-backups\`.
4. **Recomendações verificadas**: `/recomendar pc` consulta hardware autorizado,
   apresenta recomendações limitadas e informa quais métricas não foram medidas.
   Não monitora permanentemente o sistema.
5. **Comandos do chat**: `/revisar C:\caminho\meu.gd`, ou
   `/trocar "C:\caminho\meu.gd" "speed = 10" => "speed = 20"`.
   O segundo comando prepara uma proposta e botão de confirmação;
   **não modifica o arquivo automaticamente**.
5. **Monitor/OCR opcional**: no painel, escolha o monitor e clique em
   **Ler texto (OCR local)**. Exige `mss`, `Pillow`, a biblioteca
   `pytesseract` e a instalação nativa do Tesseract OCR, com dados de
   idioma `por` ou `eng`. Sem isso, informa indisponibilidade.
   O OCR pode cometer erros e não equivale a compreensão visual.
   Nenhum texto reconhecido é enviado à IA sem seleção explícita.
6. **Voz**: `🎤 Falar (local)` fica habilitado apenas quando o navegador
   anuncia reconhecimento `pt-BR` no dispositivo por meio de
   `SpeechRecognition.available({langs:["pt-BR"],processLocally:true})`.
   Se não estiver disponível, permanece desabilitado; não usa serviços
   de transcrição remotos automaticamente. A fala reconhecida preenche
   a mensagem e requer envio do usuário.

## Como autorizar

Use `INICIAR-COPILOTO-WINDOWS.bat`. Na inicialização escolha uma pasta
pequena e específica do seu projeto (não todo `C:\`) e habilite
**editar código** separadamente. As permissões de captura e consulta aos
programas do Windows continuam independentes.

**Limites do editor:** somente arquivos UTF-8 de código, até 80 KB, com
substituição de trecho único e diff máximo de 18 KB. As autorizações
de aplicação duram 90 segundos e só podem ser usadas uma vez. Arquivos
alterados externamente invalidam a proposta. Executáveis e scripts
`.bat`, `.ps1` e `.sh` não são editáveis por esse fluxo.

## O que ainda falta para um J.A.R.V.I.S. completo

- **Planejador de agente e loop de ferramentas**: interpretação de pedidos
  gerais de mudança pelo modelo, geração de patches e verificação
  automática com testes. O editor implementado ainda é de substituição
  explícita; não é uma IA que refatora projetos autonomamente.
- **Diagnóstico visual contextual**: OCR extrai texto, mas ainda é
  necessário interpretar posições, janelas, imagens e correlacionar
  erros do Godot a arquivos e linhas.
- **Abertura de Godot/VS Code**: continua limitada à allowlist anterior
  (Bloco de Notas e Calculadora). Outros programas dependem de novo
  registro seguro e aprovação específica.
- **Conversa continuamente duplex**: a versão atual usa entrada por
  pressionar para falar, geração SSE e saída de voz opcional; não há
  escuta passiva permanente nem interrupção semântica em tempo real.
- **Recomendações proativas contínuas**: hoje são acionadas sob demanda.
  Monitoramento e sugestões automáticas exigirão opt-in por janela,
  limites, proteção contra dados sensíveis e um botão de parada.

## Testes

```bat
py -3 -m unittest discover -s tests -p "test_copilot_code_edits.py" -v
py -3 -m unittest discover -s tests -p "test_copilot.py" -v
py -3 tools\run_copilot_question_battery.py --full
```

Testes de CI não comprovam a execução física da UI, reconhecimento de
voz ou OCR no computador do usuário. Repita estes fluxos localmente.

## Verificação e desfazer (nova etapa)

Depois de clicar em **Confirmar edição no disco**, use **Verificar última
alteração** para comprovar que o arquivo atual ainda corresponde ao SHA-256
gravado. O resultado não garante que o código funciona.

O botão **Preparar desfazer** compara o arquivo ao conteúdo aplicado,
verifica o backup e mostra a diferença inversa. **Confirmar desfazer**
exige nova autorização antes de restaurar o arquivo. Somente a última
edição da sessão pode ser revertida, durante até 30 minutos, e a
prévia expira em 90 segundos. Reversão é rejeitada se o arquivo ou
o backup foi modificado desde a operação original.

Quando o Agent Core encontra um arquivo relacionado ao erro, use
**Selecionar arquivo encontrado no editor** para transferir seu caminho
ao fluxo de edição, sem aplicar alterações automaticamente.

Testes específicos:
```bat
py -3 -m unittest discover -s tests -p "test_copilot_code_edits.py" -v
```
