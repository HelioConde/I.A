#!/usr/bin/env python3
"""Small deterministic negative-control study for lexical episodic recall.

NO human memory, neural simulation, model training or GGUF inference.
This is only a regression dataset for the experiment's candidate retrieval.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from brain_ssd.chat.episodic import EpisodicMemory

NOTES = {
    "A": "A reunião da equipe aurora será terça no laboratório norte",
    "B": "A reunião da equipe aurora será quinta na biblioteca leste",
    "C": "O protótipo rover azul usa sensores lidar para navegar",
    "D": "O protótipo drone verde usa sensores infravermelho para navegar",
    "E": "A receita de pão integral utiliza farinha de aveia",
    "F": "O inventário do museu está em planilhas na pasta catálogo",
    "G": "O experimento da planta cresce perto da janela da sala",
    "H": "O livro astronomia fica na prateleira superior da biblioteca",
}
POSITIVE = [
    ("equipe aurora laboratório", "A"),
    ("equipe aurora biblioteca", "B"),
    ("rover azul lidar", "C"),
    ("drone verde infravermelho", "D"),
    ("pão integral aveia", "E"),
    ("inventário museu catálogo", "F"),
    ("experimento planta janela", "G"),
    ("livro astronomia prateleira", "H"),
]
NEGATIVE = [
    "temperatura do oceano pacifico",
    "futebol olimpico medalhas",
    "código tributário estadual",
    "qual minha senha bancaria",
    "como consertar motor a diesel",
    "notícias sobre cinema",
    "previsão da economia global",
    "escrever poema sobre amizade",
]
AMBIGUOUS = ("reunião equipe aurora", ("A","B"))


def evaluate() -> dict:
    with tempfile.TemporaryDirectory() as temp:
        store = EpisodicMemory(Path(temp) / "episodes.sqlite3")
        known = {}
        for key, note in NOTES.items():
            known[store.add(note)["id"]] = key
        positive_hits = 0
        outcomes = []
        for cue, expected in POSITIVE:
            matches = [known[m["id"]] for m in store.recall(cue, limit=3)]
            correct = matches[:1] == [expected]
            positive_hits += int(correct)
            outcomes.append({"cue":cue,"expected":expected,"top1":matches[0] if matches else None,"pass":correct})
        false_retrievals = sum(bool(store.recall(cue)) for cue in NEGATIVE)
        ambiguous_matches = {known[m["id"]] for m in store.recall(AMBIGUOUS[0])}
        ambiguity_preserved = set(AMBIGUOUS[1]).issubset(ambiguous_matches)
        return {
            "label": "SYNTHETIC_LEXICAL_NEGATIVE_CONTROL_ONLY",
            "positive_count":len(POSITIVE),
            "top1_positive_correct":positive_hits,
            "top1_positive_accuracy":positive_hits/len(POSITIVE),
            "negative_count":len(NEGATIVE),
            "negative_false_retrievals":false_retrievals,
            "negative_false_rate":false_retrievals/len(NEGATIVE),
            "ambiguous_not_silently_merged":ambiguity_preserved,
            "cases":outcomes,
            "limitations":"Tiny authored lexical set, not user behavior; cannot support cognitive or Qwen quality claims.",
        }


def main() -> int:
    report=evaluate()
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0 if (report["top1_positive_correct"] == len(POSITIVE)
                 and report["negative_false_retrievals"] == 0
                 and report["ambiguous_not_silently_merged"]) else 1


if __name__=="__main__":
    raise SystemExit(main())
