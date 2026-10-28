#!/usr/bin/env python3
"""Local Code Studio CLI: produce a staged prompt, review, and approved apply."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from brain_ssd.chat.code_studio import ProposalError, parse_proposal, review_proposal, apply_new_files
from brain_ssd.chat.game_dev import GAME_ENGINES, build_game_plan, engine_prompt

BENCHMARK = ROOT / "benchmarks" / "arcade_s1" / "brief.json"


def make_prompt(brief: dict, stage: str, engine: str = "web2d") -> str:
    if not isinstance(brief, dict) or brief.get("benchmark_version") != 1:
        raise ProposalError("Benchmark ausente ou inválido.")
    stages = brief.get("stages")
    if not isinstance(stages, list):
        raise ProposalError("Nenhuma etapa definida.")
    stage_record = next((s for s in stages if isinstance(s, dict) and s.get("id") == stage), None)
    if stage_record is None:
        raise ProposalError("Etapa não encontrada.")
    return (
        engine_prompt(engine)
        + "Você é a Luna no modo Code Studio. Construa uma implementação ORIGINAL "
        "de jogo de ação/plataforma, sem copiar sprites, marcas, músicas ou código de terceiros.\n"
        "Responda com UM OBJETO JSON COMPLETO e nada fora dele; formato estrito:\n"
        '{"version":1,"goal":"objetivo concreto","files":[{"path":"index.html","content":"..."}]}\n'
        "Crie no máximo 20 arquivos, 48 KB cada, 250 KB total. Não use dependências externas, "
        "CDNs, eval, código remoto, telemetria, login, rede ou comandos de shell. "
        "Siga o contrato do motor selecionado, com foco em boa jogabilidade e estrutura modular. "
        "Se não couber no limite de saída do modelo, entregue uma etapa menor, válida e testável; "
        "nunca feche JSON incompleto ou finja que executou testes. "
        "O jogo NÃO será instalado nem executado automaticamente.\n"
        "Etapa atual: " + str(stage_record.get("title", "")) + "\n"
        "Critérios: " + json.dumps(stage_record.get("requirements", []), ensure_ascii=False) + "\n"
        "Requisitos transversais: " +
        json.dumps(brief.get("cross_cutting", []), ensure_ascii=False) + "\n"
        "Use apenas arte original; não inclua conteúdo protegido de Grand Chase.\n"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Luna Code Studio (opt-in, no auto-exec)")
    sub = parser.add_subparsers(dest="action", required=True)
    prompt = sub.add_parser("prompt", help="Produce a prompt for a benchmark milestone")
    prompt.add_argument("--stage", required=True)
    prompt.add_argument("--engine", choices=tuple(GAME_ENGINES), default="web2d")
    plan = sub.add_parser("plan", help="Print a game-development milestone plan (no files written)")
    plan.add_argument("--engine", choices=tuple(GAME_ENGINES), default="web2d")
    sub.add_parser("engines", help="List available engine specializations and QA limits")
    review = sub.add_parser("review", help="Review JSON proposal without writing files")
    review.add_argument("proposal", type=Path)
    apply = sub.add_parser("apply", help="Write NEW files only after explicit approval")
    apply.add_argument("proposal", type=Path)
    apply.add_argument("--workspace", type=Path, required=True)
    apply.add_argument("--approve", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.action == "engines":
            print(json.dumps(GAME_ENGINES, ensure_ascii=False, indent=2))
            return 0
        if args.action == "plan":
            brief = json.loads(BENCHMARK.read_text(encoding="utf-8"))
            print(json.dumps(build_game_plan(brief, args.engine), ensure_ascii=False, indent=2))
            return 0
        if args.action == "prompt":
            brief = json.loads(BENCHMARK.read_text(encoding="utf-8"))
            print(make_prompt(brief, args.stage, engine=args.engine))
            return 0
        data = parse_proposal(args.proposal.read_text(encoding="utf-8"))
        report = review_proposal(data)
        if args.action == "review":
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0 if report["status"] == "READY_FOR_HUMAN_REVIEW" else 1
        if not args.approve:
            print("Revisão obrigatória. Execute novamente com --approve, apenas após conferir os arquivos.", file=sys.stderr)
            return 2
        paths = apply_new_files(data, args.workspace.absolute(), approved=True)
        print(json.dumps({"status": "CREATED_NEW_FILES", "paths": paths,
                          "warning": "Arquivos NÃO executados, NÃO testados no navegador."},
                         ensure_ascii=False, indent=2))
        return 0
    except (ProposalError, OSError, ValueError, PermissionError) as exc:
        print(f"Code Studio: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
