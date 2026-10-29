# Plano técnico separado — próxima fase da Luna GameCoder

## Evidência e limite atual

O MiniCoder desta trilha é um Transformer causal minúsculo, por caractere/ASCII,
com janela de 128 posições. O treino atual gera exemplos sintéticos por oito
templates e separa os textos de treino e validação por sementes, mas o código
declara que as famílias de tarefas se sobrepõem. O currículo original inclui
oito tarefas de treino e quatro holdouts, ainda não treinados segundo seu
manifesto. A queda da perda nos exemplos vistos não é evidência de geração
funcional ou generalização.

## Sequência proposta com gates

1. **Fixar baseline e proveniência.** Preservar cada checkpoint sem sobrescrita;
   gerar manifesto com SHA-256, configuração, dados, tokenizer, seed e métricas.
   Incluir apenas exemplos originais ou licenciados com proveniência registrada.
   Excluir KOM, código comercial e dados sem autorização explícita.
2. **Diversificar dados e splits.** Trocar variações de constantes em templates
   por tarefas originais variadas, com splits por mecânica, estrutura e
   composição. Manter um holdout cego que nunca entre em treino, validação,
   seleção de hiperparâmetros ou revisão de prompts.
3. **Medir tokenizer e contexto.** Comparar tokenização atual, UTF-8/bytes e uma
   tokenização subword reproduzível. Avaliar janelas crescentes em função de
   memória, latência, truncamento e qualidade; escolher com benchmark e não por
   preferência teórica.
4. **Validar sintaxe e comportamento.** Adicionar parsing de Lua e JavaScript
   com versões fixadas e erros reportados. Testar mecânicas originais com
   entradas, invariantes e resultados esperados determinísticos. Não executar
   saídas arbitrárias fora de um runner isolado, sem rede e com limites de
   tempo/recursos.
5. **Avaliar generalização às cegas.** Criar tarefas inéditas e composições não
   vistas; reportar taxa de parsing, testes funcionais aprovados, regressões,
   diversidade de tentativas e custo. Separar métricas de treino, validação e
   teste; não usar apenas loss, correspondência textual ou exemplos vistos.
6. **Promover e reverter.** Salvar cada candidato em diretório/versionamento
   novo. Comparar com a baseline nos mesmos conjuntos fixos, preservar os
   artefatos anteriores e permitir rollback por seleção de manifesto/checkpoint.
   Reprovar promoção se houver regressão no holdout ou quebra de proveniência.
7. **Escalar gradualmente.** Só após gates repetidos, ampliar de funções
   isoladas para pequenos sistemas de jogo 2D; exigir execução funcional
   controlada, correção de bugs e avaliação cega antes de afirmar capacidade de
   criar jogos.

## Critérios mínimos para a próxima iteração

- Nenhum checkpoint V0/V2 atual é sobrescrito ou modificado nesta fase.
- Dados e holdouts têm manifestos de origem e hashes; holdout permanece isolado.
- Parsing de Lua/JavaScript e testes funcionais são gates independentes.
- Relatórios mostram resultados por tarefa inédita e baseline, não só a perda.
- Toda execução de código gerado ocorre em ambiente de teste isolado e limitada.
- Nenhum dado KOM ou código comercial entra no corpus.

## Status da implementação — 2026-10-29

- `luna_codegen_model.py` confirma Transformer causal de caracteres, vocabulário
  128, janela 128, dimensão 64 e duas camadas. Foi adicionada decodificação
  greedy opt-in reproduzível; o modo amostrado anterior permanece como default
  para compatibilidade.
- `train_codegen.py` permanece um gerador de oito famílias sintéticas; mudar
  constantes/seed não elimina vazamento por mecânica. Não foi usado como
  evidência de generalização.
- `github_corpus.py` declara quatro projetos MIT fixados (três treino e um
  holdout), com fontes e commits explícitos. A coleta externa não foi executada
  nesta etapa. O verificador agora revalida o checksum do código normalizado,
  avisos de licença e manifesto de split usando fixtures sintéticas.
- O workspace atual não contém pesos V0/V2 nem um corpus coletado; portanto
  comparação de checkpoints, avaliação de saída do modelo e protótipo atribuído
  à Luna não são reprodutíveis aqui. As métricas V2 fornecidas pelo usuário
  estão arquivadas em `GAMECODER_BASELINE_2026-10-29.json`.
- JavaScript pode ser submetido a `node --check` no avaliador existente, mas
  isso prova apenas sintaxe. Não foi executado código gerado nem foram aprovados
  testes funcionais de movimentação, pulo, colisão, combate, inimigos ou
  habilidades. Esses gates seguem abertos; nenhuma capacidade de criar jogos
  é afirmada.

O comando `sample_codegen.py --deterministic` oferece decodificação greedy para
pesos locais. A ponte Brain-SSD também aceita `--deterministic`; seus pesos
continuam opcionais e fora do workspace.
