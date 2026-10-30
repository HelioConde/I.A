"""Inspect locally trained PRIVATE Luna Lua weights; never execute generated text."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

from train_private_lua import OUTPUT_ROOT,private_models
from luna_codegen_model import Config,LunaMiniCoder

def verify_checkpoint(folder: Path)->tuple[dict,Path]:
    candidate=Path(folder).resolve()
    if candidate.parent!=OUTPUT_ROOT.resolve() or not candidate.name.startswith("private-lua-"):
        raise ValueError("Private Lua candidate must be inside the ignored local-only folder")
    weights=candidate/"weights.pt"
    reportfile=candidate/"report.json"
    if not weights.is_file() or not reportfile.is_file():
        raise FileNotFoundError("Incomplete private model")
    report=json.loads(reportfile.read_text(encoding="utf-8"))
    if report.get("status")!="private_experimental_checkpoint_not_promoted" or report.get("model_promotion_allowed") is not False:
        raise ValueError("Invalid private model provenance")
    expected=report.get("weights_sha256")
    digest=hashlib.sha256()
    with weights.open("rb") as stream:
        for part in iter(lambda:stream.read(1024*1024),b""):
            digest.update(part)
    if digest.hexdigest()!=expected:
        raise ValueError("Private model checksum mismatch")
    if weights.stat().st_size>64*1024*1024:
        raise ValueError("Unexpected oversized MiniCoder weights")
    return report,weights

def preview(task: str,chars: int=240)->dict:
    if not 1<=chars<=480 or not task.strip() or len(task)>600:
        raise ValueError("Invalid preview request limits")
    options=private_models()
    if not options:
        raise FileNotFoundError("No private Lua checkpoint trained yet")
    candidate=options[0]
    report,weights=verify_checkpoint(candidate)
    import torch
    torch.set_num_threads(4)
    model=LunaMiniCoder(Config(**report["architecture"]))
    model.load_state_dict(torch.load(weights,map_location="cpu",weights_only=True,mmap=True),assign=True)
    model.eval()
    torch.manual_seed(20261028)
    prefix="-- tarefa de jogo: "+task.strip()+"\n-- codigo Lua:\nfunction "
    text=model.generate(prefix,chars=chars,temperature=.65)[len(prefix):]
    return {
        "backend":"Luna MiniCoder incremental private Lua; NOT Qwen",
        "private_model":candidate.name,
        "training_source":"authorized local Lua samples (not copied to GitHub)",
        "generated_text":"function "+text,
        "source_code_executed":False,
        "generated_code_executed":False,
        "syntax_validated":False,
        "gameplay_validated":False,
        "model_promoted":False,
        "parent_sha256":report["parent_weights_sha256"],
        "warning":"This is a 116K-character model with context 128. It may produce incoherent Lua; metrics are experimental.",
    }

def main():
    p=argparse.ArgumentParser(description="View private local Lua-trained MiniCoder output")
    p.add_argument("action",choices=("list","generate"))
    p.add_argument("--task",default="movimentacao horizontal original de um personagem 2D")
    p.add_argument("--chars",type=int,default=240)
    args=p.parse_args()
    if args.action=="list":
        print(json.dumps({"available_private_candidates":len(private_models()),
                          "active_model_changed":False},indent=2))
    else:
        print(json.dumps(preview(args.task,args.chars),ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
