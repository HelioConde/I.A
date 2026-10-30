"""License/provenance gate for Luna's Grand Chase reference study.

These repositories are NOT an input to training. Only the independently
written action_platform_curriculum.json can be exported as student examples.
No network, cloning, decrypting, extraction or game-client execution.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
CATALOG=ROOT/"grandchase_research_catalog.json"
CURRICULUM=ROOT/"action_platform_curriculum.json"
SHA=re.compile(r"^[0-9a-f]{40}$")
REPO=re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")

def verify(catalog: Path=CATALOG, curriculum: Path=CURRICULUM) -> dict:
    sources=json.loads(Path(catalog).read_text(encoding="utf-8"))
    tasks=json.loads(Path(curriculum).read_text(encoding="utf-8"))
    if sources["training_enabled"] is not False:
        raise ValueError("Grand Chase repository ingestion must stay disabled")
    expected={
        "Divv10/GcResourcesApp","SkelletonX/GrandChaseIV",
        "grandchaseproject/GrandChase-Playtest","rocverde/GrandChaseSeasonV",
        "Diqxy1/grandchase","rockerudon/grandchase_toolkit",
        "rage123450/GrandChasePacketDecoder","Raitou/GrandChaseSeasonEternal",
        "AngelsOnlineDev/grandchase-kom-extractor"
    }
    rows=sources["repositories"]
    if len(rows)!=len(expected) or {r["repository"] for r in rows}!=expected:
        raise ValueError("Expected exactly the nine user-provided source repositories")
    for row in rows:
        repo=row["repository"]
        if not REPO.fullmatch(repo) or not SHA.fullmatch(row["commit"]):
            raise ValueError("Unpinned or invalid repository")
        if row["url"]!="https://github.com/"+repo:
            raise ValueError("Incorrect project provenance URL")
        if row["include_raw_code_in_training"] is not False:
            raise ValueError("Source code from Grand Chase projects cannot enter training automatically")
        if row["disposition"] not in ("excluded","metadata_only","optional_code_after_review"):
            raise ValueError("Unknown disposition")
        if row["license"]=="unspecified" and row["disposition"] not in ("excluded","metadata_only"):
            raise ValueError("Unlicensed code cannot be admitted")
    if tasks["no_external_code"] is not True:
        raise ValueError("Curriculum must contain original examples only")
    records=tasks["tasks"]
    if len(records)<8 or len({t["id"] for t in records})!=len(records):
        raise ValueError("Need enough unique benchmark tasks")
    seen_splits=set()
    for task in records:
        if not re.fullmatch(r"[a-z][a-z0-9_]*",task["id"]):
            raise ValueError("Unsafe task ID")
        if task["language"] not in ("gdscript","javascript"):
            raise ValueError("Unsupported learning language")
        if task["split"] not in ("train","holdout"):
            raise ValueError("Unsupported split")
        if not task["objective"] or len(task["criteria"])<2:
            raise ValueError("Incomplete learning task")
        solution=task.get("reference_solution")
        if task["split"]=="train":
            if not solution or len(solution)<30:
                raise ValueError("Train task requires original reference code")
            if any(ord(c)>127 for c in solution):
                raise ValueError("ASCII-only tokenizer needs ASCII source")
        elif solution is not None:
            raise ValueError("Holdout tasks must never include training answers")
        seen_splits.add(task["split"])
    if seen_splits!={"train","holdout"}:
        raise ValueError("Need separate train and heldout")
    return {"audited_repositories":len(rows),"raw_grandchase_sources_in_training":0,
            "original_training_tasks":sum(t["split"]=="train" for t in records),
            "unseen_evaluation_tasks":sum(t["split"]=="holdout" for t in records),
            "training_source":"Original Luna implementation, not raw copyrighted game sources"}

def export_training(out: Path, curriculum: Path=CURRICULUM) -> dict:
    verify(curriculum=curriculum)
    tasks=json.loads(Path(curriculum).read_text(encoding="utf-8"))["tasks"]
    out=Path(out)
    out.parent.mkdir(parents=True,exist_ok=True)
    if out.exists():
        raise FileExistsError("Refusing to overwrite training examples")
    with out.open("w",encoding="utf-8") as fh:
        for item in tasks:
            if item["split"]!="train":
                continue
            row={"id":item["id"],"provenance":"Luna original authored example",
                 "objective":item["objective"],"language":item["language"],
                 "code":item["reference_solution"],"split":"train",
                 "criteria":item["criteria"]}
            fh.write(json.dumps(row,ensure_ascii=False,sort_keys=True)+"\n")
    return {"training_examples":sum(t["split"]=="train" for t in tasks),
            "path":str(out),"holdout_exported":0}

def main():
    cli=argparse.ArgumentParser()
    cli.add_argument("action",choices=("audit","export"))
    cli.add_argument("--out",type=Path,default=ROOT/"external_data"/"original_curriculum_train.jsonl")
    args=cli.parse_args()
    print(json.dumps(verify() if args.action=="audit" else export_training(args.out),
          indent=2,ensure_ascii=False))

if __name__=="__main__":
    main()
