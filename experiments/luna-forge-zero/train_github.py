"""Train a scratch Luna MiniCoder on real, pinned, MIT game code.

Research only. Does not alter the active Luna model or execute source code.
Train: 3 independent external GitHub projects; holdout: 4th project.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import random
from time import perf_counter

import torch
from luna_codegen_model import Config, LunaMiniCoder
from github_corpus import verify


def prepare(data: Path, curriculum: Path | None = None):
    verify(data)
    rows=[json.loads(line) for line in (data/"corpus.jsonl").read_text(encoding="utf-8").splitlines()]
    groups={"train":defaultdict(list),"holdout":defaultdict(list)}
    for row in rows:
        text=("// project: "+row["category"]+" / "+row["path"]+"\n"+row["code"]+"\n").encode("ascii", errors="replace")
        if len(text)<150:
            continue
        groups[row["split"]][row["repository"]].append(torch.tensor(list(text),dtype=torch.long))
    if curriculum is not None:
        from grandchase_reference_gate import verify as verify_original
        verify_original(curriculum=curriculum)
        examples=json.loads(Path(curriculum).read_text(encoding="utf-8"))["tasks"]
        for item in examples:
            if item["split"] != "train":
                continue
            code=item["reference_solution"]
            example=("TASK: "+item["objective"]+"\nLANGUAGE: "+item["language"]+"\nCODE:\n"+code+"\nEND\n").encode("ascii",errors="replace")
            if len(example)>129:
                groups["train"]["luna-original-curriculum"].append(torch.tensor(list(example),dtype=torch.long))
    if len(groups["train"])<3 or len(groups["holdout"])<1:
        raise ValueError("Expected multiple independent training projects and an untouched holdout project")
    return groups

def train(data: Path, out: Path, steps=180, batch_size=12, threads=2, seed=20261028, curriculum: Path | None = None):
    if not 1<=steps<=2500 or not 1<=batch_size<=32 or not 1<=threads<=8:
        raise ValueError("Invalid CPU budget")
    groups=prepare(data, curriculum=curriculum)
    torch.manual_seed(seed);torch.set_num_threads(threads)
    rng=random.Random(seed)
    cfg=Config()
    model=LunaMiniCoder(cfg)
    opt=torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=.01)
    keys={split:list(rows) for split,rows in groups.items()}

    def make_batch(split, n, generator):
        xs=[];ys=[]
        for _ in range(n):
            repo=generator.choice(keys[split])
            tokens=generator.choice(groups[split][repo])
            start=generator.randrange(len(tokens)-cfg.block-1)
            segment=tokens[start:start+cfg.block+1]
            xs.append(segment[:-1]);ys.append(segment[1:])
        return torch.stack(xs),torch.stack(ys)

    @torch.no_grad()
    def evaluation():
        model.eval()
        # identical evaluation windows across before/after
        evaluation_rng=random.Random(seed+1999)
        scores=[]
        for _ in range(8):
            x,y=make_batch("holdout",batch_size,evaluation_rng)
            _,loss=model(x,y)
            scores.append(float(loss))
        return round(sum(scores)/len(scores),6)

    before=evaluation()
    start=perf_counter()
    history=[]
    for step in range(1,steps+1):
        model.train()
        x,y=make_batch("train",batch_size,rng)
        _,loss=model(x,y)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(),1.0)
        opt.step()
        if step==1 or step%50==0 or step==steps:
            val=evaluation()
            record={"step":step,"train_loss":round(float(loss),5),"unseen_repo_loss":val}
            history.append(record)
            print(json.dumps(record),flush=True)
    after=evaluation()
    out=Path(out)
    if out.exists():
        raise FileExistsError("Refusing to overwrite experiment: "+str(out))
    out.mkdir(parents=True)
    torch.save(model.state_dict(),out/"weights.pt")
    digest=hashlib.sha256((out/"weights.pt").read_bytes()).hexdigest()
    report={
        "status":"experiment_not_promoted","training":"random initialization; external MIT game source code plus separately authored original mechanics when selected",
        "architecture":asdict(cfg),"config":asdict(cfg),"parameters":sum(p.numel() for p in model.parameters()),
        "origin_repositories":[x for x in keys["train"] if x!="luna-original-curriculum"],"heldout_repositories":keys["holdout"],
        "original_curriculum_examples":len(groups["train"].get("luna-original-curriculum",[])),
        "original_curriculum_sha256":hashlib.sha256(Path(curriculum).read_bytes()).hexdigest() if curriculum else None,
        "grandchase_raw_repositories_in_training":0,
        "dataset_sha256":hashlib.sha256((data/"corpus.jsonl").read_bytes()).hexdigest(),
        "weights_sha256":digest,"sha256":digest,"steps":steps,"batch":batch_size,"seed":seed,
        "holdout_next_char_loss_before":before,"holdout_next_char_loss_after":after,
        "holdout_improved":after<before,"history":history,"elapsed_sec":round(perf_counter()-start,2),
        "interpretation":"Predicting characters, not evidence of ability to create runnable games",
        "promotion_allowed":False,"weights_used_in_chat":False,
        "model_provenance":"trained from scratch; pinned MIT code plus separately original Luna-authored examples; no code from the nine Grand Chase repositories"
    }
    (out/"report.json").write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
    return report

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--data",type=Path,default=Path("external_data"))
    ap.add_argument("--out",type=Path,default=Path("external_data/model_candidate"))
    ap.add_argument("--steps",type=int,default=180)
    ap.add_argument("--batch",type=int,default=12)
    ap.add_argument("--threads",type=int,default=2)
    ap.add_argument("--curriculum",type=Path,default=None)
    args=ap.parse_args()
    report=train(args.data,args.out,args.steps,args.batch,args.threads,curriculum=args.curriculum)
    print(json.dumps({key:value for key,value in report.items() if key!="history"},indent=2,ensure_ascii=False))
if __name__=="__main__":main()
