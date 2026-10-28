#!/usr/bin/env python3
"""Ask *real Qwen* for three small, auditable dash patches to Luna's own game.

No gameplay code is supplied as fallback. Proposed source is never executed
in this script; syntax and safety are checked before isolated Chromium QA.
"""
from __future__ import annotations
import argparse, hashlib, json, os, re, sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from brain_ssd.backend import GenerationRequest
from brain_ssd.local_runtime.pipeline import clean_answer
from generate_luna_original_game import node_check
from install_game_coder_model import MODEL_FILENAME,MODEL_SHA256
from install_windows_chat import verified_file

ORIGINAL=ROOT/"site"/"luna-created"
OUT=ROOT/"results"/"luna-gc-s1-dash"
BLOCKED=re.compile(r"\b(?:eval|Function|fetch|WebSocket|XMLHttpRequest|require|import|Worker|setInterval)\s*\(|"
                   r"\b(?:window|document|localStorage|sessionStorage)\b|https?://",re.I)
GLOBAL_MARKER="let attackTarget = null;"
RIGHT_MARKER="player.vx = 5;"
LEFT_MARKER="player.vx = -5;"

TASKS=[
 {"name":"dash_state","marker":GLOBAL_MARKER,"kind":"after",
  "prompt":"Você é Luna criando o dash de seu jogo autoral de plataforma. "
  "Responda SÓ declaração JavaScript (uma linha), criando com let as variáveis "
  "lastRightTap e lastLeftTap, ambas inicializadas em zero. "
  "Esses marcadores de tempo são necessários para detectar duplo toque. Sem explicação.",
  "required":("let","lastRightTap","lastLeftTap"),"limit":100},
 {"name":"right_dash","marker":RIGHT_MARKER,"kind":"replace",
  "prompt":"Você é Luna, programadora. O jogador já tem input ArrowRight e variáveis globais "
  "lastRightTap e lastLeftTap. Substitua APENAS a instrução player.vx = 5; "
  "por instruções JS que usem performance.now() para detectar dois apertos ArrowRight "
  "em até 260ms. Se a tecla NÃO estiver em repetição (e.repeat), marque último toque "
  "lastRightTap. É OBRIGATÓRIO usar a expressão !e.repeat no teste de duplo toque. O primeiro toque (lastRightTap=0) NÃO pode disparar dash: exija lastRightTap>0. Em duplo toque, player.vx deve ser 14; caso contrário 5. "
  "Não mude y, x, HP, inimigos nem outras teclas. "
  "Retorne SOMENTE código JS substituto, 1 a 4 instruções, sem chaves de if externo.",
  "required":("lastRightTap","performance.now","e.repeat","player.vx"),"limit":190},
 {"name":"left_dash","marker":LEFT_MARKER,"kind":"replace",
  "prompt":"Você é Luna, programadora. O jogador já tem input ArrowLeft e globais lastLeftTap/lastRightTap. "
  "Substitua APENAS player.vx = -5; por JS com performance.now() e e.repeat: "
  "OBRIGATÓRIO ter !e.repeat no código para ignorar tecla repetida, e lastLeftTap>0 para ignorar primeiro toque. Se tocar ArrowLeft duas vezes em até 260ms, usar player.vx=-14, "
  "senão -5. Atualize lastLeftTap apenas quando e.repeat for falso. "
  "Retorne SOMENTE 1-4 instruções JS, sem função, sem if externo, sem explicação.",
  "required":("lastLeftTap","performance.now","e.repeat","player.vx"),"limit":190},
]

