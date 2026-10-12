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
