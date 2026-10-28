# Luna Arcade S1 — jogo jogável de referência / GameDev AI benchmark

## Duas métricas independentes

1. **Jogo de referência entregue pelo assistente:** roda no navegador, com código original em `site/arcade/`. É avaliado via Playwright real, usando controles de teclado e o estado do Canvas.
2. **Capacidade de a própria Luna construir jogos:** medida separadamente com Qwen real no `tools/evaluate_game_coding_windows.py`; o primeiro desafio é gerar um arquivo JavaScript pequeno com três classes. Resultados negativos são preservados.

**Não apresentar a existência do jogo de referência como evidência de que o Qwen o escreveu.**

## Arquitetura

- `site/arcade/index.html`: menu, HUD, pausa, vitória, controles e três heróis originais — Kael, Lyra e Orin.
- `site/arcade/styles.css`: visual de fantasia, responsividade, teclado, reduced-motion e botões touch.
- `site/arcade/game.js`: física, colisões, pulo, dash, combo, projéteis, especiais com MP, vida, IA simples, três regiões, chefe e arte procedural Canvas.
- `window.__LUNA_GAME_QA__.snapshot()`: observação somente leitura do estado real do motor, sem métodos de mutação/vitória.

## Evidências de navegador

- [Playwright original 6/6](https://github.com/HelioConde/I.A/actions/runs/40625929055): seleção das três classes, movimento, pulo, dano, pausa e screenshots responsivos.
- [Missão completa 7/7](https://github.com/HelioConde/I.A/actions/runs/40626152153): teclado, inimigos, três regiões, chefe, vitória e reinício com espadachim.
- A suíte foi ampliada para exigir vitória com três classes; **consultar o último workflow antes de declarar aprovação**.

O jogo usa assets originais e não reproduz sprites, músicas, nomes comerciais ou código do Grand Chase.

## Publicação

Depois do merge e deploy bem-sucedido, o GitHub Pages publica [Jogar Luna Arcade S1](https://helioconde.github.io/I.A/arcade/). O jogo estático funciona sem banco de dados nem API.

## Como executar testes

Terminal 1, na raiz do projeto:

~~~powershell
python -m http.server 4799 --bind 127.0.0.1 --directory site/arcade
~~~

Terminal 2:

~~~powershell
cd site-tests
npm install
npx playwright install chromium
$env:LUNA_GAME_URL="http://127.0.0.1:4799"
npx playwright test --config playwright.game.config.cjs
~~~

Para medir Qwen real escrevendo código mínimo no seu Windows, sem executar os arquivos gerados:

~~~powershell
python tools/evaluate_game_coding_windows.py --profile economia
python tools/evaluate_game_coding_windows.py --profile equilibrado --model-file Qwen3-4B-Q4_K_M.gguf
~~~

O segundo comando exige o arquivo GGUF exato na pasta `models/`. Cada avaliação grava `results/game_agent/latest.json`, sem aplicar alterações no jogo.

## O que falta para uma IA de jogos autônoma

- Fazer **o próprio modelo** gerar o jogo em vez do assistente entregar o jogo de referência;
- Contexto de múltiplos arquivos e geração longa com planejamento e validação incremental;
- Sandbox que execute código gerado sem acesso a dados privados e com limites rígidos de recursos;
- Ciclo automático de falha Playwright → diagnóstico → patch → novo teste, com aprovação humana;
- Editor Godot 4 real e automação de cenas GDScript;
- Comparação de modelos especializados em código, memória/latência e qualidade por tarefa;
- Revisão manual de gameplay, arte, performance, confiabilidade e segurança.

A meta completa do Luna GameDev permanece **em desenvolvimento** enquanto não houver evidência de sucesso dessas etapas.
