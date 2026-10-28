"""From-scratch Luna Lua V2: strictly original lessons, CPU-bounded.

Research experiment, NOT a competent game developer. This fixes two structural
weaknesses of the V0 scratch trainer: a context window too small for the
prompt/function header and under-sampling of Lua lessons in mixed-language
training. It deliberately does not read or train on private client archives.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict
from datetime import datetime
import hashlib
import json
from pathlib import Path
import random

HERE=Path(__file__).resolve().parent
DEST_ROOT=HERE/"external_data"
PROMPT_VARIANTS={
    "horizontal_motion":(
        "Move a platform character horizontally using acceleration and dt",
        "Update actor velocity, x and facing from an input axis",
        "Implement delta-time independent horizontal actor movement"),
    "grounded_jump":(
        "Give a grounded actor jumping gravity and landing",
        "Update vertical physics with floor collision and gravity",
        "Implement jump and fall with a grounded flag"),
    "three_hit_combo":(
        "Implement a timed three hit action combo",
        "Track combo attacks with cooldown and chained input",
        "Advance the three strike sequence with a timing window"),
    "damage_and_invulnerability":(
        "Apply damage, knockback and short invulnerability",
        "Reduce health only outside temporary i-frames",
        "Implement hit reaction and invulnerability timeout"),
    "rectangle_hitbox":(
        "Test axis aligned rectangles for overlap",
        "Check whether two 2D hitboxes intersect",
        "Implement generic bounding rectangle collision"),
    "enemy_patrol":(
        "Move enemy between two patrol endpoints",
        "Reverse patrol direction at the bounds",
        "Implement simple enemy back and forth platform patrol"),
}

def samples() -> list[dict]:
    from original_lua_lessons import lessons,verify,HOLDOUT
    proof=verify()
    if proof["commercial_lua_training_files"]!=0:
        raise ValueError("Training provenance not original-only")
    if any(row["answer"] is not None for row in HOLDOUT):
        raise ValueError("Holdout tasks must not contain answers")
    rows=lessons()
    if set(PROMPT_VARIANTS)!={x["id"] for x in rows}:
        raise ValueError("Training task set changed: review new variants first")
    result=[]
    for row in rows:
        if row["split"]!="train" or row["language"]!="lua" or row["provenance"]!="new Luna-authored implementation; not from commercial game files":
            raise ValueError("Only reviewed original Lua training code allowed")
        for objective in (row["objective"],*PROMPT_VARIANTS[row["id"]]):
            prefix=f"TASK: {objective}\nLANGUAGE: lua\nCODE:\n"
            code=row["code"]+"\nEND\n"
            if not prefix.isascii() or not code.isascii():
                raise ValueError("ASCII tokenizer limitation")
            result.append({"task":row["id"],"prefix":prefix,"code":code})
    return result

def model_config():
    from luna_codegen_model import Config
    # 0.8M weights, 4x attention, 256 ASCII char context, compatible class.
    return Config(vocab=128,block=256,width=128,heads=4,layers=4)

def encode_corpus(rows):
    import torch
    result=[]
    for item in rows:
        prefix=item["prefix"].encode("ascii")
        body=item["code"].encode("ascii")
        if len(prefix)>=model_config().block-2:
            raise ValueError("Task prompt too long for context")
        full=prefix+body
        if len(full)<model_config().block+1:
            # Using shorter examples is valid when sampling shorter segments.
            pass
        result.append({
            "task":item["task"],
            "prefix_size":len(prefix),
            "sequence":torch.tensor(list(full),dtype=torch.long),
        })
    return result

def sample_batch(data, cfg, batch_size, rng):
    """Half tasks begin at TASK prefix; rest train code continuations.

    Mask NEXT-TOKEN labels for the task prefix. This prevents the small
    model from spending capacity predicting English prompt boilerplate.
    """
    import torch
    xs=[];ys=[]
    for _ in range(batch_size):
        item=rng.choice(data)
        tokens=item["sequence"]
        if rng.random()<.55:
            start=0
        else:
            high=max(0,len(tokens)-2)
            start=rng.randint(0,high)
        end=min(start+cfg.block+1,len(tokens))
        segment=tokens[start:end]
        if len(segment)<2:
            start=max(0,len(tokens)-2)
            segment=tokens[start:min(start+cfg.block+1,len(tokens))]
        x=segment[:-1]
        y=segment[1:].clone()
        pos=torch.arange(start+1,start+1+len(y))
        y[pos<item["prefix_size"]]=-100
        # Pad model input with arbitrary valid byte; mask loss on padded labels.
        if len(x)<cfg.block:
            x=torch.nn.functional.pad(x,(0,cfg.block-len(x)),value=10)
            y=torch.nn.functional.pad(y,(0,cfg.block-len(y)),value=-100)
        xs.append(x)
        ys.append(y)
    return torch.stack(xs),torch.stack(ys)

def train(*,steps=600,batch=4,threads=4,seed=20261028,out:Path|None=None,
          eval_steps=4):
    import torch
    from luna_codegen_model import LunaMiniCoder
    if not 1<=steps<=3000 or not 1<=batch<=16 or not 1<=threads<=8:
        raise ValueError("Safe local CPU budget is steps 1..3000, batch 1..16, threads 1..8")
    if not 1<=eval_steps<=8:
        raise ValueError("Evaluation batches must be 1..8")
    cfg=model_config()
    rows=samples()
    data=encode_corpus(rows)
    torch.manual_seed(seed)
    torch.set_num_threads(threads)
    model=LunaMiniCoder(cfg)
    optim=torch.optim.AdamW(model.parameters(),lr=0.00035,weight_decay=0.01)
    rng=random.Random(seed+100)
    def evaluate_training_examples():
        model.eval()
        fixed=random.Random(seed+200)
        scores=[]
        with torch.no_grad():
            for _ in range(eval_steps):
                x,y=sample_batch(data,cfg,batch,fixed)
                _,loss=model(x,y)
                scores.append(float(loss))
        return round(sum(scores)/len(scores),5)
    before=evaluate_training_examples()
    log=[]
    for step in range(1,steps+1):
        model.train()
        x,y=sample_batch(data,cfg,batch,rng)
        _,loss=model(x,y)
        optim.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(),1.)
        optim.step()
        if step in (1,steps) or step%100==0:
            record={"step":step,"train_sample_loss":round(loss.item(),5)}
            if step==steps:
                record["fixed_training_sample_loss"]=evaluate_training_examples()
            log.append(record)
            print(json.dumps(record),flush=True)
    after=evaluate_training_examples()
    root=DEST_ROOT.resolve()
    path=(Path(out).resolve() if out else root/("lua-v2-"+datetime.now().strftime("%Y%m%d-%H%M%S-%f")))
    # Only under ignored external_data, never source directories.
    if path.parent!=root or not path.name.startswith("lua-v2-"):
        raise ValueError("Output must be lua-v2-* directly inside external_data")
    if path.exists():
        raise FileExistsError("Experiment checkpoint exists and cannot be replaced")
    path.mkdir(parents=True,mode=0o700)
    torch.save(model.state_dict(),path/"weights.pt")
    checksum=hashlib.sha256((path/"weights.pt").read_bytes()).hexdigest()
    report={
        "schema":"luna-original-lua-v2-training-v1",
        "status":"experiment_not_promoted",
        "model":"Luna MiniCoder V2 (random initialization, no pretrained model)",
        "architecture":asdict(cfg),"config":asdict(cfg),
        "parameters":sum(t.numel() for t in model.parameters()),
        "original_game_mechanics":len(PROMPT_VARIANTS),
        "prompt_variant_examples":len(rows),
        "source":"original_lua_gameplay.lua; reviewed project-original Lua lessons",
        "original_lua_source_sha256":hashlib.sha256((HERE/"original_lua_gameplay.lua").read_bytes()).hexdigest(),
        "steps":steps,"batch":batch,"threads":threads,"seed":seed,
        "training_sample_loss_before":before,"training_sample_loss_after":after,
        "training_sample_improved":after<before,
        "holdout_code_examples_in_training":0,
        "holdout_task_prompts":3,
        "grandchase_raw_repositories_in_training":0,
        "commercial_lua_files_used":0,
        "private_game_files_read":0,
        "pretrained_weights_used":False,
        "synthetic_augmentations":True,
        "code_executed":False,"model_promotion_allowed":False,
        "weights_sha256":checksum,"history":log,
        "interpretation":"Train-sample next-character loss does not measure code syntax, gameplay, generalization or real game creation.",
    }
    (path/"report.json").write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps({"checkpoint":str(path),"parameters":report["parameters"],
                      "training_sample_loss_before":before,"training_sample_loss_after":after,
                      "still_experimental":True,"commercial_training_files":0},
                     indent=2,ensure_ascii=False))
    return report

def main():
    p=argparse.ArgumentParser(description="Train scratch Luna V2 on six original Lua mechanics only")
    p.add_argument("--steps",type=int,default=600)
    p.add_argument("--batch",type=int,default=4)
    p.add_argument("--threads",type=int,default=4)
    p.add_argument("--eval-steps",type=int,default=4)
    p.add_argument("--out",type=Path)
    a=p.parse_args()
    train(steps=a.steps,batch=a.batch,threads=a.threads,out=a.out,eval_steps=a.eval_steps)

if __name__=="__main__":
    main()
