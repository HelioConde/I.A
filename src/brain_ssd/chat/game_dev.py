"""Luna GameDev specialization: engine-aware, evidence-driven game planning.

This does not train model weights, edit game files or pretend to run a game.
The frozen Brain-SSD research pipeline is outside this module's scope.
"""
from __future__ import annotations

from typing import Any

GAME_ENGINES: dict[str, dict[str, Any]] = {
    "web2d": {
        "label": "Web 2D — HTML5 Canvas",
        "status": "PROMPT_AND_ACCEPTANCE_DEFINED",
        "entrypoint": "index.html",
        "source_files": ("index.html", "styles.css", "src/game.js"),
        "language": "JavaScript + HTML + CSS",
        "tests": "Playwright against a running local game and real engine state",
        "publish": "GitHub Pages (single-player/offline; no database)",
        "instructions": (
            "Use HTML5 Canvas, JavaScript modules, HTML and CSS without CDNs. "
            "The real simulation owns player and enemy state; expose only a read-only "
            "window.__LUNA_GAME_QA__.snapshot() adapter for Playwright. "
            "Keyboard gameplay must work on a localhost static server; prevent page "
            "scroll from consuming gameplay keys while the game is active. "
            "Do not claim mobile touch controls or multiplayer unless implemented."
        ),
    },
    "godot4": {
        "label": "Godot 4 — 2D",
        "status": "PROMPT_AND_ACCEPTANCE_DEFINED",
        "entrypoint": "project.godot",
        "source_files": ("project.godot", "scenes/main.tscn", "scripts/player.gd"),
        "language": "GDScript 2.0 and Godot 4 scene resources",
        "tests": "Godot 4 headless parse/import and actual interactive playtest on a local editor",
        "publish": "Export via Godot after user approval; no automated export in Code Studio",
        "instructions": (
            "Produce only Godot 4 compatible GDScript 2.0, .tscn/.tres text resources "
            "and project.godot. Use CharacterBody2D, CanvasLayer, InputMap, "
            "collision layers/masks and state machines where appropriate. "
            "Every referenced resource path must correspond to a proposed existing "
            "file or an explicitly documented later milestone. "
            "Never include editor plugins, @tool scripts, or autoload executable "
            "operations in the initial milestone. "
            "Use godot --headless --path PROJECT --editor --quit for parse/import QA "
            "only when installed and authorized; it does not prove gameplay."
        ),
    },
}

WORKFLOW_STEPS = (
    ("design", "Definir experiência jogável, regras, classes e estética original"),
    ("architecture", "Definir cenas/sistemas, contratos, dependências e testes"),
    ("implementation", "Produzir uma alteração pequena e revisável"),
    ("validation", "Executar o jogo real, coletar falhas e screenshots"),
    ("repair", "Corrigir regressões e repetir o teste"),
    ("review", "Solicitar aprovação humana antes de gravar, exportar ou publicar"),
)


def engine_profile(engine: str) -> dict[str, Any]:
    if not isinstance(engine, str) or engine not in GAME_ENGINES:
        raise ValueError("Motor não reconhecido. Escolha web2d ou godot4.")
    return GAME_ENGINES[engine].copy()


def engine_prompt(engine: str) -> str:
    settings = engine_profile(engine)
    return (
        f"Motor escolhido: {settings['label']}.\n"
        f"Linguagem: {settings['language']}.\n"
        f"Arquivos iniciais típicos: {', '.join(settings['source_files'])}.\n"
        f"Entrada do jogo: {settings['entrypoint']}.\n"
        f"Validação esperada: {settings['tests']}.\n"
        f"Publicação possível: {settings['publish']}.\n"
        "Restrições técnicas: " + settings["instructions"] + "\n"
        "Atue como equipe de desenvolvimento de jogos em pequenos passos: "
        "game designer, arquiteto, programador, testador e revisor. "
        "Priorize primeiro o loop jogável sobre telas decorativas. "
        "Não alegue ter executado o jogo, compilado o projeto, observado imagens "
        "ou atingido FPS sem evidência do processo e logs reais.\n"
    )


def build_game_plan(brief: dict[str, Any], engine: str) -> dict[str, Any]:
    """Reproducible plan: no LLM needed and no fabricated completion signals."""
    profile = engine_profile(engine)
    if not isinstance(brief, dict) or brief.get("benchmark_version") != 1:
        raise ValueError("Benchmark inválido.")
    stages = brief.get("stages")
    if not isinstance(stages, list) or not stages:
        raise ValueError("Benchmark sem etapas.")
    stage_ids: set[str] = set()
    planned = []
    for stage in stages:
        if not isinstance(stage, dict):
            raise ValueError("Etapa inválida.")
        ident, title, requirements = stage.get("id"), stage.get("title"), stage.get("requirements")
        if (not isinstance(ident, str) or not ident or ident in stage_ids
                or not isinstance(title, str) or not title
                or not isinstance(requirements, list) or not requirements
                or not all(isinstance(value, str) and value.strip() for value in requirements)):
            raise ValueError("Etapas duplicadas ou sem critérios de aceitação.")
        stage_ids.add(ident)
        planned.append({
            "id": ident, "title": title, "requirements": list(requirements),
            "status": "NOT_STARTED", "evidence": [],
        })
    gate = brief.get("graduation", {})
    if not isinstance(gate, dict) or not isinstance(gate.get("hard_gates"), list):
        raise ValueError("Critérios de liberação incompletos.")
    scoring = brief.get("scoring")
    if not isinstance(scoring, dict) or sum(
        v for v in scoring.values() if type(v) is int
    ) != 100 or any(type(v) is not int or v < 0 for v in scoring.values()):
        raise ValueError("A pontuação deve somar 100 pontos.")
    return {
        "schema_version": 1,
        "project": "Luna Arcade S1",
        "benchmark_id": brief.get("id", "unknown"),
        "engine": engine,
        "engine_label": profile["label"],
        "status": "PLANNED_NOT_BUILT",
        "stages": planned,
        "workflow_steps": [{"id": key, "goal": value} for key, value in WORKFLOW_STEPS],
        "score": None,
        "tests_executed": False,
        "gameplay_verified": False,
        "release_gates": [{"criterion": label, "status": "NOT_TESTED"}
                          for label in gate["hard_gates"]],
        "note": "Plano e rubrica, não um jogo gerado ou teste executado.",
    }
