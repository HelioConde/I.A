# Ornith 1.5 9B autoreparo genuíno do próprio jogo

O código gerado realmente pelo Ornith, extraído da execução 40653494692, passou em 2/4 testes no replay 40659377921. Falhou no pulo por player.vy não inicializado e no KeyZ por tratar `KeyboardEvent.key` como `code`. Solicitar ao próprio Ornith dois patches pequenos, preservar prompts e SHA, depois testar Chromium real e não publicar automaticamente.
