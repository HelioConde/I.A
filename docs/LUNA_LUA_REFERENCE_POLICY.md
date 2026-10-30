# Luna GameCoder — estudo de mecânicas Lua / Grand Chase

## Situação verificada
O usuário informa que a Luna já foi treinada com arquivos originais de Grand Chase escritos em Lua. **Este relato não foi comprovado por pesos, dataset ou logs de treinamento nesta revisão do GitHub.** A busca de código no repositório `HelioConde/I.A` não identificou um corpus Lua de Grand Chase com procedência e autorização verificadas.

## Uso responsável
Não adicionar ou distribuir scripts, mapas, sprites, áudio, personagens ou código proprietário de Grand Chase sem autorização de uso adequada. O objetivo técnico é estudar **mecânicas gerais** e implementar um action-platformer original. Caso os arquivos Lua tenham licença ou autorização, documentar origem, licença, hashes, permissão, versão e filtros de avaliação antes da ingestão. Não declarar que o Qwen3-4B foi fine-tuned a partir deles sem registros de treinamento.

## Novo contrato de avaliação
O arquivo `benchmarks/luna_arcade_s1/lua_mechanics_contract.json` define cinco desafios comportamentais originais: drop-through, pulo, tempo de combos, direção das hitboxes e alternância entre salto e descida. O teste de navegador atual da M1 verifica apenas canvas, snapshot, movimentação, pulo e ausência de erros — **não certifica esses cinco desafios**.

## Resultado recente
Run [41004990898](https://github.com/HelioConde/I.A/actions/runs/41004990898): Qwen3-4B produziu candidato JS original, hash `0f4f3f958f3d25301530329d52680587451ded83700919c77296e0efa6620c87`, e passou nos cinco smoke checks em Chromium. É progresso de M1, não prova de jogo completo ou equivalência com o jogo de referência.
