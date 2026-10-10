#!/usr/bin/env python3
"""Manual offline episodic review queue. Nothing runs without user command."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from brain_ssd.chat.episodic import EpisodicMemory,default_episodic_path
from brain_ssd.chat.consolidation import ConsolidationQueue


def main() -> int:
    parser=argparse.ArgumentParser(description="Revisão manual de consolidação, sem IA externa.")
    base=default_episodic_path()
    parser.add_argument("--episodes",type=Path,default=base)
    parser.add_argument("--reviews",type=Path,default=base.with_name("consolidation-review.sqlite3"))
    actions=parser.add_mutually_exclusive_group()
    actions.add_argument("--propose",nargs="+",metavar="EPISODE_ID",help="Propor 2 a 6 IDs confirmados")
    actions.add_argument("--approve",metavar="DRAFT_ID",help="Aprovar um rascunho já criado")
    actions.add_argument("--reject",metavar="DRAFT_ID")
    actions.add_argument("--revoke",metavar="REVIEWED_ID")
    actions.add_argument("--delete",metavar="DRAFT_ID")
    parser.add_argument("--summary",help="Resumo escrito pelo usuário; usado somente com --approve")
    args=parser.parse_args()
    try:
        # Default lists drafts; explicit mutations are required.
        if not args.episodes.is_file():
            print("Nenhum banco de notas episódicas encontrado; crie notas no chat com opt-in.")
            return 2
        memory=EpisodicMemory(args.episodes)
        reviews=ConsolidationQueue(args.reviews,memory)
        if args.propose:
            result=reviews.create_draft(args.propose)
        elif args.approve:
            result=reviews.review(args.approve,"approve",args.summary)
        elif args.reject:
            result=reviews.review(args.reject,"reject")
        elif args.revoke:
            result={"revoked":reviews.revoke(args.revoke)}
        elif args.delete:
            result={"deleted":reviews.delete(args.delete)}
        else:
            result={"mode":"READ_ONLY_PREVIEW","candidates":reviews.list(),
                    "note":"Aprovação exige --approve ID --summary TEXTO; nenhum conteúdo é enviado ao Qwen."}
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 0
    except (ValueError,OSError) as error:
        print(f"Falha de revisão: {error}",file=sys.stderr)
        return 1


if __name__=="__main__":
    raise SystemExit(main())
