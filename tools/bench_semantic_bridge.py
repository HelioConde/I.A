#!/usr/bin/env python3
"""Opt-in narrow-PTBR-alias A/B regression, no Qwen or personal data."""
from __future__ import annotations
import json
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from brain_ssd.chat.episodic import EpisodicMemory
from brain_ssd.chat.semantic_bridge import BRIDGE_VERSION

NOTES = {
    "dog_meet": "A reunião com cachorro aconteceu sábado na praça",
    "computer_fix": "O conserto do computador terminou ontem na oficina",
    "car_picture": "Fotografia do automóvel guardada na garagem",
    "phone_bike": "Celular e bicicleta ficam na caixa grande",
    "medicine_school": "Medicamento entregue na escola da avenida",
    "dog_medicine": "Remédio para cachorro entregue no domingo",
}
POSITIVE = [
    ("encontro cão", "dog_meet"),
    ("reunião cachorro", "dog_meet"),
    ("reparo notebook", "computer_fix"),
    ("conserto computador", "computer_fix"),
    ("foto carro", "car_picture"),
    ("fotografia automóvel", "car_picture"),
    ("smartphone bike", "phone_bike"),
    ("celular bicicleta", "phone_bike"),
    ("remédio colégio", "medicine_school"),
    ("medicamento escola", "medicine_school"),
    ("medicamento cão", "dog_medicine"),
    ("remédio cachorro", "dog_medicine"),
]
NEGATIVE = [
    "encontro automóvel", "notebook fotografia", "celular remédio",
    "bicicleta cachorro", "carro escola", "medicamento oficina",
    "conserto código", "smartphone cachorro", "encontro noturno",
    "bike automóvel", "remédio computador", "fotografia reunião",
]


def evaluate() -> dict:
    with tempfile.TemporaryDirectory(prefix="brainssd-alias-ab-") as temp:
        store=EpisodicMemory(Path(temp)/"episodic.sqlite3")
        names={store.add(text)["id"]:key for key,text in NOTES.items()}
        baseline_correct=0
        aliases_correct=0
        alias_only_correct=0
        failures=[]
        for question, expected in POSITIVE:
            base=store.recall(question)
            extra=store.recall(question, experimental_aliases=True)
            base_name=names[base[0]["id"]] if base else None
            extra_name=names[extra[0]["id"]] if extra else None
            baseline_correct += int(base_name == expected)
            aliases_correct += int(extra_name == expected)
            alias_only_correct += int(base_name != expected and extra_name == expected)
            if extra_name != expected:
                failures.append({"type":"top1","expected":expected,"got":extra_name,"question":question})
        baseline_false=0
        alias_false=0
        for question in NEGATIVE:
            baseline_false += bool(store.recall(question))
            extra=store.recall(question, experimental_aliases=True)
            alias_false += bool(extra)
            if extra:
                failures.append({"type":"false_recall","question":question,"count":len(extra)})
        # One alias-only word must not unlock an unrelated note.
        one_word=store.recall("cão",experimental_aliases=True)
        if one_word:
            failures.append({"type":"single_word_alias_not_abstained"})
        # The index must behave consistently after reopening and deletion.
        reopened=EpisodicMemory(store.path)
        dog_id=next(ident for ident,name in names.items() if name=="dog_meet")
        before=reopened.recall("encontro cão",experimental_aliases=True)
        reopened.delete(dog_id)
        after=reopened.recall("encontro cão",experimental_aliases=True)
        deletion_ok=bool(before) and all(item["id"]!=dog_id for item in after)
        if not deletion_ok:
            failures.append({"type":"deletion_after_reopen"})
        return {
            "classification":"EXPLICIT_ALIAS_EXPERIMENT_SYNTHETIC_ONLY",
            "bridge_version":BRIDGE_VERSION,
            "positive_queries":len(POSITIVE),
            "lexical_baseline_top1":baseline_correct,
            "alias_top1":aliases_correct,
            "new_alias_only_hits":alias_only_correct,
            "negative_queries":len(NEGATIVE),
            "lexical_baseline_false_retrievals":baseline_false,
            "alias_false_retrievals":alias_false,
            "single_word_alias_abstained":not bool(one_word),
            "deletion_survived_restart":deletion_ok,
            "failures":failures,
            "limits":"Curated overlap/synonym tests, not generalized semantics or Qwen quality.",
        }


if __name__=="__main__":
    result=evaluate()
    print(json.dumps(result,indent=2,ensure_ascii=False))
    raise SystemExit(0 if not result["failures"] and
                     result["alias_top1"]==result["positive_queries"] and
                     result["alias_false_retrievals"]==0 and
                     result["new_alias_only_hits"]>=4 else 1)
