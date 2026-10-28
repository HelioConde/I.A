# Luna: Constelação Perdida — tentativa de jogo 100% escrito pelo Qwen

## Resultado pretendido

O usuário quer **jogar uma versão completa criada pela Luna**, não apenas ver o protótipo do ChatGPT ou patches isolados. A referência do ChatGPT permanece intacta em [Luna Arcade S1](https://helioconde.github.io/I.A/arcade/). A versão de autoria da Luna será isolada em `site/luna-created/` **somente se passar por aprovação e publicação**.

Este documento não afirma que essa versão já existe ou que o modelo aprendeu a desenvolver jogos completos.

## O que é atribuído à Luna

O workflow [Luna Original — Generate Entire Game with Real Qwen](../.github/workflows/luna-complete-game.yml) instala GGUF oficial `Qwen3-4B-Q4_K_M.gguf` e CPU runtime, validando tamanho/SHA. O script [generate_luna_original_game.py](../tools/generate_luna_original_game.py) envia três tarefas ao **modelo real**, sem qualquer template pronto de jogo e sem recuperar/colar o código de referência:

1. `index.html` — interface do jogo, seleção de três classes e Canvas;
2. `styles.css` — visual e responsividade;
3. `game.js` — todo o motor, inputs, três ondas, inimigos, chefe, derrota, vitória, reinício e hook de observação de testes.

O Qwen precisa gerar **os bytes de cada arquivo**; o assistente é autor apenas das instruções, orquestrador, requisitos de teste e infraestrutura. Cada hash SHA-256 consta no artifact `provenance.json` junto de status e tentativas. É proibido substituir arquivos incompletos por código do ChatGPT ou afirmar que output sintaticamente válido significa jogo pronto.

## Portões de qualidade para criar o link público

1. O Qwen precisa produzir **3/3 arquivos** em inferência real; testes unitários impedem respostas falsas.
2. Os arquivos devem passar pelas regras de origem local e segurança: sem CDN, rede externa, execução dinâmica, scripts inline HTML ou referências ao protótipo pronto.
3. O Playwright precisa executar de verdade a seleção de personagem, movimento, pulo, combate, três ondas, chefe, vitória e reinício; também detectar exceções de JS e overflow mobile.
4. A versão com todas as verificações passando é gravada em uma branch de revisão `luna/generated-complete-<run-id>`. **Não vai diretamente para o GitHub Pages**.
5. Um revisor inspeciona código, screenshots e artefatos. Somente depois de aprovação pode ser criada/mesclada uma PR em `main`. O GitHub Pages atual publica apenas o conteúdo de `site/` na `main`.

**Se o modelo falhar, isso é um resultado negativo legítimo; não oferecer um jogo do assistente como se fosse da Luna.**

## Comparação depois de publicada

O jogo da Luna será testável em `https://helioconde.github.io/I.A/luna-created/` e a referência em `https://helioconde.github.io/I.A/arcade/`. O jogador poderá testar ambas e relatar bugs, visual, responsividade, classes, combate e qualidade das fases. Uma versão funcional mas inferior à referência **não atinge ainda** a meta adicional de superar a referência em qualidade.


## Evidência real — primeiro jogo do Qwen3-4B (28/10/2026)

- [Inferência nativa 40636116071](https://github.com/HelioConde/I.A/actions/runs/40636116071): **3/3 arquivos efetivamente gerados pela Luna em uma tentativa cada**: `index.html`, `styles.css`, `game.js`; hash SHA-256 registrado no artifact `luna-original-raw-40636116071`.
- [Auditoria e navegador 40636973421](https://github.com/HelioConde/I.A/actions/runs/40636973421): arquivos originais preservados e validados após normalização CRLF→LF; **2 de 4 testes de navegador aprovados**. Falhas reais: pulo não funcionou e progressão declarou vitória cedo, sem terceira onda completa.
- [Fonte original da própria Luna, em branch de revisão](https://github.com/HelioConde/I.A/tree/luna/generated-review-40636116071/site/luna-created): **é um protótipo incompleto, não publicado como jogo final**. A primeira versão foi criada pela Luna, mas ainda não pode ser chamada de jogável do início ao fim.
- [Tentativa de autoreparo pelo Qwen](https://github.com/HelioConde/I.A/actions/runs/40637251344): nova geração do JavaScript solicitada com os defeitos do Chromium, sem substituição por código do ChatGPT. O resultado requer conferência da execução mais recente.

**Nenhuma versão pública final da Luna foi aprovada nesta primeira avaliação.** A meta exige testes verdes e revisão humana antes de publicação.

## Segunda tentativa — reescrita integral recusada

- [Autorreparo real do Qwen3-4B, run 40637251344](https://github.com/HelioConde/I.A/actions/runs/40637251344): o runtime retornou erro nas **duas solicitações** de gerar novamente todo o `game.js`; não houve nova versão válida. Estado honesto: `INCOMPLETE`.
- O job seguinte foi corretamente bloqueado por ausência do jogo reparado; nenhum arquivo do ChatGPT substituiu a saída do modelo.
- Nova estratégia: [`repair_luna_original_targeted.py`](../tools/repair_luna_original_targeted.py) divide o problema em cinco patches pequenos que devem ser todos produzidos pela inferência real do Qwen e compilar individualmente; um jogo incompleto não será publicado como aprovado.

## Estado atual e próximos passos

A infraestrutura de geração, registro de autoria e teste está implementada, mas **o resultado do modelo será registrado somente depois da execução real**. Se a geração ou os testes falharem, atualizar este documento com execução identificada e causas, mantendo a meta aberta.
