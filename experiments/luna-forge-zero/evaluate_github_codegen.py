"""Nonexecuting smoke evaluation of generated JS from the GitHub-trained candidate.

node --check performs parsing only, not running the game's JavaScript.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import torch
from luna_codegen_model import LunaMiniCoder, Config

PROMPTS = (
    "// project: phaser / arcade movement\nfunction movePlayer(",
    "// project: canvas / player control\nfunction updatePlayer(",
    "// project: platformer / enemies\nfunction updateEnemy(",
    "// project: canvas / gravity\nfunction applyGravity(",
    "// project: game / coins\nfunction collectCoins(",
)

def evaluate(checkpoint: Path) -> dict:
    checkpoint=Path(checkpoint)
    report=json.loads((checkpoint/"report.json").read_text(encoding="utf-8"))
    weights=checkpoint/"weights.pt"
    if hashlib.sha256(weights.read_bytes()).hexdigest()!=report["weights_sha256"]:
        raise ValueError("Checkpoint integrity error")
    model=LunaMiniCoder(Config(**report["config"]))
    model.load_state_dict(torch.load(weights,map_location="cpu",weights_only=True,mmap=True),assign=True)
    model.eval()
    node=shutil.which("node")
    results=[]
    for index,prompt in enumerate(PROMPTS):
        raw=model.generate(prompt,chars=190,temperature=.6,deterministic=True)
        code=raw[len(prompt):].split("\nFIM")[0].strip()
        parse="unverified" if node is None else "fail"
        if node and len(code)>=8:
            with tempfile.TemporaryDirectory(prefix="luna_code_eval_") as temporary:
                candidate=Path(temporary)/"candidate.js"
                candidate.write_text(prompt+code,encoding="utf-8")
                run=subprocess.run([node,"--check",str(candidate)],
                                   text=True,capture_output=True,check=False,timeout=5)
                parse="pass" if run.returncode==0 else "fail"
        results.append({"id":index,"prompt":prompt,"generated_len":len(code),
                        "output_sha256":hashlib.sha256(code.encode()).hexdigest(),
                        "syntax_only":parse,
                        "behavior":"NOT_TESTED"})
    return {"checkpoint_sha256":report["weights_sha256"],
            "model_code_samples":len(results),
            "syntax_pass":sum(s["syntax_only"]=="pass" for s in results),
            "results":results,
            "disclaimer":"Syntax is not functionality. No code was executed, no gameplay claim."}

if __name__=="__main__":
    cli=argparse.ArgumentParser()
    cli.add_argument("--checkpoint",type=Path,required=True)
    cli.add_argument("--out",type=Path,required=True)
    args=cli.parse_args()
    score=evaluate(args.checkpoint)
    args.out.write_text(json.dumps(score,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(score,indent=2,ensure_ascii=False))
