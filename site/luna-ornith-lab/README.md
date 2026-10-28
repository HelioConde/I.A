# Luna GameDev — minijogo experimental Ornith 1.5 9B

Este é um **minijogo independente de benchmark**, escrito pelo **Ornith 1.5 9B Q4_K_M** e testado com CPU. O modelo gerou a versão inicial e corrigiu dois defeitos de seu próprio JavaScript. Não é o Arcade S1 do ChatGPT e não tem a profundidade do jogo completo Qwen.

## Abrir e comparar

- **Ornith 9B:** https://helioconde.github.io/I.A/luna-ornith-lab/
- **Primeiro jogo completo da Luna, Qwen3-4B:** https://helioconde.github.io/I.A/luna-created/
- **Jogo de referência escrito pelo ChatGPT:** https://helioconde.github.io/I.A/arcade/

## Autoria comprovada

O arquivo `game.js` foi gerado e reparado **somente pelo Ornith 1.5 9B**: inferência no [run 40653494692](https://github.com/HelioConde/I.A/actions/runs/40653494692), duas correções reais no [run 40660720374](https://github.com/HelioConde/I.A/actions/runs/40660720374). O SHA-256 do código reproduzido sem nenhuma modificação é `e6e8f5536d6b633e9b69f9e06b7abc6210ad77dd5e1bef1371b16404ca85e7de`.

O `index.html`, o teste automatizado, o CI e este README são infraestrutura **produzida pelo ChatGPT**, não pelo Ornith. O arquivo `provenance.json` preserva as respostas e as tentativas. A origem foi auditada neste [branch](https://github.com/HelioConde/I.A/tree/luna/ornith9b-playtested-40660720374/experiments/luna-ornith-9b).

## Jogo e limites

Controles: **setas esquerda/direita** para mover, **Espaço** para pular, **Z** para atacar. O Chromium passou nos **4/4 testes reais**: inicialização, movimento/pulo, dano a inimigos e viewport mobile.

Este jogo roda no GitHub Pages como HTML/JS estático, sem banco de dados. É uma demonstração de competência em gerar e reparar um minijogo, **não comprova que o Ornith é superior em jogos completos ou arte**.
