#!/usr/bin/env python3
"""Real GGUF-vs-GGUF browser-game coding trial; no model output is prewritten."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import subprocess
import tempfile
import time
from pathlib import Path

PROMPT=(
 "Você é Luna GameDev. Responda SOMENTE JavaScript bruto (sem Markdown). "
 "A página contém canvas#game 800x480. Crie um minijogo Canvas 2D independente: "
 "jogador em x=80 y=392 de 28x28, chão y=420, gravidade, ArrowLeft/ArrowRight "
 "movimentam, Space pula apenas do chão, KeyZ ataca inimigos a até 75 pixels "
 "com cooldown 120ms. O inimigo nasce em x=410 y=392 hp=3 e só morre por dano. "
 "Desenhe jogador, solo, inimigo e um cenário original por requestAnimationFrame. "
 "OBRIGATÓRIO criar window.__LUNA_GAMEDEV_QA__={snapshot:()=>({"
 "player:{x:player.x,y:player.y,hp:player.hp},"
 "enemies:enemies.map(e=>({x:e.x,hp:e.hp})),mode:mode})} "
 "após declarar player, enemies e mode. O hook não pode alterar o jogo. "
 "Use literalmente 'ArrowLeft', 'ArrowRight', 'Space', 'KeyZ', "
 "getContext, requestAnimationFrame. "
 "Sem frameworks, recursos externos, import, require, eval, fetch, rede ou HTML."
)
REQUIRED=("getContext","requestAnimationFrame","ArrowLeft","ArrowRight",
          "Space","KeyZ","__LUNA_GAMEDEV_QA__","player","enemies")
DANGEROUS=re.compile(
 r"\b(?:eval|Function|fetch|WebSocket|XMLHttpRequest|Worker|SharedWorker|importScripts)\s*\("
 r"|\b(?:require|import)\s*\(|\b(?:localStorage|sessionStorage|indexedDB)\b|https?://",re.I
)

def sha(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(4*1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()

def extract_llama_cli_source(raw:str,prompt:str|None=None)->str:
    """Strip llama.cpp interactive UI, prompt echo and perf footer.

    Recent llama-cli emits a banner, a shortened copy of our prompt and
    performance statistics even with --simple-io. Those bytes are NOT model
    output, and feeding them to node creates false syntax failures.
    Do not change actual model code or repair it during extraction.
    """
    marker=re.search(r"\n> [^\n]*\.\.\. \(truncated\)\s*\n",raw)
    if marker:
        text=raw[marker.end():]
    elif "Loading model..." in raw:
        # Short prompts are displayed in full, without "(truncated)".
        full_echo="\n> "+prompt+"\n" if prompt is not None else ""
        if not full_echo or full_echo not in raw:
            raise ValueError("cli_output_delimiter_not_found")
        text=raw.split(full_echo,1)[1]
    else:
        return raw.strip()
    perf=re.search(r"\n\[ Prompt:\s*[\d.]+ t/s\s*\|\s*Generation:",text)
    if perf:
        text=text[:perf.start()]
    return text.strip()


def clean(raw:str)->str:
    text=extract_llama_cli_source(raw)
    text=re.sub(r"^<think>.*?</think>\s*","",text,flags=re.I|re.S)
    if "<think>" in text or "</think>" in text:
        raise ValueError("incomplete_reasoning")
    text=re.sub(r"(?:\[end of text\]|</s>|<\|im_end\|>)\s*$","",text).strip()
    fence=chr(96)*3
    match=re.fullmatch(re.escape(fence)+r"(?:js|javascript)?\s*\n(.*?)\n"+re.escape(fence),
                       text,re.I|re.S)
    if match:text=match.group(1).strip()
    if not 250<=len(text)<=30000:raise ValueError("unexpected_output_size")
    if DANGEROUS.search(text) or "<script" in text.lower():raise ValueError("unsafe_code")
    if any(token not in text for token in REQUIRED):raise ValueError("missing_game_contract")
    return text+"\n"

def syntax_valid(code:str)->bool:
    with tempfile.TemporaryDirectory(prefix="luna-native-code-") as folder:
        p=Path(folder)/"game.js"
        p.write_text(code,encoding="utf-8")
        try:
            r=subprocess.run(["node","--check",str(p)],capture_output=True,timeout=10)
            return r.returncode==0
        except (OSError,subprocess.TimeoutExpired):
            return False

def command(runtime:Path,model:Path,prompt:str,tokens:int=2600)->list[str]:
    return [str(runtime),"-m",str(model),"-p",prompt,
            "-n",str(tokens),"-c","4096","-t","4",
            "--temp","0.6","--top-p","0.95","--top-k","20",
            "--no-display-prompt","--simple-io","--no-warmup",
            "--reasoning","off","--jinja"]

def generate(runtime:Path,model:Path,out:Path,label:str,attempts:int=2)->dict:
    if not runtime.is_file() or not model.is_file():
        raise FileNotFoundError("Runtime/quantized GGUF missing")
    if attempts not in (1,2,3):raise ValueError("invalid_attempts")
    out.mkdir(parents=True,exist_ok=True)
    report={"benchmark":"Luna native GameDev v4","model":label,"model_file":model.name,
            "model_sha256":sha(model),
            "prompt_sha256":hashlib.sha256(PROMPT.encode("utf-8")).hexdigest(),
            "source_author":"real local GGUF model","assistant_gameplay_code_used":False,
            "gameplay_verified":False,"accepted_source":False,"attempts":[]}
    feedback=""
    for attempt in range(1,attempts+1):
        prompt=PROMPT+("\nNa tentativa anterior: "+feedback+
                      ". Reescreva o arquivo JS inteiro e válido." if feedback else "")
        started=time.monotonic()
        try:
            proc=subprocess.run(command(runtime,model,prompt),capture_output=True,text=True,
                                encoding="utf-8",errors="replace",timeout=1200)
            raw=proc.stdout or ""
            (out/("attempt-"+str(attempt)+".raw.txt")).write_text(raw,encoding="utf-8")
            if proc.returncode:raise ValueError("runtime_exit_"+str(proc.returncode))
            candidate=clean(raw)
            if not syntax_valid(candidate):raise ValueError("javascript_syntax_error")
            (out/"game.js").write_bytes(candidate.encode("utf-8"))
            report["game_js_sha256"]=hashlib.sha256(candidate.encode("utf-8")).hexdigest()
            report["accepted_source"]=True
            reason="STATIC_CANDIDATE"
        except subprocess.TimeoutExpired:
            reason="native_timeout"
        except (OSError,ValueError) as exc:
            reason=str(exc)[:180]
        report["attempts"].append({"attempt":attempt,"status":reason,
                                   "seconds":round(time.monotonic()-started,1),
                                   "real_model_invoked":True})
        feedback=reason
        if report["accepted_source"]:break
    report["status"]="STATIC_CANDIDATE" if report["accepted_source"] else "INCOMPLETE"
    (out/"provenance.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return report

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--model",type=Path,required=True)
    p.add_argument("--runtime",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--label",choices=("ornith-1.5-9b","qwen3-4b"),required=True)
    p.add_argument("--attempts",type=int,choices=(1,2,3),default=2)
    args=p.parse_args()
    report=generate(args.runtime,args.model,args.out,args.label,args.attempts)
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
    return 0 if report["accepted_source"] else 1

if __name__=="__main__":
    raise SystemExit(main())