def digest(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()

def valid_piece(raw:str,task:dict[str,Any])->tuple[bool,str,str]:
    if not isinstance(raw,str):
        return False,"non_string",""
    piece=raw.strip()
    fenced=re.fullmatch(r"\x60\x60\x60(?:javascript|js)?\s*\n(.*?)\n\x60\x60\x60",
                        piece,re.I|re.S)
    if fenced:piece=fenced.group(1).strip()
    if not 12<=len(piece)<=650 or "\x00" in piece or BLOCKED.search(piece):
        return False,"unsafe_or_invalid_size",""
    missing=[token for token in task["required"] if token not in piece]
    if missing:
        return False,"missing_dash_terms:"+",".join(missing),""
    if task["name"]=="dash_state":
        if "lastRightTap" not in piece or "lastLeftTap" not in piece or "let " not in piece:
            return False,"missing_state",""
    else:
        if "return" in piece or "function " in piece or "=> " in piece or "last" not in piece:
            return False,"invalid_key_handler",""
    return True,"candidate",piece

def patch(source:str,task:dict[str,Any],piece:str)->str:
    marker=task["marker"]
    if source.count(marker)!=1:
        raise ValueError("source_mismatch_"+task["name"])
    if task["kind"]=="after":
        return source.replace(marker,marker+"\n"+piece,1)
    return source.replace(marker,piece,1)

def run(source:str,infer,*,attempts:int=2,syntax_check=node_check)->tuple[dict[str,Any],str|None]:
    if attempts not in (1,2,3):raise ValueError("attempts")
    result={"benchmark":"Luna GC S1 original dash v1","source_sha256":digest(source.encode()),
            "model_authored_game_changes":True,"assistant_gameplay_code_used":False,
            "browser_verified":False,"attempts":[],"status":"INCOMPLETE"}
    current=source
    for task in TASKS:
        accepted=False
        attempts_log=[]
        feedback=""
        for i in range(attempts):
            prompt="/no_think\n"+task["prompt"]+("\nCorreção obrigatória: "+feedback if feedback else "")
            try:
                reply=infer(prompt,task["limit"])
                real=reply.get("model_generated") is True
                raw=str(reply.get("answer") or "")
                ok,reason,fragment=valid_piece(raw,task) if real else (False,"not_real_inference","")
                if reply.get("finish_reason")=="length":
                    ok,reason=False,"native_token_limit"
                if ok:
                    candidate=patch(current,task,fragment)
                    if not syntax_check(candidate):
                        ok,reason=False,"javascript_syntax_error"
                attempts_log.append({"attempt":i+1,"model_generated":real,"accepted":ok,
                                     "reason":reason,"fragment":raw[:850]})
                if ok:
                    current=candidate
                    accepted=True
                    break
                feedback=reason
            except Exception as exc:
                feedback="native_"+type(exc).__name__
                attempts_log.append({"attempt":i+1,"accepted":False,"reason":feedback})
        result["attempts"].append({"task":task["name"],"accepted":accepted,"trials":attempts_log})
        if not accepted:
            return result,None
    result["status"]="STATIC_CANDIDATE"
    result["output_sha256"]=digest(current.encode())
    return result,current

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--attempts",type=int,choices=(1,2,3),default=2)
    p.add_argument("--model-file",default=MODEL_FILENAME)
    args=p.parse_args()
    if os.name!="nt":
        print("Real native Windows GGUF required",file=sys.stderr)
        return 2
    OUT.mkdir(parents=True,exist_ok=True)
    engine=None
    result={"status":"ERROR","created_utc":datetime.now(timezone.utc).isoformat(),
            "model":args.model_file}
    try:
        model_path=ROOT/"models"/args.model_file
        if args.model_file!=MODEL_FILENAME or not verified_file(model_path,sha256=MODEL_SHA256):
            raise ValueError("Model must be authentic pinned Qwen3-4B.")
        provenance=json.loads((ORIGINAL/"provenance.json").read_text(encoding="utf-8"))
        source_bytes=(ORIGINAL/"game.js").read_bytes().replace(b"\r\n",b"\n")
        if digest(source_bytes)!=provenance["files"]["game.js"]["sha256"]:
            raise ValueError("Original independently authored game source mismatch.")
        from brain_ssd.chat.runtime import LocalChatRuntime
        engine=LocalChatRuntime(ROOT,profile="equilibrado",model_file=args.model_file)
        def infer(prompt:str,limit:int):
            response=engine.core_backend.generate(GenerationRequest(
                prompt=prompt,max_tokens=limit,temperature=0.12))
            if response.get("return_code")!=0:
                raise RuntimeError("native_inference_error")
            answer=clean_answer(str(response.get("stdout") or ""))
            return {"answer":answer,"model_generated":bool(answer),
                    "finish_reason":(response.get("metrics") or {}).get("finish_reason")}
        result,source=run(source_bytes.decode("utf-8"),infer,attempts=args.attempts)
        result["model"]=args.model_file
        result["model_sha256"]=MODEL_SHA256
        if source is not None:
            for name in ("index.html","styles.css"):
                (OUT/name).write_bytes((ORIGINAL/name).read_bytes())
            (OUT/"game.js").write_bytes(source.encode("utf-8"))
            return 0
        return 1
    except Exception as exc:
        result["error_type"]=type(exc).__name__
        result["error_reason"]=str(exc)[:180]
        return 2
    finally:
        if engine is not None:engine.close()
        (OUT/"provenance.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",
                                            encoding="utf-8")
        print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":
    raise SystemExit(main())
