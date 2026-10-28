#!/usr/bin/env python3
"""Second Qwen-only refinement of the same independently authored game.

Consumes run 40646692498's genuine Qwen assets and applies only code that
the actual Qwen model writes. Never embeds assistant-supplied game repairs.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib,json,os
from pathlib import Path
import sys
from typing import Any
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from brain_ssd.backend import GenerationRequest
from brain_ssd.local_runtime.pipeline import clean_answer
from generate_luna_original_game import node_check,verify_file
from repair_luna_original_targeted import generate_patches

INPUT=ROOT/"results"/"luna-original-targeted"
OUTPUT=ROOT/"results"/"luna-original-refined"
INPUT_RUN=40646692498
INPUT_STATUS="STATIC_PATCHED_CANDIDATE"
INPUT_PATCHES_REQUIRED=5
PRIOR_PATCHES=5
PATCH_STAGE="keyboard_and_target"

TASKS=[
  {
    "id":"prevent_space_default",
    "start":"document.addEventListener('keydown', (e) => {\n",
    "end":"  if (e.key === 'ArrowRight')",
    "goal": "No Chromium, após clicar no botão START, ele permanece focado. "
            "Pressionar Space pode ativá-lo novamente e reiniciar a partida no meio do pulo. "
            "Reescreva APENAS a abertura do listener document.addEventListener('keydown', (e) => { "
            "incluindo uma instrução que chama e.preventDefault() para Space, ArrowLeft, "
            "ArrowRight e KeyZ pelo e.code, ANTES do if já existente. "
            "Não feche o listener. Não inclua o if ArrowRight, que permanecerá intacto. "
            "Responda somente o cabeçalho do listener e o preventDefault.",
    "requires":("keydown","preventDefault","Space","e.code"),
    "max_tokens":230,
  },
  {
    "id":"nearest_enemy_target",
    "start":"attackTarget = findClosestEnemy();",
    "end":None,
    "allow_statement":True,
    "goal":"O Chromium comprovou que findClosestEnemy NÃO EXISTE no seu código. "
           "Substitua a linha attackTarget = findClosestEnemy(); por UMA instrução "
           "SIMPLES, de no máximo 100 caracteres: atribua a attackTarget o PRIMEIRO "
           "objeto do array enemies cujo atributo e.hp seja MAIOR QUE ZERO, ou null "
           "quando não houver nenhum. Use enemies.find. NÃO calcule distâncias, "
           "NÃO use e.alive (esse atributo não existe), NÃO use findClosestEnemy. "
           "Retorne somente uma instrução JavaScript, sem explicação.",
    "requires":("attackTarget","enemies","hp"),
    "max_tokens":115,
  },

]

def digest(blob:bytes)->str:
    return hashlib.sha256(blob).hexdigest()

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--retries",type=int,choices=(1,2,3),default=2)
    ap.add_argument("--model-file",default="Qwen3-4B-Q4_K_M.gguf")
    args=ap.parse_args()
    if os.name!="nt":
        print("Real Qwen on Windows mandatory",file=sys.stderr)
        return 2
    OUTPUT.mkdir(parents=True,exist_ok=True)
    report={"status":"ERROR","created_utc":datetime.now(timezone.utc).isoformat(),
            "model":args.model_file,"original_run":40636116071,"input_run":INPUT_RUN,
            "gameplay_verified":False,"assistant_gameplay_code_used":False}
    engine=None
    try:
        old=json.loads((INPUT/"provenance.json").read_text(encoding="utf-8"))
        assert old["status"]==INPUT_STATUS and old["patches_accepted"]==INPUT_PATCHES_REQUIRED
        for name in ("index.html","styles.css","game.js"):
            raw=(INPUT/name).read_bytes().replace(b"\r\n",b"\n")
            assert digest(raw)==old["provenance_sha256"][name],name
            if name!="game.js":
                (OUTPUT/name).write_bytes(raw)
        initial=(INPUT/"game.js").read_bytes().replace(b"\r\n",b"\n").decode("utf-8")
        from brain_ssd.chat.runtime import LocalChatRuntime
        engine=LocalChatRuntime(ROOT,profile="equilibrado",model_file=args.model_file)
        def infer(prompt:str,limit:int)->dict[str,Any]:
            reply=engine.core_backend.generate(GenerationRequest(
                prompt=prompt,max_tokens=limit,temperature=0.12))
            if reply.get("return_code")!=0:
                raise RuntimeError("native_model_failure")
            answer=clean_answer(str(reply.get("stdout") or ""))
            return {"answer":answer,"model_generated":bool(answer),
                    "finish_reason":(reply.get("metrics") or {}).get("finish_reason")}
        result,code=generate_patches(initial,infer,tasks=TASKS,attempts=args.retries)
        report.update(result)
        report["model"]=args.model_file
        report["new_patch_count"]=len(TASKS)
        report["total_model_patches"]=PRIOR_PATCHES+report["patches_accepted"]
        report["patch_stage"]=PATCH_STAGE
        if code is None:
            report["status"]="INCOMPLETE"
            return 1
        ok,reason,_=verify_file("game.js",code,js_check=node_check)
        if not ok:
            report["status"]="INCOMPLETE"
            report["review_failure"]=reason
            return 1
        (OUTPUT/"game.js").write_bytes(code.encode("utf-8"))
        report["status"]="STATIC_REFINED_CANDIDATE"
        report["provenance_sha256"]={name:digest((OUTPUT/name).read_bytes())
                                     for name in ("index.html","styles.css","game.js")}
        return 0
    except Exception as exc:
        report["error_type"]=type(exc).__name__
        return 2
    finally:
        if engine is not None:engine.close()
        (OUTPUT/"provenance.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":
    raise SystemExit(main())
