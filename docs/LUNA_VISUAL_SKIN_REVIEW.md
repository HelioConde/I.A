# Luna Arcade — visual model-first, sem reescrever o jogo inteiro

## Por que este experimento existe

Playtest real do usuário (30/10/2026): **movimento e combate aprovados; visual reprovado**. As missões que pediram ao Qwen3-4B que recriasse o jogo completo produziram regressões de colisão (o jogador caiu muito abaixo de y=440) ou módulos incompletos (sem contrato de entrada e saída).

## Proposta incremental e verificável

- **Base de jogabilidade:** `site/luna-created/game.js`, código previamente gerado pela Luna Qwen3-4B e preservado byte a byte.
- **Visual novo:** `visual.js`, gerado em inferência REAL da Luna Qwen3-4B, com contrato `window.LunaSkin.draw(ctx,state,time)`.
- **Ponte entre os dois:** `site-tests/luna-visual-overlay-bridge.js`, escrita pelo avaliador; cria canvas transparente sem mudar física, dano, input ou lógica da Luna.
- **Verificação:** `site-tests/check-luna-visual-skin.cjs`, teste real de Chromium que inspeciona pixels, movimentos do jogo original, erros e screenshots.
- **Proveniência:** `visual-provenance.json` com SHA-256 do GGUF, prompt e código produzido; a prova de jogabilidade antiga permanece em `site/luna-created/provenance.json`.

O módulo é exibido em uma **sobreposição visual**, portanto os movimentos originais permanecem intactos. Este modelo foi escolhido para preservar o que o jogador considerou bom. Isso **não constitui fine-tuning dos pesos** do Qwen3-4B. O classificador treinado da Luna Core é separado do modelo gerador.

## Portões de aprovação

1. O módulo deve ser gerado pelo runtime GGUF real, não pelo assistente.
2. Segurança e sintaxe devem passar, sem recursos externos.
3. O navegador deve carregar sem erro, desenhar pixels não vazios e permitir mover o personagem original.
4. Imagens reais de menu e jogo precisam ser inspecionadas por pessoa; passar em teste de pixels **não prova qualidade artística**.
5. Uma nova versão pública deve usar caminho próprio de preview, não substituir o jogo já publicado, até aprovação.

Referências: [issue de feedback #26](https://github.com/HelioConde/I.A/issues/26), [PR #25](https://github.com/HelioConde/I.A/pull/25).
