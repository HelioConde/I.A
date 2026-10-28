#!/usr/bin/env python3
"""Final Qwen-authored melee/ranged/magic range balance repair, no assistant game code."""
import repair_luna_game_extra as agent

agent.INPUT=agent.ROOT/"results"/"luna-original-class-ai"
agent.OUTPUT=agent.ROOT/"results"/"luna-original-ranges"
agent.INPUT_RUN=40648093762
agent.INPUT_STATUS="STATIC_REFINED_CANDIDATE"
agent.INPUT_PATCHES_REQUIRED=2
agent.PRIOR_PATCHES=9
agent.PATCH_STAGE="class_combat_range_balance"
agent.TASKS=[{
  "id":"repair_attack_ranges",
  "start":"const heroType = heroSelect.value;",
  "end":"\n  gameLoop();",
  "goal":"Você é Luna corrigindo uma falha de balanceamento grave no seu próprio jogo. "
         "Os três personagens já têm HP diferente, mas você atribuiu attackRange "
         "1, 3 e 0 — alcance em pixels minúsculo, quase impossível para o jogador atacar. "
         "Reescreva SOMENTE o bloco de seleção da classe, começando por "
         "const heroType = heroSelect.value; . Faça um if/else para "
         "'melee', 'ranged', 'magic'. Preserve HP distintos por classe e "
         "atribua explicitamente attackRange com valores em PIXELS: "
         "para melee ENTRE 90 e 130, para ranged ENTRE 140 e 230, "
         "para magic ENTRE 130 e 220. Use três instruções "
         "separadas de attackRange = NUMERO; com números maiores que 80. "
         "NÃO modifique heroSelect.value, wave, enemies ou gameLoop. "
         "Não inclua o gameLoop(), já está no arquivo após este bloco. "
         "Responda APENAS JavaScript do bloco corrigido.",
  "requires":("heroSelect","player.hp","attackRange","melee","ranged","magic"),
  "max_tokens":400
}]

if __name__=="__main__":
    raise SystemExit(agent.main())
