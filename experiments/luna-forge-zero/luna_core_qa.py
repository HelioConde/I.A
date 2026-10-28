"""Luna Core's bounded STATIC rubric for original 2D horizontal movement.

Not a compiler, interpreter or proof of correctness. Does not execute code,
write source files, transmit data, or access commercial game files.
All criteria are heuristics with conservative explanations.
"""
from __future__ import annotations
import re

MOVEMENT_WORDS=("horizontal","movimento","mover","movimenta","velocity","move","velocidade","atrito","friction")

def is_movement_task(task: str) -> bool:
    low=task.lower()
    return any(w in low for w in MOVEMENT_WORDS)

def assess_horizontal_movement(code: str) -> dict:
    """Return static indicators, never claim dynamic gameplay test success."""
    s=code or ""
    # Broad identifiers used in browser games. Do not confuse a constant
    # acceleration parameter with movement controlled by player input.
    has_input=bool(re.search(
        r"\b(?:axis|direction|inputx|inputaxis|moveinput|horizontalinput|"
        r"leftpressed|rightpressed|moveleft|moveright)\b",s,re.I)
        or (re.search(r"\b(?:left|arrowleft)\b",s,re.I) and re.search(r"\b(?:right|arrowright)\b",s,re.I)))
    has_time=bool(re.search(r"\b(?:dt|deltatime|delta|elapsed|timeStep|seconds)\b",s,re.I))
    delta_position=bool(re.search(
        r"(?:\b(?:x|positionX|posX|velocityX|vx|speedX)\b\s*[\+\-]?=.{0,100}"
        r"\b(?:dt|deltatime|delta|elapsed|timeStep)\b)|"
        r"(?:\b(?:dt|deltatime|delta|elapsed|timeStep)\b.{0,100}\b(?:velocityX|vx|speedX)\b)",
        s,re.I|re.S))
    # Negative max clamp by Math.max(-maxSpeed,...) or explicit abs+sign.
    symmetric=bool(
        re.search(r"Math\s*\.\s*max\s*\(\s*-\s*(?:maxSpeed|maxVelocity|speedLimit|MAX_SPEED)",s,re.I)
        and re.search(r"Math\s*\.\s*min\s*\(\s*(?:maxSpeed|maxVelocity|speedLimit|MAX_SPEED)",s,re.I)
        or re.search(r"Math\s*\.\s*abs\s*\([^)]*\).{0,150}(?:maxSpeed|maxVelocity|speedLimit|MAX_SPEED)",s,re.I|re.S)
        or re.search(r"Math\s*\.\s*sign\s*\([^)]*\).{0,150}(?:maxSpeed|maxVelocity|speedLimit|MAX_SPEED)",s,re.I|re.S)
    )
    # Multiplying velocity by constant friction on EVERY frame is not
    # framerate independent. This is intentionally stricter than syntax.
    frame_friction=bool(re.search(
        r"(?:velocityX|vx|speedX)\s*\*=\s*(?:friction|drag|damping)\s*;",s,re.I)
        or re.search(r"(?:velocityX|vx|speedX)\s*=\s*(?:velocityX|vx|speedX)\s*\*\s*(?:friction|drag|damping)\b",s,re.I))
    dt_friction=bool(re.search(
        r"(?:friction|drag|damping|deceleration)\s*\*\s*(?:dt|deltaTime|delta|elapsed|timeStep)\b|"
        r"(?:dt|deltaTime|delta|elapsed|timeStep)\s*\*\s*(?:friction|drag|damping|deceleration)\b|"
        r"Math\s*\.\s*(?:exp|pow)\s*\([^;]*\b(?:dt|deltaTime|delta|elapsed|timeStep)\b",
        s,re.I))
    neutral=bool(re.search(
        r"(?:\b(?:axis|direction|inputX|inputAxis|moveInput)\s*===?\s*0\b)|"
        r"(?:\b(?:axis|direction|inputX|inputAxis|moveInput)\s*!==?\s*0\b)|"
        r"(?:\b(?:axis|direction|inputX|inputAxis|moveInput)\s*\?\s*)",
        s,re.I))
    checks={
      "player_direction_input":has_input,
      "delta_time_used_in_position":has_time and delta_position,
      "symmetric_max_speed":symmetric,
      "frame_rate_independent_friction":dt_friction and not frame_friction,
      "neutral_input_handling":neutral,
    }
    descriptions={
      "player_direction_input":"Receber e utilizar entrada direcional esquerda/direita; uma aceleração constante positiva não serve",
      "delta_time_used_in_position":"Integrar a posição usando a velocidade e deltaTime",
      "symmetric_max_speed":"Limitar velocidade positiva e negativa ao máximo em módulo",
      "frame_rate_independent_friction":"Escalonar atrito/desaceleração por deltaTime, não multiplicar por constante a cada quadro",
      "neutral_input_handling":"Quando o jogador soltar o comando, desacelerar até parar",
    }
    missing=[descriptions[k] for k,v in checks.items() if not v]
    return {
      "method":"static_heuristic_indicators_only",
      "indicators":checks,
      "indicators_detected":sum(checks.values()),
      "indicators_total":len(checks),
      "issues_to_review":missing,
      "generated_code_executed":False,
      "behavior_verified":False,
      "quality_approved":False,
      "disclaimer":"Regex indicators can miss valid implementations or accept incorrect ones. Require isolated functional tests and human review.",
    }

def review(task: str, code: str) -> dict:
    if is_movement_task(task):
        return {"task_type":"horizontal_movement","rubric":assess_horizontal_movement(code)}
    return {"task_type":"general","rubric":{
        "method":"not_available_for_task","quality_approved":False,
        "behavior_verified":False,"generated_code_executed":False,
        "issues_to_review":["Implementar uma suite de testes específica antes de considerar o código correto."]
    }}
