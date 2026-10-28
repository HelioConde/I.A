"""Evaluate ORIGINAL scratch Luna V2 on the same original holdout prompts as V0.

Never executes generated code or reads commercial data. Reports separate
training-sample learning vs unseen-brief signature heuristics.
"""
from __future__ import annotations
import argparse
from hashlib import sha256
import json
from pathlib import Path

from original_lua_lessons import HOLDOUT
from benchmark_original_lua import prompt_for,summarize
from train_original_lua_v2 import DEST_ROOT

def find_candidates():
    root=DEST_ROOT.resolve()
    if not root.is_dir():
        return []
    return sorted((p for p in root.iterdir() if p.is_dir() and p.name.startswith("lua-v2-")
                   and (p/"weights.pt").is_file() and (p/"report.json").is_file()),
                  key=lambda x:x.name,reverse=True)

def verified(ckpt:Path):
    path=Path(ckpt).resolve()
    if path.parent!=DEST_ROOT.resolve() or not path.name.startswith("lua-v2-"):
        raise ValueError("V2 checkpoint must be in the ignored external_data folder")
    report=json.loads((path/"report.json").read_text(encoding="utf-8"))
    if (report.get("schema")!="luna-original-lua-v2-training-v1"
        or report.get("pretrained_weights_used") is not False
        or report.get("commercial_lua_files_used")!=0
        or report.get("model_promotion_allowed") is not False
        or report.get("status")!="experiment_not_promoted"):
        raise ValueError("V2 provenance not verified")
    if report.get("holdout_code_examples_in_training")!=0:
        raise ValueError("Holdout answers may not enter training")
    path_weights=path/"weights.pt"
    if path_weights.stat().st_size>64*1024*1024:
        raise ValueError("Checkpoint file exceeds safe bound")
    digest=sha256()
    with path_weights.open("rb") as f:
        for part in iter(lambda:f.read(1024*1024),b""):
            digest.update(part)
    if digest.hexdigest()!=report.get("weights_sha256"):
        raise ValueError("V2 checksum mismatch")
    return report,path_weights

def probe(*,ckpt:Path|None=None,chars:int=220,seed:int=20261028,
          include_output:bool=True):
    if not 1<=chars<=240:
        raise ValueError("Chars must be 1..240")
    path=Path(ckpt) if ckpt is not None else next(iter(find_candidates()),None)
    if path is None:
        raise FileNotFoundError("No local original Lua V2 candidate. Train with menu 16 first.")
    report,weights=verified(path)
    from luna_codegen_model import Config,LunaMiniCoder
    import torch
    torch.set_num_threads(min(torch.get_num_threads(),4))
    model=LunaMiniCoder(Config(**report["config"]))
    model.load_state_dict(torch.load(weights,weights_only=True,map_location="cpu",mmap=True),assign=True)
    model.eval()
    results=[]
    for i,task in enumerate(HOLDOUT):
        prompt=prompt_for(task)
        torch.manual_seed(seed+i)
        produced=model.generate(prompt,chars=chars,temperature=.6)[len(prompt):]
        row={"task_id":task["id"],"objective":task["objective"],**summarize(produced)}
        if include_output:
            row["raw_generated_text"]=produced
        results.append(row)
    return {
        "schema":"luna-original-lua-v2-heldout-probe",
        "model":"Luna MiniCoder V2 scratch only, Qwen NOT USED",
        "checkpoint":path.name,
        "checkpoint_sha256":report["weights_sha256"],
        "train_sample_loss_before":report["training_sample_loss_before"],
        "train_sample_loss_after":report["training_sample_loss_after"],
        "holdout_prompts":len(results),
        "function_signature_heuristic_count":sum(
            x["contains_obvious_lua_function_signature"] for x in results),
        "holdout_syntax":"NOT_TESTED",
        "holdout_gameplay":"NOT_TESTED",
        "not_a_game_creating_model_proof":True,
        "raw_commercial_scripts_used":0,
        "code_executed":False,"new_training_performed":False,
        "model_promoted":False,
        "results":results,
        "warning":"Train loss reduction may just mean memorizing six tiny lesson solutions. Holdout prompts contain no reference code and this heuristic is not a valid syntax/behavior test.",
    }

def main():
    p=argparse.ArgumentParser(description="Try own V2 Lua model on novel original game tasks")
    p.add_argument("--chars",type=int,default=220)
    p.add_argument("--no-output",action="store_true")
    a=p.parse_args()
    print(json.dumps(probe(chars=a.chars,include_output=not a.no_output),
                     ensure_ascii=False,indent=2))
if __name__=="__main__":
    main()
