#!/usr/bin/env python3
"""Re-evaluate UNCHANGED real GGUF outputs from run 40653494692.

The first evaluation mistakenly parsed llama.cpp's interactive banner/prompt
as game code. This script downloads no model, performs no inference and never
rewrites the model's JavaScript; it removes only the known CLI envelope.
"""
from __future__ import annotations
import argparse
import hashlib,json
from pathlib import Path
from benchmark_luna_game_models import clean,syntax_valid
from luna_cli_answer_parser import extract_native_answer
from install_game_coder_model import MODEL_SHA256 as QWEN_SHA
from install_ornith_game_model import MODEL_SHA256 as ORNITH_SHA

SOURCE_RUN=40653494692
KNOWN={"ornith-1.5-9b":ORNITH_SHA,"qwen3-4b":QWEN_SHA}

def replay(raw:bytes, source_report:dict, *, label:str, attempt:int)->tuple[dict,str|None]:
    if label not in KNOWN or attempt not in (1,2):
        raise ValueError("unsupported_source_selection")
    if source_report.get("model")!=label or source_report.get("model_sha256")!=KNOWN[label]:
        raise ValueError("source_model_integrity_mismatch")
    original_hash=hashlib.sha256(raw).hexdigest()
    report={"source_run":SOURCE_RUN,"model":label,"attempt":attempt,
            "origin_prompt_sha256":source_report.get("prompt_sha256"),
            "origin_model_sha256":source_report["model_sha256"],
            "origin_raw_sha256":original_hash,
            "actual_model_generated":True,"new_inference_performed":False,
            "assistant_game_code_written":False,"gameplay_verified":False}
    try:
        code=clean(extract_native_answer(raw.decode("utf-8","replace")))
        if not syntax_valid(code):
            raise ValueError("javascript_syntax_error")
        report["status"]="STATIC_CANDIDATE"
        report["code_sha256"]=hashlib.sha256(code.encode()).hexdigest()
        return report,code
    except ValueError as exc:
        report["status"]="INCOMPLETE"
        report["reason"]=str(exc)[:160]
        return report,None

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--artifact-dir",type=Path,required=True)
    p.add_argument("--label",choices=tuple(KNOWN),required=True)
    p.add_argument("--attempt",type=int,choices=(1,2),required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    origin=json.loads((a.artifact_dir/"provenance.json").read_text(encoding="utf-8"))
    raw=(a.artifact_dir/("attempt-"+str(a.attempt)+".raw.txt")).read_bytes()
    report,code=replay(raw,origin,label=a.label,attempt=a.attempt)
    a.out.mkdir(parents=True,exist_ok=True)
    if code is not None:(a.out/"game.js").write_bytes(code.encode("utf-8"))
    (a.out/"provenance.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
    return 0 if code is not None else 1

if __name__=="__main__":
    raise SystemExit(main())
