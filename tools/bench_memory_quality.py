#!/usr/bin/env python3
"""Deterministic episodic-memory quality gate — synthetic lexical tasks only.

NOT a benchmark of Qwen's answers, human memory, semantic generalization,
neural plasticity, or actual system RAM use. Dataset is intentionally small,
transparent and built from invented, nonpersonal episodes.
"""
from __future__ import annotations
import json
import sys
import tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from brain_ssd.chat.episodic import EpisodicMemory
from brain_ssd.chat.memory_safety import check_memory_ambiguities

NOTES = {
    "meet_tuesday": "Reunião projeto rover terça biblioteca norte",
    "meet_thursday": "Reunião projeto rover quinta biblioteca norte",
    "drone": "Protótipo drone verde sensores infravermelho",
    "rover": "Protótipo rover azul sensores lidar",
    "course": "Curso Python backend dados PostgreSQL",
    "bread": "Receita pão integral farinha aveia",
    "astronomy": "Livro astronomia prateleira superior",
    "documentation": "Documentação Brain-SSD benchmark Windows",
    "museum": "Inventário museu histórico planilha catálogo",
    "plants": "Experimento planta estufa irrigação",
    "energy": "Projeto energia solar bateria lítio",
    "pictures": "Backup fotografias pasta arquivos",
}
POSITIVE = [
    ("reunião rover terça", "meet_tuesday"),
    ("projeto terça biblioteca norte", "meet_tuesday"),
    ("reunião rover quinta", "meet_thursday"),
    ("projeto quinta biblioteca norte", "meet_thursday"),
    ("drone verde infravermelho", "drone"),
    ("protótipo drone sensores", "drone"),
    ("rover azul lidar", "rover"),
    ("protótipo rover sensores lidar", "rover"),
    ("curso Python PostgreSQL", "course"),
    ("backend dados PostgreSQL", "course"),
    ("pão integral aveia", "bread"),
    ("receita farinha aveia", "bread"),
    ("livro astronomia prateleira", "astronomy"),
    ("astronomia prateleira superior", "astronomy"),
    ("Brain-SSD benchmark Windows", "documentation"),
    ("documentação benchmark Windows", "documentation"),
    ("inventário museu planilha", "museum"),
    ("museu histórico catálogo", "museum"),
    ("experimento planta irrigação", "plants"),
    ("estufa planta irrigação", "plants"),
    ("energia solar bateria", "energy"),
    ("projeto solar lítio", "energy"),
    ("backup fotografias arquivos", "pictures"),
    ("fotografias pasta arquivos", "pictures"),
]
NEGATIVE = [
    "equação segundo grau", "jogo futebol sábado estádio", "qual CPF pessoal",
    "receita macarrão molho queijo", "vacina calendário infantil",
    "história revolução francesa", "comparar prazo entrega online",
    "viagem férias praia hotel", "meteorologia chuva vento litoral",
    "dinossauros fósseis jurássico", "melhorar sinal wifi roteador",
    "senha email pessoal", "consulta médica dor lombar", "música jazz saxofone",
    "preço combustível gasolina", "filme animação estúdio",
    "rodoviária passagem ônibus", "contrato aluguel imóvel",
    "imposto renda restituição", "horário trem estação",
]
AMBIGUOUS = [
    "reunião projeto rover biblioteca",
    "reunião rover biblioteca norte",
    "qual dia da reunião rover biblioteca",
    "reunião do projeto rover",
    "biblioteca norte projeto rover",
]


def run() -> dict:
    with tempfile.TemporaryDirectory(prefix="brainssd-memory-quality-") as temp:
        store=EpisodicMemory(Path(temp)/"episodes.sqlite3")
        mapping={store.add(text)["id"]:name for name,text in NOTES.items()}
        passed_positive=0
        failures=[]
        for query,expected in POSITIVE:
            hits=store.recall(query)
            top1=mapping[hits[0]["id"]] if hits else None
            if top1==expected:
                passed_positive += 1
            else:
                failures.append({"kind":"positive","expected":expected,"got":top1,"query":query})
        false_positive=0
        for query in NEGATIVE:
            hits=store.recall(query)
            if hits:
                false_positive += 1
                failures.append({"kind":"false_positive","query":query,
                                 "returned_count":len(hits)})
        ambiguity_count=0
        for query in AMBIGUOUS:
            hits=store.recall(query)
            if len(check_memory_ambiguities(hits))>0:
                ambiguity_count += 1
            else:
                failures.append({"kind":"missed_weekday_ambiguity","query":query})
        # Restart then revoke: deleted memories must not reappear by index.
        deleted_id=next(identity for identity,name in mapping.items() if name=="meet_tuesday")
        reopened=EpisodicMemory(store.path)
        deleted=reopened.delete(deleted_id)
        after=reopened.recall("reunião rover biblioteca")
        deletion_safe=deleted and all(x["id"]!=deleted_id for x in after)
        if not deletion_safe:
            failures.append({"kind":"deletion_index_staleness"})
        return {
            "label":"SMALL_SYNTHETIC_LEXICAL_MEMORY_ONLY",
            "positive": {"correct_top1":passed_positive, "total":len(POSITIVE),
                         "top1_accuracy":passed_positive/len(POSITIVE)},
            "negative": {"false_retrievals":false_positive,"total":len(NEGATIVE),
                         "false_retrieval_rate":false_positive/len(NEGATIVE)},
            "weekday_ambiguity": {"flagged":ambiguity_count, "total":len(AMBIGUOUS)},
            "forgetting": {"no_deleted_episode_retrieved":deletion_safe},
            "failures":failures,
            "limitations": [
                "Lexical-only synthetic prompts overlap words with stored notes.",
                "No Qwen inference, no test on real users, no semantic paraphrases.",
                "Potential weekday differences are not proof that either memory is false.",
            ],
        }


def main() -> int:
    report=run()
    print(json.dumps(report,indent=2,ensure_ascii=False))
    return 0 if (
        report["positive"]["correct_top1"]==report["positive"]["total"]
        and report["negative"]["false_retrievals"]==0
        and report["weekday_ambiguity"]["flagged"]==report["weekday_ambiguity"]["total"]
        and report["forgetting"]["no_deleted_episode_retrieved"]
    ) else 1


if __name__=="__main__":
    raise SystemExit(main())
