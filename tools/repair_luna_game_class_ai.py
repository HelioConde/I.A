#!/usr/bin/env python3
"""Third independently attributable game repair — Qwen-created classes and enemy AI."""
from pathlib import Path
import repair_luna_game_extra as agent

agent.INPUT=agent.ROOT/"results"/"luna-original-refined"
agent.OUTPUT=agent.ROOT/"results"/"luna-original-class-ai"
agent.INPUT_RUN=40647732624
agent.INPUT_STATUS="STATIC_REFINED_CANDIDATE"
agent.INPUT_PATCHES_REQUIRED=2
agent.PRIOR_PATCHES=7
agent.PATCH_STAGE="classes_and_enemy_behavior"
agent.TASKS=[
  {
    "id":"respect_selected_class",
    "start":"  document.getElementById('hero').value = 'melee';",
    "end":"\n  gameLoop();",
    "goal":"Bug real: após clicar Iniciar o código FORÇA heroSelect=melee, "
           "ignorando a classe escolhida. Você deve SUBSTITUIR esta linha por 3 "
           "possibilidades usando const heroType = heroSelect.value, "
           "if/else com os três valores 'melee', 'ranged' e 'magic'. "
           "Atribua a player.hp valores DIFERENTES para cada uma das três classes "
           "e, se desejar, ajuste attackRange. NÃO mude heroSelect.value. "
           "O código precisa conter literalmente player.hp, heroSelect, melee, ranged, magic. "
           "Não inclua gameLoop(), ele já vem logo após este trecho. "
           "Responda SOMENTE as instruções JS substitutas.",
    "requires":("heroSelect","player.hp","melee","ranged","magic"),
    "max_tokens":330,
  },
  {
    "id":"keep_enemies_in_arena",
    "start":"    // Enemy movement\n",
    "end":"    // Check for enemy collision\n",
    "goal":"No seu jogo, cada inimigo avançava sempre para direita e, ao sair "
           "da tela, era removido e o jogo declarava vitória SEM derrotar o chefe. "
           "Reescreva só o bloco Enemy movement, dentro do gameLoop, para "
           "percorrer o array enemies, aproximar enemy.x de player.x devagar "
           "por Math.sign(player.x - enemy.x) e limitar x entre 0 e 940. "
           "NÃO use enemies.splice, enemies.filter, pop, shift, nem retire inimigos "
           "do array aqui. A morte verdadeira será verificada só pelo dano no combate. "
           "Retorne SOMENTE JavaScript do bloco, sem o marcador Check for enemy collision.",
    "requires":("enemies","player","x"),
    "max_tokens":375,
  },
]

if __name__=="__main__":
    raise SystemExit(agent.main())
