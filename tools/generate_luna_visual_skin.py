"""Generate an original visual-only skin with the real Luna GameCoder GGUF.

The assistant writes this evaluator, never the visual source. Authentic model
output is stored verbatim with hashes and is never patched by the evaluator.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import subprocess
import time
from pathlib import Path

from benchmark_luna_game_models import command, syntax_valid, DANGEROUS, sha
from luna_cli_answer_parser import extract_native_answer

ROOT=Path(__file__).resolve().parents[1]
PROMPT=ROOT/"benchmarks/luna_arcade_s1/prompt_visual_skin.txt"

def clean_skin(raw: str) -> str:
    text=raw.strip()
    text=re.sub(r"^<think>.*?</think>\s*","",text,flags=re.I|re.S)
    text=re.sub(r"(?:\[end of text\]|</s>|<\|im_end\|>)\s*$","",text).strip()
    match=re.fullmatch(r"```(?:javascript|js)?\s*\n(.*?)\n```",text,re.I|re.S)
    if match: text=match.group(1).strip()
    if not 350<=len(text)<=20000:raise ValueError("invalid_skin_size")
    if DANGEROUS.search(text) or re.search(r"<script|document\.|\b(?:window\.location|XMLHttpRequest)\b",text,re.I):
        raise ValueError("unsafe_visual_source")
    if not re.search(r"window\.LunaSkin\s*=",text):
        raise ValueError("missing_LunaSkin_assignment")
    if not re.search(r"\bdraw\s*\(\s*ctx\s*,\s*state\s*,\s*time\s*\)",text):
        raise ValueError("missing_draw_contract")
    if not re.search(r"ctx\.(?:fillRect|arc|fill|stroke)\s*\(",text):
        raise ValueError("missing_canvas_drawing")
    if not syntax_valid(text):raise ValueError("javascript_syntax_error")
    return text+"\n"

def generate(runtime:Path,model:Path,out:Path,attempts:int=2)->dict:
    if not runtime.is_file() or not model.is_file():
        raise FileNotFoundError("Missing verified runtime or GGUF")
    out.mkdir(parents=True,exist_ok=True)
    prompt=PROMPT.read_text(encoding="utf-8")
    report={"status":"INCOMPLETE","model_file":model.name,"model_sha256":sha(model),
            "prompt_sha256":hashlib.sha256(prompt.encode()).hexdigest(),
            "visual_source_author":"real local GGUF model",
            "assistant_visual_code_used":False,"model_visual_verified":False,"attempts":[]}
    feedback=""
    for i in range(1,attempts+1):
        full=prompt+("\nCorreção da tentativa anterior: "+feedback+
                     ". Reescreva APENAS o módulo completo." if feedback else "")
        began=time.monotonic()
        try:
            proc=subprocess.run(command(runtime,model,full,tokens=2400,context=4096),
                capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=1200)
            raw=proc.stdout or ""
            (out/f"visual-attempt-{i}.raw.txt").write_text(raw,encoding="utf-8")
            if proc.returncode:raise ValueError(f"runtime_exit_{proc.returncode}")
            source=clean_skin(extract_native_answer(raw))
            (out/"visual.js").write_text(source,encoding="utf-8")
            report["visual_js_sha256"]=hashlib.sha256(source.encode()).hexdigest()
            report["status"]="STATIC_VISUAL_CANDIDATE"
            feedback="ok"
        except subprocess.TimeoutExpired:
            feedback="native_timeout"
        except (ValueError,OSError) as exc:
            feedback=str(exc)[:200]
        report["attempts"].append({"attempt":i,"real_model_invoked":True,
            "status":feedback,"seconds":round(time.monotonic()-began,1)})
        if report["status"]=="STATIC_VISUAL_CANDIDATE":break
    (out/"visual-provenance.json").write_text(
        json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    return report

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--model",type=Path,required=True)
    ap.add_argument("--runtime",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--attempts",type=int,choices=(1,2,3),default=2)
    args=ap.parse_args()
    report=generate(args.runtime,args.model,args.out,args.attempts)
    print(json.dumps(report,ensure_ascii=False))
    return 0 if report["status"]=="STATIC_VISUAL_CANDIDATE" else 1

if __name__=="__main__":
    raise SystemExit(main())
