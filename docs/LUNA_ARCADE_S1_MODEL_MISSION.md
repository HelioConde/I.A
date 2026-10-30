# Missão da Luna GameCoder — Action Platformer Original (referência mecânica: Grand Chase S1)

O objetivo é alcançar, por etapas, a **profundidade de controles de um jogo de ação e plataforma clássico**, sem reproduzir seus personagens, áudio, telas, roteiro ou mapas.

## Separação rigorosa de autoria
- O arquivo `mission.json`, o prompt e os testes são infraestrutura do **avaliador**, não código escrito pela Luna.
- **Só** um artefato de JavaScript realmente produzido pelo modelo local GGUF poderá ser creditado à Luna GameCoder.
- Nenhuma implementação criada pelo assistente será apresentada como geração da Luna.
- `M1`: movimento, pulo, plataformas de sentido único e descida por ArrowDown.
- `M2`: combo, dano, inimigos e resposta a ataques.
- `M3`: arenas originais, boss, HP/MP, vitória/derrota.
- O critério de passagem exige execução real no navegador e inspeção visual. Sintaxe válida é apenas a porta inicial.

## Como gerar no GitHub Actions
O workflow `luna-arcade-s1-model.yml` prepara um GGUF real, usa o mesmo gerador existente `tools/benchmark_luna_game_models.py` com `--prompt-file` apontando ao prompt M1, guarda a saída e a proveniência em artefatos. Compilar ou produzir JS sem executar testes de interação significa `STATIC_CANDIDATE`, não jogo completo.

## Observações de hardware/custo
- Rodar modelo de 4B no runner do GitHub usa CPU e pode levar bastante tempo.
- Não usar fontes externas sem verificação de licenças e isolamento de benchmarks.
- Não misturar resultados do roteador Naive Bayes com qualidade da GameCoder.
