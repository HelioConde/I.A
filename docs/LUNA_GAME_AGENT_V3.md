# Luna GameDev v3 — geração de JavaScript nativo

O **Luna Arcade S1 de referência** continua disponível no GitHub Pages, jogável com as três classes. Este novo experimento avalia a **própria Luna (Qwen3-4B)** programando um trecho pequeno, sem aproveitar o código do jogo pronto.

## Motivo da nova abordagem

A [avaliação S1 do agente v2](https://github.com/HelioConde/I.A/actions/runs/40628359254) falhou, com 0/1 arquivos aceitos. O 4B respondeu de verdade duas vezes: uma saída JSON inválida e outra com sintaxe JS inválida. Ao inserir um arquivo JavaScript longo dentro de uma string JSON, aumenta-se o risco de falhas de escape e encerramento. O protocolo v3 **muda explicitamente o formato da geração** e, por isso, é um novo benchmark, não correção de pontuação retrospectiva.

## O que o v3 mede

O Qwen3-4B recebe uma descrição específica e responde **apenas JavaScript bruto** que busca `canvas#game`, define `player`, usa as teclas de movimentação e salto, aplica gravidade e desenha em um loop `requestAnimationFrame`.

O verificador:

- Aceita código puro ou um único bloco fenced; rejeita saída vazia, raciocínio exposto e wrappers inválidos.
- Rejeita APIs de rede, importação dinâmica, execuções por `eval`/`Function` e armazenamento local.
- Exige sinais do contrato de jogo e sintaxe JavaScript real via `node --check`.
- Permite uma segunda tentativa com feedback limitado, sem alterar o código do jogo existente.
- Pode salvar **somente um rascunho** de JS sintaticamente aceito em `results/game_agent/draft-s1-movement-v3.js`, com autorização `--save-draft`.
- O GitHub Actions arquiva métricas e, se aprovado, código gerado artificialmente para auditoria; nenhum segredo, história pessoal ou arquivo do PC é utilizado.

**Não executa código gerado**, nem mede a qualidade de movimento no Canvas. Passar no v3 significa apenas que o 4B gerou um módulo JavaScript que cumpre o contrato estático, não que construiu um jogo.

## Execução local

~~~powershell
python tools/run_game_agent_v3_windows.py --model-file Qwen3-4B-Q4_K_M.gguf --attempts 2
~~~

Para salvar um rascunho com aprovação de escrita na pasta de resultados:

~~~powershell
python tools/run_game_agent_v3_windows.py --model-file Qwen3-4B-Q4_K_M.gguf --attempts 2 --save-draft
~~~

O arquivo original do `Luna Arcade S1` não é modificado. O rascunho gerado deve ser revisado e testado num navegador isolado antes de ser incorporado a outro projeto.

A execução de CI opt-in está em [game-agent-v3.yml](../.github/workflows/game-agent-v3.yml). Relatório `results/game_agent/qwen-raw-js-v3.json`. O teste compara um **formato de saída diferente** do anterior, portanto valores de aprovação são diagnósticos e não uma comparação controlada de capacidade geral dos modelos.
