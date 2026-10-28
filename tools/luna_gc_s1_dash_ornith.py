#!/usr/bin/env python3
"""Ornith 1.5 9B real-inference test on the *same* original Luna GC-style dash.

The game code remains model-authored; this script only orchestrates prompts,
source integrity and syntax validation, never a handcrafted dash fallback.
"""
from __future__ import annotations
import argparse, json, subprocess, hashlib, re
from pathlib import Path
from datetime import datetime, timezone

from luna_gc_s1_dash_trial import run,ORIGINAL,ROOT
from install_ornith_game_model import MODEL_FILE,MODEL_SHA256
from install_windows_chat import verified_file
from brain_ssd.local_runtime.pipeline import clean_answer

OUT=ROOT/"results"/"luna-gc-s1-dash-ornith"

def sha(raw:bytes)->str:
    return hashlib.sha256(raw).hexdigest()

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--runtime",type=Path,required=True)
    p.add_argument("--attempts",type=int,choices=(1,2,3),default=2)
    args=p.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    report={"status":"ERROR","model":"Ornith-1.5-9B-Q4_K_M.gguf",
            "created_utc":datetime.now(timezone.utc).isoformat(),
            "assistant_gameplay_code_used":False}
    try:
        runtime=args.runtime.resolve()
        model=(ROOT/"models"/MODEL_FILE).resolve()
        if not runtime.is_file() or not verified_file(model,sha256=MODEL_SHA256):
            raise ValueError("Ornith GGUF must be SHA-256 verified.")
        original=json.loads((ORIGINAL/"provenance.json").read_text(encoding="utf-8"))
        raw=(ORIGINAL/"game.js").read_bytes().replace(b"\r\n",b"\n")
        if sha(raw)!=original["files"]["game.js"]["sha256"]:
            raise ValueError("Original Qwen game source hash mismatch.")
        def infer(prompt:str,tokens:int):
            # Qwen3.5-based chat template from the model GGUF itself, CPU-only.
            cmd=[str(runtime),"-m",str(model),"-p",prompt,
                 "-n",str(tokens+70),"-c","4096","-t","4",
                 "--temp","0.2","--top-p","0.9",
                 "--no-display-prompt","--simple-io","--no-warmup",
                 "--reasoning","off","--jinja"]
            try:
                reply=subprocess.run(cmd,capture_output=True,text=True,encoding="utf-8",
                                     errors="replace",timeout=400,check=False)
            except subprocess.TimeoutExpired:
                raise RuntimeError("model_timed_out")
            if reply.returncode!=0:raise RuntimeError("model_exit_"+str(reply.returncode))
            answer=clean_answer(reply.stdout or "")
            return {"answer":answer,"model_generated":bool(answer)}
        report,source=run(raw.decode("utf-8"),infer,attempts=args.attempts)
        report["model"]=MODEL_FILE
        report["model_sha256"]=MODEL_SHA256
        report["original_game_author"]="Luna Qwen3-4B"
        report["dash_patch_author"]="Luna Ornith-1.5-9B"
        if source:
            (OUT/"game.js").write_bytes(source.encode("utf-8"))
            for name in ("index.html","styles.css"):
                (OUT/name).write_bytes((ORIGINAL/name).read_bytes().replace(b"\r\n",b"\n"))
            return 0
        return 1
    except Exception as exc:
        report["error_type"]=type(exc).__name__
        report["error_reason"]=str(exc)[:180]
        return 2
    finally:
        (OUT/"provenance.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":
    raise SystemExit(main())
