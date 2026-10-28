#!/usr/bin/env python3
"""Real native Qwen3 game JavaScript trial, source never executed."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))

from brain_ssd.backend import GenerationRequest
from brain_ssd.chat.game_agent_v3 import run_native_game_js_trial
from brain_ssd.local_runtime.pipeline import clean_answer


def main() -> int:
    parser=argparse.ArgumentParser(description="Luna GameDev raw JavaScript coding trial")
    parser.add_argument("--model-file",default="Qwen3-4B-Q4_K_M.gguf")
    parser.add_argument("--profile",choices=("economia","equilibrado"),default="equilibrado")
    parser.add_argument("--attempts",type=int,choices=(1,2,3),default=2)
    parser.add_argument("--save-draft",action="store_true")
    parser.add_argument("--report",type=Path,default=Path("results/game_agent/qwen-raw-js-v3.json"))
    args=parser.parse_args()
    if os.name!="nt":
        print("Windows real with Qwen GGUF required",file=sys.stderr)
        return 2
    from brain_ssd.chat.runtime import LocalChatRuntime
    engine=None
    report={"benchmark":"Luna GameDev Native JavaScript v3",
            "created_utc":datetime.now(timezone.utc).isoformat(),
            "model":args.model_file,"status":"ERROR",
            "code_executed":False,"workspace_modified":False}
    try:
        engine=LocalChatRuntime(ROOT,profile=args.profile,model_file=args.model_file)
        def infer(prompt:str,max_tokens:int)->dict:
            measured=engine.core_backend.generate(GenerationRequest(
                prompt=prompt,max_tokens=max_tokens,temperature=0.2,
            ))
            if measured.get("return_code")!=0:
                raise RuntimeError("MODEL_FAILED")
            output=clean_answer(str(measured.get("stdout") or ""))
            metrics=measured.get("metrics") or {}
            return {"answer":output,"model_generated":bool(output),
                    "finish_reason":metrics.get("finish_reason")}
        result=run_native_game_js_trial(infer,attempts=args.attempts,save_source=args.save_draft)
        source=result.pop("source",None)
        report.update(result)
        report["draft_saved"]=False
        if source is not None and args.save_draft:
            target=ROOT/"results"/"game_agent"/"draft-s1-movement-v3.js"
            target.parent.mkdir(parents=True,exist_ok=True)
            with target.open("x",encoding="utf-8") as f:
                f.write(source+"\n")
            report["draft_saved"]=True
            report["draft_filename"]=target.name
        return 0 if report["accepted_source"] else 1
    except Exception as exc:
        report["error_type"]=type(exc).__name__
        return 2
    finally:
        if engine is not None:engine.close()
        destination=args.report if args.report.is_absolute() else ROOT/args.report
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)


if __name__=="__main__":
    raise SystemExit(main())
