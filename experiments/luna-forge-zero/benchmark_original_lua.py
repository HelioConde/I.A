"""Honest local-only heldout coding probe for Luna's OWN MiniCoder weights.

Uses three original, untrained task briefs from original_lua_lessons.HOLDOUT.
This does NOT read external client scripts, execute generated code, fine-tune
weights, or attribute pretrained Ollama output to Luna. A few structural
signals are not syntax or gameplay correctness; the probe prints raw output
only to the user's own terminal so it can be reviewed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

from original_lua_lessons import HOLDOUT
from preview_local_candidate import candidates, verify_candidate, DATA

MAX_CHARS=240

def summarize(code: str) -> dict:
    """Weak structural signals only; never claim syntax or behavior validity."""
    return {
        "output_length_chars":len(code),
        "contains_function_keyword":bool(re.search(r"\bfunction\b",code)),
        "contains_end_keyword":bool(re.search(r"\bend\b",code)),
        "contains_return_keyword":bool(re.search(r"\breturn\b",code)),
        "contains_obvious_lua_function_signature":bool(
            re.search(r"\bfunction\s+[A-Za-z_][\w.:]*\s*\(",code)),
        "output_sha256":hashlib.sha256(code.encode("utf-8")).hexdigest(),
        "lua_syntax":"NOT_TESTED",
        "gameplay_behavior":"NOT_TESTED",
    }

def prompt_for(item: dict) -> str:
    if item.get("split")!="holdout" or item.get("answer") is not None:
        raise ValueError("Benchmark tasks must be original holdout without answers")
    return "TASK: "+item["objective"]+"\nLANGUAGE: lua\nCODE:\n"

def benchmark(ckpt: Path|None=None, *, chars:int=220,
              seed:int=20261028, include_output:bool=True) -> dict:
    if not 1<=chars<=MAX_CHARS:
        raise ValueError("Benchmark generation budget must be 1..240 characters")
    choice=Path(ckpt) if ckpt is not None else next(iter(candidates(DATA)),None)
    if choice is None:
        raise FileNotFoundError("No locally trained MiniCoder candidate. Train approved MIT/original data with menu 4.")
    report,weights=verify_candidate(choice,DATA)
    if report.get("grandchase_raw_repositories_in_training")!=0:
        raise ValueError("Original-only model provenance not verified")
    from luna_codegen_model import Config, LunaMiniCoder
    import torch
    torch.set_num_threads(min(4,torch.get_num_threads()))
    model=LunaMiniCoder(Config(**report["config"]))
    model.load_state_dict(torch.load(weights,weights_only=True,map_location="cpu",mmap=True),assign=True)
    model.eval()
    results=[]
    for i,item in enumerate(HOLDOUT):
        prompt=prompt_for(item)
        torch.manual_seed(seed+i)
        full=model.generate(prompt,chars=chars,temperature=.6)
        generated=full[len(prompt):]
        result={
            "task_id":item["id"],
            "objective":item["objective"],
            **summarize(generated),
            "generated_on_user_machine":True,
        }
        if include_output:
            result["raw_generated_text"]=generated
        results.append(result)
    return {
        "schema":"luna-original-lua-briefs-benchmark-v1",
        "model":"OWN MiniCoder; pretrained Qwen/Ollama NOT used",
        "candidate_checkpoint":choice.name,
        "checkpoint_sha256":report["weights_sha256"],
        "tasks_not_in_supervised_training":len(HOLDOUT),
        "task_answers_in_benchmark":0,
        "syntax_pass_count":"NOT_MEASURED",
        "gameplay_pass_count":"NOT_MEASURED",
        "function_signature_heuristic_count":sum(
            x["contains_obvious_lua_function_signature"] for x in results),
        "promoted":False,
        "trained_on_commercial_game_code":False,
        "new_training_performed":False,
        "code_executed":False,
        "game_files_read":False,
        "results":results,
        "interpretation":"Diagnostic of character generation on novel original briefs; no parsing, no gameplay execution. Zero detected signatures is not a formal model evaluation and some signatures are false positives.",
    }

def main():
    p=argparse.ArgumentParser(description="Sample OWN Luna MiniCoder against new original Lua briefs")
    p.add_argument("--chars",type=int,default=220)
    p.add_argument("--no-output",action="store_true",help="Do not show generated code, just hashes and metrics")
    args=p.parse_args()
    outcome=benchmark(chars=args.chars,include_output=not args.no_output)
    print(json.dumps(outcome,ensure_ascii=False,indent=2))
if __name__=="__main__":
    main()
