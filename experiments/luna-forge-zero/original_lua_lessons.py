"""Turn ONLY author-written, tested Lua functions into training examples.

Never reads a path supplied by the user. Never reads grand chase files,
game archives, third-party client code, or files produced by a decompiler.
Holdout questions have no answers and are never included in training output.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re

HERE=Path(__file__).resolve().parent
SOURCE=HERE/"original_lua_gameplay.lua"
LESSONS={
    "horizontal_motion": ("Move player horizontally with acceleration and facing","acceleration","frame_time"),
    "grounded_jump": ("Create grounded jump, gravity and landing","ground_check","gravity"),
    "three_hit_combo": ("Make a three-hit combo with input windows","cooldown","chain_reset"),
    "damage_and_invulnerability": ("Apply hit damage and temporary invulnerability","hp_bounds","i_frames"),
    "rectangle_hitbox": ("Detect overlapping rectangle hitboxes","overlap","strict_edges"),
    "enemy_patrol": ("Patrol a platform and reverse at its bounds","bounds","direction"),
}
HOLDOUT=(
    {"id":"boss_attack_phases","objective":"Implement original boss phases with cooldown and changing attacks","language":"lua","split":"holdout","answer":None},
    {"id":"enemy_line_of_sight","objective":"Track a target with sight radius and return to idle","language":"lua","split":"holdout","answer":None},
    {"id":"one_way_platform","objective":"Support jumping through and dropping down a one-way platform","language":"lua","split":"holdout","answer":None},
)
PATTERN=re.compile(r"(?ms)^-- lesson: ([a-z0-9_]+)[ \t]*\n(.*?)^-- end-lesson[ \t]*$")
FORBIDDEN=("\\x1bLua","\\x1bKL")

def lessons() -> list[dict]:
    content=SOURCE.read_text(encoding="utf-8")
    if not content.startswith("-- Luna Forge: original"):
        raise ValueError("Author provenance header missing")
    if any(token.lower() in content.lower() for token in FORBIDDEN):
        raise ValueError("Unexpected external game content marker")
    extracted=PATTERN.findall(content)
    if len(extracted)!=len(LESSONS) or len({x[0] for x in extracted})!=len(LESSONS):
        raise ValueError("Unexpected number of original Lua lesson blocks")
    if {name for name,_ in extracted}!=set(LESSONS):
        raise ValueError("Unreviewed lesson discovered")
    result=[]
    for name,code in extracted:
        if "function Game." not in code or len(code)<120:
            raise ValueError(f"Invalid original Lua lesson: {name}")
        if any(term in code.lower() for term in ("grandchase", "grand chase")):
            raise ValueError(f"Invalid original Lua lesson: {name}")
        if not code.isascii():
            raise ValueError("MiniCoder requires ASCII-encodable code")
        title,*criteria=LESSONS[name]
        result.append({
            "id":name,"language":"lua","objective":title,
            "criteria":criteria,"code":code.strip()+"\n","split":"train",
            "provenance":"new Luna-authored implementation; not from commercial game files",
        })
    return result

def verify() -> dict:
    rows=lessons()
    if len({x["id"] for x in HOLDOUT}.intersection(x["id"] for x in rows)):
        raise ValueError("Train and holdout overlap")
    if any(x["answer"] is not None for x in HOLDOUT):
        raise ValueError("Holdout must contain no solutions")
    return {
        "status":"reviewed_original_only",
        "lua_training_lessons":len(rows),
        "heldout_questions_without_answers":len(HOLDOUT),
        "original_module_sha256":hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "commercial_lua_training_files":0,
        "commercial_lua_files_opened":0,
        "trainer_executed_commercial_code":False,
        "source":"original_lua_gameplay.lua",
        "interpretation":"Reference functions passed their own behavior tests only if CI confirms; generated model code must be evaluated separately.",
    }

def export(path: Path) -> dict:
    report=verify()
    path=Path(path)
    if path.exists():
        raise FileExistsError("Refusing to overwrite an existing training export")
    if SOURCE.resolve().parent not in path.resolve().parents:
        raise ValueError("Export must remain inside the Luna experiment area")
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",encoding="utf-8") as f:
        for item in lessons():
            f.write(json.dumps(item,ensure_ascii=False,sort_keys=True)+"\n")
    return {**report,"output":str(path),"exported_holdout_answers":0}

def main():
    p=argparse.ArgumentParser(description="Original Lua lessons only; no commercial file ingestion")
    p.add_argument("action",choices=("verify","export","holdout"))
    p.add_argument("--out",type=Path,default=HERE/"external_data"/"original_lua_lessons.jsonl")
    a=p.parse_args()
    if a.action=="verify": result=verify()
    elif a.action=="export": result=export(a.out)
    else: result={"holdout":HOLDOUT,"answers_included":0}
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=="__main__":
    main()
