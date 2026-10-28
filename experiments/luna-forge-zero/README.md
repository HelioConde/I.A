# Luna Forge Zero (pesquisa experimental)

Dois modelos **inicializados do zero**, sem importar pesos pretreinados, para o projeto Luna.

- **Game Planner V0**: interpreta prompts de jogos (2 estilos, 6 mecânicas), modelo neural pequeno e próprio. O gerador Canvas utiliza **templates escritos por humanos**, e não código criado pelo modelo.
- **MiniCoder V0**: Transformer causal experimental treinado em miniexemplos sintéticos de JavaScript e GDScript. Sua saída pode ser inválida; não executar sem verificação.
- **Teacher Lab**: gerador procedimental de desafios de teste, não é ainda um modelo professor independente.

O pacote completo de código executável, pesos e relatórios foi entregue ao usuário como arquivo local nesta conversa. Esta branch inicia a trilha de pesquisa dentro do repositório I.A e não altera a IA principal. Nenhuma habilidade de gerar um jogo inteiro é reivindicada.

## Dados de avaliação

O Planner foi treinado em 9.000 prompts sintéticos; 600 de validação e 600 de teste. O desempenho em teste sintético foi aproximadamente 99,7% em correspondência exata, mas a avaliação manual ajustada foi 9/12: isso **não** comprova generalização real. O MiniCoder é avaliado separadamente por perda de previsão de caractere e testes de sintaxe.

## Metas

1. Tornar treináveis e reprodutíveis os pesos de ambos os modelos.
2. Aprender tarefas de código Godot 4 e Web Canvas licenciadas.
3. Executar JavaScript em Chromium e GDScript em Godot headless.
4. Adicionar professor com currículo, verificador, revisão humana, métricas e rollback.
5. Promover uma versão só depois de testes cegos melhores que a baseline.

**Segurança:** não inserir modelos experimentais no chat Brain-SSD sem avaliação e permissão do usuário.