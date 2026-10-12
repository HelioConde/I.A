# Brain-SSD — diagnóstico Godot com evidências

## Capacidades

O copiloto pode inspecionar um projeto Godot autorizado, listar scripts, cenas e comentários TODO/FIXME, e correlacionar texto de erros reais com caminhos de recursos e linhas presentes nos arquivos. Essa função não executa o Godot, não muda arquivos e não inventa causas de erros.

## Uso

Inicie INICIAR-COPILOTO-WINDOWS.bat e autorize somente a pasta do projeto que contém project.godot. No painel Copiloto, seção Diagnóstico de projeto Godot, preencha a pasta, clique em Inspecionar projeto, cole o erro do Godot e clique em Encontrar arquivo e linha do erro.

Comandos no chat:

    /projeto C:\Users\helio\Documents\Slime-Harvest
    /erro-godot "C:\Users\helio\Documents\Slime-Harvest" :: SCRIPT ERROR: at res://scripts/player.gd:42

A busca dá preferência a res:// e a uma linha explícita; procura um basename somente quando ele for único. Arquivos protegidos, symlinks e caches .godot são excluídos. A inspeção limita-se a 180 diretórios, 3500 entradas, 250 arquivos e profundidade 8. O texto de erro deve ter no máximo 4000 caracteres.

## Monitor e privacidade

Uma pergunta explícita como "Olhe para o monitor 2 e identifique o erro no Godot" pode chamar OCR local se Tesseract e pytesseract estiverem instalados. OCR extrai texto imperfeitamente e não compreende pixels semanticamente.

Quando feito pelo painel, o texto extraído não é encaminhado ao chat sem clicar em Usar texto no chat. Quando solicitado no próprio chat, a transcrição aparece na resposta e pode ser mantida no histórico de texto. Evite pedir OCR em telas com senhas ou dados sensíveis.

## Testes

    py -3 -m unittest discover -s tests -p "test_godot_diagnostics.py" -v
    py -3 -m unittest discover -s tests -p "test_copilot_queries.py" -v

Os testes usam projetos temporários e não precisam executar Godot. A associação entre arquivo e mensagem do erro não comprova automaticamente a correção. Para editar, utilize o fluxo existente de diff, confirmação e backup.

## Próximas fases

Selecionar contexto do projeto por sessão, planejar patches com a IA e provas de origem, verificar a alteração com testes seguros executados sob autorização, e permitir ação reversível com botão de parada. A inferência Qwen 0.6B continua limitada e não equivale a um agente autônomo validado.

## Verificação real de GDScript (opt-in, com confirmação)

Esta etapa adiciona um validador de sintaxe com o executável Godot do
próprio usuário. O Godot é iniciado **somente após** um pedido explícito
e um segundo clique de confirmação. A execução termina em até 30 segundos.
Não há execução arbitrária de comandos PowerShell, shell ou scripts externos.

Ao iniciar `INICIAR-COPILOTO-WINDOWS.bat`, autorize uma pasta de projeto
e, quando perguntado, forneça o **caminho completo** do executável Godot
(exemplo: `C:\Ferramentas\Godot_v4.6.1-stable_win64.exe`).
O Brain-SSD não instala nem escolhe esse executável sozinho.

Depois acesse o painel **Diagnóstico de projeto Godot**, digite
`res://scripts/player.gd` e pressione **Preparar verificação**.
Revise o binário, o projeto e o aviso. Apenas o botão
**Confirmar execução de Godot**, mais a confirmação do navegador,
inicia o processo.

Também há um comando textual:

```text
/validar-godot "C:\Users\helio\Documents\MeuJogo" :: res://scripts/player.gd
```

O comando por si só **não executa** o Godot; ele retorna uma proposta
que pode ser confirmada no chat.

O sistema usa os argumentos fixos `--headless --recovery-mode --path
<projeto> --script res://arquivo.gd --check-only`, conforme a documentação
de linha de comando do Godot:
https://docs.godotengine.org/pt-br/4.x/tutorials/editor/command_line_tutorial.html

**Aviso de segurança:** modo headless e `--check-only` não criam uma
sandbox de sistema; Godot pode carregar plugins/extensões ou criar caches
na pasta do projeto. Use essa função apenas para projetos locais confiáveis.
O motor, o manifesto e o script precisam continuar sem alterações entre
a proposta e a confirmação. Os pedidos expiram em 90 segundos e são
usados uma única vez.

Os resultados indicam `PASS` (processo retornou exit code 0),
`FAIL` (exit code diferente de 0) ou `TIMEOUT` (30 segundos).
Mesmo PASS não significa que o jogo foi executado, que os testes de
gameplay passaram ou que o bug visual foi resolvido.

Para regressão sem abrir Godot:
```bat
py -3 -m unittest discover -s tests -p "test_godot_validation.py" -v
```

Os testes de regressão interceptam `subprocess.run`, criam um projeto
temporário e não iniciam o executável real.
