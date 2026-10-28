#!/usr/bin/env python3
"""Real Ornith9B fixes two bugs in its own genuinely model-authored JS.

The assistant authors test scaffolding and requirements; every changed JS
substring must be a verified model response. Never insert a canned fix.
"""
from __future__ import annotations
import argparse,hashlib,json,re,subprocess
from pathlib import Path
from benchmark_luna_game_models import command,extract_llama_cli_source,syntax_valid

SOURCE_RUN=40659377921
TASKS=(
 {
  "name":"finite_physics_velocity",
  "original":"player = { x: 80, y: 392, w: 28, h: 28, hp: 3, onGround: true };",
  "requirements":("player","vy","0","hp","onGround","392"),
  "max_tokens":135,
  "prompt":"Luna, você escreveu este código JavaScript do seu próprio jogo:\n"
           "player = { x: 80, y: 392, w: 28, h: 28, hp: 3, onGround: true };\n"
           "O Chromium mostrou player.y = NaN porque game.update() faz player.vy += GRAVITY, "
           "mas vy não foi inicializado. Reescreva SOMENTE essa declaração inteira, "
           "mantendo x, y, w, h, hp e onGround e ADICIONANDO vy: 0 no mesmo objeto. "
           "Uma única linha JavaScript, sem markdown, comentários ou explicação."
 },
 {
  "name":"physical_keyboard_codes",
  "original":"const k = e.key;",
  "requirements":("const k","e.code"),
  "max_tokens":70,
  "prompt":"Luna, no seu jogo, document.addEventListener('keydown', (e) => { "
           "usa a linha 'const k = e.key;' e depois verifica k === 'Space' ou "
           "k === 'KeyZ'. KeyboardEvent.key retorna ' ' ou 'z', não 'Space' nem "
           "'KeyZ', impedindo salto e ataque. Responda SOMENTE a linha JavaScript "
           "substituta correta que atribui a k o campo físico de KeyboardEvent, "
           "sem mudar o nome da variável. Sem markdown e sem explicações."
 },
)

def sha(blob:bytes)->str:
    return hashlib.sha256(blob).hexdigest()

def validate_piece(text:str,task:dict)->tuple[bool,str,str]:
    s=text.strip()
    fence=chr(96)*3
    m=re.fullmatch(re.escape(fence)+r"(?:js|javascript)?\s*\n(.*?)\n"+re.escape(fence),s,re.S|re.I)
    if m:s=m.group(1).strip()
    if "\n" in s or len(s)>260 or len(s)<13 or re.search(r"<|>|https?:|eval|fetch|Function",s,re.I):
        return False,"not_safe_one_line",""
    if any(x not in s for x in task["requirements"]):
        return False,"missing_contract",""
    if task["name"]=="finite_physics_velocity":
        if not re.fullmatch(r"player\s*=\s*\{[^{};]+\}\s*;",s):
            return False,"not_player_object_statement",""
        keys={"x","y","w","h","hp","onGround","vy"}
        if not all(re.search(r"\b"+key+r"\s*:",s) for key in keys):
            return False,"missing_player_property",""
        if not re.search(r"\bvy\s*:\s*0\b",s):
            return False,"nonzero_initial_velocity",""
    else:
        if not re.fullmatch(r"const\s+k\s*=\s*e\.code\s*;",s):
            return False,"wrong_keyboard_event_field",""
    return True,"MODEL_PATCH_CANDIDATE",s

def repair(original:str,generate,*,attempts:int=2)->tuple[dict,str|None]:
    if attempts not in (1,2,3):raise ValueError("invalid_attempts")
    current=original
    evidence=[]
    for task in TASKS:
        if current.count(task["original"])!=1:
            return {"status":"SOURCE_MARKER_MISMATCH","patches":evidence},None
        passed=False
        rows=[]
        for i in range(attempts):
            try:
                response=generate(task["prompt"],task["max_tokens"],task["name"],i+1)
                if response.get("real_model") is not True:
                    ok,reason,source=False,"not_native_inference",""
                else:
                    ok,reason,source=validate_piece(response.get("answer",""),task)
                    if ok:
                        proposed=current.replace(task["original"],source)
                        if not syntax_valid(proposed):
                            ok,reason=False,"whole_game_syntax_error"
                rows.append({"attempt":i+1,"accepted":ok,"reason":reason,
                             "raw_sha256":response.get("raw_sha256"),
                             "model_piece":source if ok else None})
                if ok:
                    current=proposed
                    passed=True
                    break
            except Exception as exc:
                rows.append({"attempt":i+1,"accepted":False,"reason":"native_"+type(exc).__name__})
        evidence.append({"task":task["name"],"accepted":passed,"trials":rows})
        if not passed:break
    good=len(evidence)==len(TASKS) and all(x["accepted"] for x in evidence)
    return {"status":"STATIC_REPAIR" if good else "INCOMPLETE","source_run":SOURCE_RUN,
            "patches":evidence,"patch_count":sum(x["accepted"] for x in evidence),
            "gameplay_verified":False,"assistant_gameplay_code_used":False,
            "source_sha256":sha(original.encode("utf-8")),
            "repaired_sha256":sha(current.encode("utf-8")) if good else None},(current if good else None)

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--model",type=Path,required=True)
    p.add_argument("--runtime",type=Path,required=True)
    p.add_argument("--input",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--attempts",type=int,choices=(1,2,3),default=2)
    args=p.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    original=args.input.read_text(encoding="utf-8")
    def infer(prompt,limit,name,attempt):
        result=subprocess.run(command(args.runtime,args.model,prompt,limit),
                              capture_output=True,text=True,encoding="utf-8",
                              errors="replace",timeout=650)
        raw=result.stdout or ""
        f=args.out/("model-"+name+"-"+str(attempt)+".raw.txt")
        f.write_text(raw,encoding="utf-8")
        return {"answer":extract_llama_cli_source(raw),"real_model":result.returncode==0,
                "raw_sha256":sha(raw.encode("utf-8"))}
    evidence,code=repair(original,infer,attempts=args.attempts)
    evidence.update({"model":"ornith-1.5-9b","model_sha256":sha(args.model.read_bytes()),
                     "original_inference":40653494692,
                     "original_browser_replay":SOURCE_RUN})
    if code is not None:
        (args.out/"game.js").write_bytes(code.encode("utf-8"))
    (args.out/"provenance.json").write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(evidence,ensure_ascii=False,indent=2),flush=True)
    return 0 if code is not None else 1
if __name__=="__main__":raise SystemExit(main())
