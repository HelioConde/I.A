#!/usr/bin/env python3
"""Real model-only patch challenge against Luna's already Qwen-authored game.

Neither this evaluator nor its prompt provides replacement gameplay code.
The model generates the precise JavaScript fragment. Source is never run during
inference; only Chromium in a disposable CI job may execute accepted candidates.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time
from benchmark_luna_game_models import command, sha

ROOT=Path(__file__).resolve().parents[1]
START="// Attack\n"
END="// Enemy movement\n"
GAME_PATH=ROOT/"site"/"luna-created"/"game.js"
REQUEST=(
    "Você é Luna GameDev, corrigindo seu próprio jogo original 2D em JS Canvas. "
    "O jogo está completo e o problema é que um único ataque reduz hp a cada "
    "frame (até 50 vezes), matando instantaneamente um boss de 150 HP. "
    "Substitua SOMENTE o bloco Attack da função gameLoop, sem mexer em HTML, "
    "CSS, inimigos, controles ou outras linhas. Responda com APENAS instruções "
    "JavaScript do corpo de gameLoop(), sem markdown, sem comentários, sem "
    "explicações e SEM as linhas // Attack e // Enemy movement. "
    "Variáveis disponíveis: isAttacking, attackTimer, attackTarget, player, "
    "attackRange, enemies. Um KeyZ arma um ataque, atribui attackTimer e "
    "seleciona attackTarget. Um ataque acertado deve aplicar dano de 10 HP "
    "UMA VEZ, mesmo que o gameLoop execute muitos frames; após aplicar "
    "dano, remova referência ao alvo com 'attackTarget = null' para impedir "
    "dano repetido. Se o inimigo chegar a hp <= 0, remova-o usando indexOf "
    "e splice ou filter sem acessar índice inválido. Se attackTimer chegar "
    "a zero, finalize isAttacking. A distância usa x/y de player e "
    "attackTarget, com attackRange. Não use funções não declaradas, "
    "timer externo, import, fetch, eval nem rede. Retorne apenas bloco "
    "JavaScript que se encaixe em gameLoop. "
)
BANNED=re.compile(
    r"<script|https?://|\b(?:eval|Function|fetch|WebSocket|XMLHttpRequest|"
    r"Worker|require|import)\s*\(|\b(?:localStorage|sessionStorage|indexedDB)\b",re.I
)
REQUIRED=("isAttacking","attackTimer","attackTarget","attackRange","hp","enemies")
MAX_FRAGMENT=6000

def source_region(original:str)->tuple[str,str,str]:
    if original.count(START)!=1 or original.count(END)!=1:
        raise ValueError("baseline_attack_markers_not_unique")
    a=original.index(START)+len(START)
    b=original.index(END,a)
    return original[:a],original[a:b],original[b:]

def unwrap_fragment(text:str)->str:
    t=text.strip()
    t=re.sub(r"^<think>.*?</think>\s*","",t,flags=re.I|re.S)
    if "</think>" in t or "<think>" in t:
        raise ValueError("incomplete_model_reasoning")
    code=chr(96)*3
    m=re.fullmatch(re.escape(code)+r"(?:javascript|js)?\s*\n(.*?)\n"+re.escape(code),t,re.I|re.S)
    if m:t=m.group(1).strip()
    if not 35<=len(t)<=MAX_FRAGMENT:
        raise ValueError("invalid_patch_size")
    if START.strip() in t or END.strip() in t:
        raise ValueError("model_repeated_markers")
    if BANNED.search(t):
        raise ValueError("unsafe_patch")
    if any(term not in t for term in REQUIRED):
        raise ValueError("missing_attack_contract")
    if not re.search(r"attackTarget\s*=\s*null",t):
        raise ValueError("no_single_hit_prevention")
    if not re.search(r"attackTarget\.hp\s*-=",t):
        raise ValueError("no_real_enemy_damage")
    return t+"\n"

def check_js(code:str)->bool:
    import tempfile
    with tempfile.TemporaryDirectory(prefix="luna-combat-check-") as td:
        path=Path(td)/"game.js"
        path.write_bytes(code.encode("utf-8"))
        try:
            res=subprocess.run(["node","--check",str(path)],capture_output=True,timeout=10)
            return res.returncode==0
        except (OSError,subprocess.TimeoutExpired):
            return False

def run_trial(original:str,infer,*,attempts:int=3,validate=check_js)->tuple[dict,str|None]:
    if not 1<=attempts<=3:raise ValueError("invalid_attempts")
    before,bug,after=source_region(original)
    feedback=""
    rows=[]
    candidate=None
    for i in range(attempts):
        prompt="/no_think\n"+REQUEST+"\nTRECHO DO SEU JOGO A CORRIGIR:\n"+bug
        if feedback:prompt+="\nO código anterior falhou com: "+feedback+". Gere bloco inteiro novamente."
        try:
            response=infer(prompt,900)
            raw=str(response.get("answer") or "")
            if response.get("model_generated") is not True:raise ValueError("not_real_model")
            patch=unwrap_fragment(raw)
            updated=before+patch+after
            if not validate(updated):raise ValueError("javascript_syntax_error")
            if updated==original:raise ValueError("unchanged_game")
            candidate=updated
            reason="STATIC_ACCEPTED"
            accepted=True
        except Exception as exc:
            reason=str(exc)[:120] if isinstance(exc,ValueError) else "native_"+type(exc).__name__
            accepted=False
        rows.append({"attempt":i+1,"model_generated":response.get("model_generated") is True if "response" in locals() else False,
                     "reason":reason,"accepted":accepted})
        if accepted:break
        feedback=reason
    report={"benchmark":"Luna GameDev real attack-once model patch",
            "status":"STATIC_PATCH_CANDIDATE" if candidate else "INCOMPLETE",
            "source_sha256":hashlib.sha256(original.encode()).hexdigest(),
            "model_generated_patch":bool(candidate),
            "assistant_gameplay_code_used":False,
            "gameplay_verified":False,"attempts":rows}
    if candidate:
        report["game_js_sha256"]=hashlib.sha256(candidate.encode()).hexdigest()
    return report,candidate

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--model",type=Path,required=True)
    p.add_argument("--runtime",type=Path,required=True)
    p.add_argument("--label",choices=("ornith-1.5-9b","qwen3-4b"),required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--attempts",type=int,choices=(1,2,3),default=3)
    args=p.parse_args()
    original=GAME_PATH.read_text(encoding="utf-8")
    args.out.mkdir(parents=True,exist_ok=True)
    last_out=[]
    def infer(prompt:str,tokens:int)->dict:
        started=time.monotonic()
        try:
            proc=subprocess.run(command(args.runtime,args.model,prompt,tokens),
                                capture_output=True,text=True,encoding="utf-8",
                                errors="replace",timeout=600)
            raw=proc.stdout or ""
            (args.out/("model-attempt-"+str(len(last_out)+1)+".txt")).write_bytes(raw.encode())
            last_out.append({"exit":proc.returncode,
                             "seconds":round(time.monotonic()-started,1)})
            return {"answer":raw,"model_generated":proc.returncode==0}
        except subprocess.TimeoutExpired:
            last_out.append({"exit":"timeout","seconds":600})
            return {"answer":"","model_generated":False}
    report,code=run_trial(original,infer,attempts=args.attempts)
    report.update({"model":args.label,"model_sha256":sha(args.model),
                   "model_execution":last_out})
    if code is not None:
        (args.out/"game.js").write_bytes(code.encode("utf-8"))
    (args.out/"provenance.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
    return 0 if code else 1

if __name__=="__main__":
    raise SystemExit(main())
