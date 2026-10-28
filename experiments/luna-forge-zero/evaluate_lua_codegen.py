"""Syntax-only benchmark of GENERATED original Lua tasks.

Unlike the passing authored gameplay tests, this evaluates the MiniCoder output.
The luac command parses and compiles candidates but NEVER executes them.
No commercial game files, user directories, or source are accessed.
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
from luna_codegen_model import Config, LunaMiniCoder

PROMPTS=(
    ("lua_boss_phase","TASK: Original boss attack phase function\nLANGUAGE: lua\nCODE:\nfunction Game.boss_phase("),
    ("lua_enemy_sensor","TASK: Follow target inside perception range\nLANGUAGE: lua\nCODE:\nfunction Game.enemy_sense("),
    ("lua_one_way_floor","TASK: Implement collision with one-way platforms\nLANGUAGE: lua\nCODE:\nfunction Game.platform_collision("),
    ("lua_hitbox_stun","TASK: Apply a short stun to an enemy\nLANGUAGE: lua\nCODE:\nfunction Game.apply_stun("),
    ("lua_collectible","TASK: Collect an item inside a pickup radius\nLANGUAGE: lua\nCODE:\nfunction Game.collect_item("),
)

def evaluate(checkpoint: Path) -> dict:
    checkpoint=Path(checkpoint)
    report=json.loads((checkpoint/"report.json").read_text(encoding="utf-8"))
    digest=hashlib.sha256((checkpoint/"weights.pt").read_bytes()).hexdigest()
    if digest!=report["weights_sha256"]:
        raise ValueError("Invalid model checkpoint checksum")
    model=LunaMiniCoder(Config(**report["config"]))
    model.load_state_dict(torch.load(checkpoint/"weights.pt",weights_only=True,map_location="cpu",mmap=True),assign=True)
    model.eval()
    luac=shutil.which("luac5.4") or shutil.which("luac")
    results=[]
    for i,(task,prompt) in enumerate(PROMPTS):
        torch.manual_seed(4400+i)
        generated=model.generate(prompt,chars=220,temperature=.6)
        code=generated[len(prompt):].split("\nEND\n")[0]
        syntax="unverified" if not luac else "fail"
        if luac and code.strip():
            with tempfile.TemporaryDirectory(prefix="luna_lua_syntax_") as temp:
                candidate=Path(temp)/"candidate.lua"
                candidate.write_text("local Game={}\n"+prompt.rsplit("CODE:\n",1)[1]+code+"\nreturn Game\n",encoding="utf-8")
                outcome=subprocess.run([luac,"-p",str(candidate)],text=True,capture_output=True,timeout=5,check=False,cwd=temp)
                if outcome.returncode==0: syntax="pass"
        results.append({"task":task,"generated_characters":len(code),
                        "generated_sha256":hashlib.sha256(code.encode("utf-8")).hexdigest(),
                        "syntax":syntax,"behavior":"NOT_TESTED"})
    return {"model_checkpoint_sha256":digest,"generated_lua_examples":len(PROMPTS),
            "lua_syntax_pass":sum(x["syntax"]=="pass" for x in results),
            "syntax_verifier_available":luac is not None,
            "generated_code_executed":False,"behavior_tested":False,
            "training_promotion_allowed":False,
            "results":results,
            "disclaimer":"These are generated code tests. Passing tests for author-written examples do not imply model competency."}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--checkpoint",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    if args.out.exists():
        raise FileExistsError("Refusing to overwrite evaluation report")
    data=evaluate(args.checkpoint)
    args.out.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(data,indent=2,ensure_ascii=False))
if __name__=="__main__": main()
