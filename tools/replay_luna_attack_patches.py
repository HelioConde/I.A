#!/usr/bin/env python3
"""Replay actual Qwen and Ornith combat snippets from immutable run 40656525253.

No new inference and no assistant replacement gameplay code. Earlier evaluator
mistakenly treated the multi-line llama.cpp /no_think prompt echo as JavaScript.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from benchmark_luna_attack_patch import source_region,unwrap_fragment,check_js,GAME_PATH
from luna_cli_answer_parser import extract_native_answer
from install_game_coder_model import MODEL_SHA256 as QWEN_SHA
from install_ornith_game_model import MODEL_SHA256 as ORNITH_SHA

ORIGIN_RUN=40656525253
CHECKSUMS={"ornith-1.5-9b":ORNITH_SHA,"qwen3-4b":QWEN_SHA}

def replay(baseline:str,raw:bytes,origin:dict,label:str,attempt:int):
    if label not in CHECKSUMS or attempt not in (1,2,3):
        raise ValueError("invalid_model_or_attempt")
    if origin.get("model")!=label or origin.get("model_sha256")!=CHECKSUMS[label]:
        raise ValueError("origin_model_pin_mismatch")
    original_hash=hashlib.sha256(baseline.encode("utf-8")).hexdigest()
    if origin.get("source_sha256")!=original_hash:
        raise ValueError("source_baseline_mismatch")
    report={"origin_run":ORIGIN_RUN,"model":label,"attempt":attempt,
            "model_sha256":CHECKSUMS[label],"baseline_sha256":original_hash,
            "raw_stdout_sha256":hashlib.sha256(raw).hexdigest(),
            "inference_now":False,"assistant_gameplay_code_used":False,
            "gameplay_verified":False}
    try:
        body=extract_native_answer(raw.decode("utf-8","replace"))
        frag=unwrap_fragment(body)
        left,_,right=source_region(baseline)
        result=left+frag+right
        if not check_js(result):
            raise ValueError("javascript_syntax_error")
        report["status"]="STATIC_CANDIDATE"
        report["candidate_sha256"]=hashlib.sha256(result.encode()).hexdigest()
        return report,result
    except ValueError as exc:
        report["status"]="INCOMPLETE"
        report["reason"]=str(exc)[:200]
        return report,None

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--artifact-dir",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--label",choices=tuple(CHECKSUMS),required=True)
    p.add_argument("--attempt",choices=(1,2,3),type=int,required=True)
    args=p.parse_args()
    raw=(args.artifact_dir/("model-attempt-"+str(args.attempt)+".txt")).read_bytes()
    origin=json.loads((args.artifact_dir/"provenance.json").read_text(encoding="utf-8"))
    baseline=GAME_PATH.read_text(encoding="utf-8")
    report,game=replay(baseline,raw,origin,args.label,args.attempt)
    args.out.mkdir(parents=True,exist_ok=True)
    if game is not None:
        (args.out/"game.js").write_bytes(game.encode())
    (args.out/"provenance.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
    return 0 if game is not None else 1

if __name__=="__main__":
    raise SystemExit(main())
