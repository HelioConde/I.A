"""Train a lightweight multinomial Naive Bayes skill router using ONLY curated prompts.

This trains class priors and token likelihoods; it does not fine-tune an LLM.
No external repositories or benchmark holdout content are accessed.
"""
from __future__ import annotations
import argparse
import collections
import hashlib
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "knowledge/game_dev/router_examples.json"
TOKEN = re.compile(r"[a-zA-ZÀ-ÿ][a-zA-ZÀ-ÿ0-9_]+")
def words(value: str) -> list[str]:
    return [w.casefold() for w in TOKEN.findall(value) if len(w)>2]

def fit(examples: list[dict]) -> dict:
    train=[e for e in examples if e["split"]=="train"]
    if not train: raise ValueError("No training examples")
    counts=collections.Counter(e["skill"] for e in train)
    tokens={label:collections.Counter() for label in counts}
    for e in train: tokens[e["skill"]].update(words(e["text"]))
    vocabulary=sorted({word for group in tokens.values() for word in group})
    return {"model_type":"multinomial_naive_bayes","version":1,"classes":sorted(counts),
            "doc_counts":dict(counts),"word_counts":{k:dict(v) for k,v in tokens.items()},
            "vocabulary":vocabulary,"alpha":1.0,
            "note":"Skill-routing statistical model only; not an LLM fine-tune"}

def predict(model:dict,text:str)->str:
    vocab=set(model["vocabulary"])
    terms=collections.Counter(w for w in words(text) if w in vocab)
    total_docs=sum(model["doc_counts"].values())
    scores={}
    for label in model["classes"]:
        count=model["doc_counts"][label]
        likelihood=model["word_counts"][label]
        denominator=sum(likelihood.values())+model["alpha"]*len(vocab)
        scores[label]=math.log(count/total_docs)+sum(
          number*math.log((likelihood.get(token,0)+model["alpha"])/denominator)
          for token,number in terms.items())
    return sorted(scores,key=lambda label:(-scores[label],label))[0]

def train_and_evaluate(path:Path=DATA)->tuple[dict,dict]:
    raw=path.read_bytes()
    data=json.loads(raw)
    if data.get("schema_version")!=1: raise ValueError("Invalid dataset schema")
    examples=data["examples"]
    if any(e.get("split") not in ("train","test") for e in examples):raise ValueError("Unknown split")
    if len({(e["text"].casefold()) for e in examples})!=len(examples):raise ValueError("Duplicate prompts")
    train_texts={e["text"].casefold() for e in examples if e["split"]=="train"}
    if any(e["text"].casefold() in train_texts for e in examples if e["split"]=="test"):
        raise ValueError("Train/test leakage")
    catalog=json.loads((ROOT/"knowledge/game_dev/skills.json").read_text(encoding="utf-8"))
    known={s["id"] for s in catalog["skills"]}
    if any(e["skill"] not in known for e in examples):raise ValueError("Unknown skill")
    model=fit(examples)
    if set(model["classes"])!=known:raise ValueError("Missing skill training examples")
    model["dataset_sha256"]=hashlib.sha256(raw).hexdigest()
    held=[e for e in examples if e["split"]=="test"]
    if not held:raise ValueError("No test examples")
    results=[{"expected":e["skill"],"predicted":predict(model,e["text"])} for e in held]
    correct=sum(x["expected"]==x["predicted"] for x in results)
    report={"model_type":model["model_type"],"train_examples":len(examples)-len(held),
            "test_examples":len(held),"correct":correct,"accuracy":correct/len(held),
            "results":results,"dataset_sha256":model["dataset_sha256"]}
    return model,report

def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--output-dir",type=Path,default=ROOT/"results/game_knowledge_training")
    parser.add_argument("--min-accuracy",type=float,default=0.0)
    args=parser.parse_args()
    model,report=train_and_evaluate()
    args.output_dir.mkdir(parents=True,exist_ok=True)
    (args.output_dir/"skill_router_model.json").write_text(json.dumps(model,indent=2,ensure_ascii=False,sort_keys=True)+"\n",encoding="utf-8")
    (args.output_dir/"evaluation.json").write_text(json.dumps(report,indent=2,ensure_ascii=False,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k!="results"},sort_keys=True))
    return 0 if report["accuracy"]>=args.min_accuracy else 1

if __name__=="__main__":
    raise SystemExit(main())
