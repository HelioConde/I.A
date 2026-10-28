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
agent.TASKS=[
  {
    "id":"repair_range_melee",
    "start":"attackRange = 1;",
    "end":None,
    "allow_statement":True,
    "goal":"Você é Luna, autor do game.js. O espadachim tem attackRange = 1; "
           "um alcance de 1 pixel, impossível de usar. Retorne APENAS UMA instrução "
           "JavaScript completa, começando com attackRange =, atribuindo "
           "um NUMERO INTEIRO entre 90 e 130 pixels para o melee. "
           "Não escreva if, else, bloco, JSON, markdown nem texto.",
    "requires":("attackRange",),
    "max_tokens":70,
  },
  {
    "id":"repair_range_ranged",
    "start":"attackRange = 3;",
    "end":None,
    "allow_statement":True,
    "goal":"Você é Luna, autor do game.js. A arqueira tem attackRange = 3; "
           "um alcance inútil. Retorne APENAS UMA instrução JS completa, "
           "começando com attackRange = e atribuindo NUMERO INTEIRO "
           "entre 140 e 230 pixels para ranged. Não escreva outros trechos.",
    "requires":("attackRange",),
    "max_tokens":70,
  },
  {
    "id":"repair_range_magic",
    "start":"attackRange = 0;",
    "end":None,
    "allow_statement":True,
    "goal":"Você é Luna, autor do game.js. O mago tem attackRange = 0; "
           "seus feitiços não alcançam ninguém. Retorne APENAS UMA instrução "
           "JavaScript completa começando com attackRange = e com NUMERO "
           "INTEIRO entre 130 e 220 pixels. Nada de blocos ou explicações.",
    "requires":("attackRange",),
    "max_tokens":70,
  }
]

if __name__=="__main__":
    raise SystemExit(agent.main())
