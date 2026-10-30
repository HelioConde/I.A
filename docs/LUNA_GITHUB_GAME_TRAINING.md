# Luna GameCoder — estudo com projetos externos do GitHub

**Experimento de 28/10/2026.** O usuário solicitou utilizar repositórios de outros desenvolvedores, não apenas os próprios. Este ciclo utiliza **apenas código externo** em sua base, sem qualquer projeto HelioConde, e mantém a IA Brain-SSD principal intacta.

## Fontes externas aprovadas

As versões são imutáveis e referenciadas por SHA de commit:

| Repositório | Commit | Licença do código | Uso |
| --- | --- | --- | --- |
| [godotengine/godot-demo-projects](https://github.com/godotengine/godot-demo-projects) | b761b4cd5718a7118f2c95eb55f181d0a5f004f1 | MIT (LICENSE.md) | train |
| [statico/godot-roguelike-example](https://github.com/statico/godot-roguelike-example) | 5fa12fd3206df9ce42284cf7aab6b41b69b7fca6 | MIT (LICENSE) | train |
| [phaserjs/examples](https://github.com/phaserjs/examples) | eb87db8355861ae222d0c5cd13aae54c2d7d72ae | MIT para código (README.md; assets excluídos) | train |
| [stm1978/retro-platformer](https://github.com/stm1978/retro-platformer) | 9835295888c7cb8afa795ca2a31707a65167c2ea | MIT (LICENSE) | holdout |

O coletor usa whitelist de arquivos \`.gd\` e \`.js\`, verifica conteúdo textual, confirma evidências de licença, limita a coleta a ~1.5 MB, registra origem, SHA-256, projeto/commit/arquivo/split, e produz cópia das licenças em \`LICENSE_NOTICES.json\`. Não executa código baixado, não coleta sprites, sons, arquivos ZIP ou binários.

## Fluxo completo

\`\`\`powershell
cd C:\Users\helio\Documents\I.A\experiments\luna-forge-zero
py github_corpus.py collect --out external_data
py github_corpus.py verify --out external_data
py -m pip install torch --index-url https://download.pytorch.org/whl/cpu
py train_github.py --data external_data --out external_data/model_candidate --steps 180 --batch 12 --threads 2
\`\`\`

As saídas sob \`external_data/\` devem permanecer locais, fora do Git; os arquivos de licença acompanham quaisquer distribuições de trechos. Pesos binários novos ficam no artifact do GitHub Actions. Não substituem \`checkpoints/luna-minicoder-zero-v0\`, o chat principal ou o Qwen.

## Execução observada

- [Run real do GitHub Actions — 40684669748](https://github.com/HelioConde/I.A/actions/runs/40684669748): **SUCCESS**; coleta, teste de licença, instalação CPU PyTorch, atualização efetiva dos parâmetros, checagem do SHA e upload do checkpoint.
- [Artifact: luna-github-game-corpus-and-model](https://github.com/HelioConde/I.A/actions/runs/40684669748/artifacts/12813823089).
- 4 repositórios externos distintos; 25 arquivos (19 treinamento; 6 holdout integralmente de outro repositório); 136.447 bytes de código.
- Transformer causal com **116.480 parâmetros**, inicializado do zero (sem pesos pretreinados).
- 180 etapas de atualização com CPU. Loss de previsão de próximo caractere em repositório holdout: **35.61765 antes → 3.376007 depois**.
- Nenhum resultado de sintaxe/execução do código gerado foi medido neste experimento. NÃO reivindicar desenvolvimento de jogos, aprendizado generalizado ou ganho de Brain-SSD na memória física.
- \`promotion_allowed=false\`: novo modelo é candidato experimental; qualquer promoção requer comparação independente em tarefas de jogo reais.

## Próxima etapa

1. Expandir fontes externas de autores independentes com licenças comprovadas, sem duplicar forks ou espelhos.
2. Criar pares instrução→código a partir de testes verificáveis e diffs revisados, em vez de somente previsão de caracteres.
3. Executar casos de Godot headless e Chromium/Playwright com critérios de movimento, colisão, inimigos e transição de fases.
4. Medir baseline vs candidato em código jogável, latência, consumo de RAM e contexto.
5. Registrar as fontes no Brain-SSD em páginas recuperáveis, com limite de ativação, integridade e evidências; não confundir RAG com treinamento dos pesos.
6. Somente após aprovação humana promover checkpoint, mantendo rollback.


## Avaliação de geração após treinar (segunda execução)

- [Run com verificação de sintaxe — 40685078383](https://github.com/HelioConde/I.A/actions/runs/40685078383): SUCCESS na coleta, treinamento, verificação de checkpoint, avaliação e artefatos.
- [Artifact com pesos, relatório e avaliação](https://github.com/HelioConde/I.A/actions/runs/40685078383/artifacts/12813848999).
- Cinco amostras JavaScript novas produzidas pelo modelo, nenhuma passou em node --check (0/5).
- Nenhum teste de gameplay foi executado; é inadequado promover o modelo.
- O próximo ciclo deve aprender com pares enunciado→função/teste e usar avaliações reais.
