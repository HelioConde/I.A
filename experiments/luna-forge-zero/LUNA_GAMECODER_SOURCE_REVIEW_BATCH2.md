# Luna GameCoder — segunda rodada de curadoria GitHub (2026-10-30)

Esta rodada complementa `LUNA_GAMECODER_SOURCE_REVIEW.json`, **sem fazer download de
codigo para treinamento e sem executar qualquer treinamento**.

## Maiores descobertas

1. **[OpenGame](https://github.com/leigest519/OpenGame)** — licenca Apache-2.0
   inspecionada; arquitetura de agente para criar jogos web de ponta a ponta.
   Boa referencia para planejamento → codigo → preview → testes. Os arquivos
   de demonstracao fazem referencia a franquias conhecidas e NAO sao dados
   aprovados, nao devem ser importados para os jogos originais da Luna.
2. **[Claude Code Game Studios](https://github.com/Donchitos/Claude-Code-Game-Studios)**
   — LICENSE MIT inspecionada; organizacao de agentes, QA, papeis e workflows.
   Usar os principios para Luna Core/QA/GameCoder, sem impor uso de Claude.
3. **[Flatris](https://github.com/ovidiuch/flatris)** — LICENSE MIT inspecionada;
   logica de jogo web, estado e componentes JS. Candidato futuro a codigo-only,
   separado por projeto entre treino e avaliacao.
4. **[CraftyJS](https://github.com/craftyjs/Crafty)** — LICENSE MIT inspecionada;
   input, movimento, plataformas e colisoes em JS. Candidato futuro apos
   revisar arquivos de codigo e licencas incorporadas.
5. **[DeepLearningFlappyBird](https://github.com/yenchenlin/DeepLearningFlappyBird)**
   — LICENSE MIT inspecionada; exemplo de aprendizado por reforco de politicas
   do agente jogador. **Nao equivale** a aprender a gerar codigo de jogos.

Outras fontes com licenca explicitamente inspecionada: 
[GameFramework Unity/C#](https://github.com/EllanJiang/GameFramework) (MIT),
[GameZone](https://github.com/kunjgit/GameZone) (Apache-2.0),
[CharlesPikachu/Games](https://github.com/CharlesPikachu/Games) (Apache-2.0).
Colecoes extensas ou com contribuidores numerosos precisam de revisao
arquivo a arquivo para verificar avisos de terceiros.

## Fontes nao importadas

Metadados do GitHub foram consultados em dezenas de repositorios. Alguns
mostram licencas customizadas (`NOASSERTION`), outras licencas como AGPL,
e alguns nao exibem licenca detectavel. Essas fontes foram preservadas como
referencias ou pendencias; nunca se pode concluir que todos os arquivos,
assets, livros e demonstracoes sao reutilizaveis apenas porque o repositorio
e publico.

## Regra operacional

- Apenas codigo-fonte com direitos verificados e notices preservados.
- Arquivos e commits fixados; nenhum `main` dinamico em um corpus.
- Repositorios reservados para holdout nao podem gerar exemplos de treino,
  correcoes guiadas ou selecao de hiperparametros.
- Sem executaveis, assets, jogos comerciais, dados privados, pesos de terceiros
  ou material gerado que contenha personagens/franquias sem autorizacao.
- Dados importados para treinamento devem ter aprovacao adicional por arquivo.
- O coletor atual `github_corpus.py` continua restrito a codigos MIT/GDScript
  e JS/TS/TSX. A adicao de licencas Apache ou outras linguagens exige alteracoes
  deliberadas e verificadas.

## Rumo ao treinamento de verdade

Primeiro iremos usar as ideias de planejamento/QA de OpenGame e Game Studios
para um **ciclo de autocorrecao rastreavel**, medindo novamente a falha conhecida
de 1/9 no Qwen original. Depois, com a curadoria de licencas concluida,
podemos treinar uma nova MiniCoder propria em um conjunto de exemplos
originais ou criteriosamente aprovados. O pipeline nao pode atribuir a MiniCoder
codigo gerado por modelos pretreinados.
