#!/usr/bin/env python3
"""Real local Qwen -> small GameDev file drafts. Never executes generated code.

Only an explicit --save-draft saves a complete reviewed candidate to a JSON
under results/game_agent; applying to a game remains a separate approval step.
"""
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
from brain_ssd.chat.game_agent_v2 import run_generation_session, STAGE_TASKS
from brain_ssd.local_runtime.pipeline import clean_answer


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description="Luna GameDev real-model multi-file candidate")
    parser.add_argument("--stage",choices=tuple(STAGE_TASKS),default="s0-plan")
    parser.add_argument("--profile",choices=("economia","equilibrado"),default="equilibrado")
    parser.add_argument("--model-file",default=None,help="Existing GGUF filename within models/ (no download)")
    parser.add_argument("--attempts",type=int,choices=(1,2,3),default=2)
    parser.add_argument("--save-draft",action="store_true",help="Save reviewed JSON draft under results/game_agent, never apply to a game")
    parser.add_argument("--report",type=Path,default=Path("results/game_agent/v2-latest.json"))
    args=parser.parse_args(argv)
    if os.name!="nt":
        print("O modo real exige Windows, GGUF e runtime CPU instalados.",file=sys.stderr)
        return 2

    from brain_ssd.chat.runtime import LocalChatRuntime

    report:dict={
        "benchmark":"Luna GameDev Multi-file Candidate v2",
        "created_utc":datetime.now(timezone.utc).isoformat(),
        "stage":args.stage,"profile":args.profile,"model_requested":args.model_file or "default",
        "status":"ERROR","model_inference_verified":False,
        "code_executed":False,"workspace_modified":False,
    }
    engine=None
    try:
        engine=LocalChatRuntime(ROOT,profile=args.profile,model_file=args.model_file)
        report["runtime_model"]=engine.status()["model"]
        def infer(prompt:str,max_tokens:int)->dict:
            # The chat UI caps response_tokens at 256; this agent uses the
            # native CPU backend directly to permit bounded longer file output.
            measured=engine.core_backend.generate(GenerationRequest(
                prompt=prompt,max_tokens=max_tokens,temperature=0.2,
            ))
            if measured.get("return_code")!=0:
                raise RuntimeError("NATIVE_INFERENCE_FAILED")
            text=clean_answer(str(measured.get("stdout") or ""))
            metrics=measured.get("metrics") or {}
            return {"answer":text,"model_generated":bool(text),
                    "finish_reason":metrics.get("finish_reason")}
        result=run_generation_session(infer,args.stage,attempts_per_file=args.attempts,
                                      include_code=args.save_draft)
        proposal=result.pop("proposal",None)
        report.update(result)
        report["model_inference_verified"]=result["model_inference_attempts"]>0
        if proposal is not None and args.save_draft:
            # Reviewable draft only; never mutate the active game workspace.
            draft=ROOT/"results"/"game_agent"/("draft-"+args.stage+".json")
            draft.parent.mkdir(parents=True,exist_ok=True)
            if draft.exists():
                raise FileExistsError("O rascunho já existe: não será substituído.")
            draft.write_text(json.dumps(proposal,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            report["draft_saved"]=True
            report["draft_name"]=draft.name
        else:
            report["draft_saved"]=False
        return 0 if report["status"]=="CANDIDATE_FOR_HUMAN_REVIEW" else 1
    except Exception as exc:
        report["error_type"]=type(exc).__name__
        return 2
    finally:
        if engine is not None:
            engine.close()
        target=args.report if args.report.is_absolute() else ROOT/args.report
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)


if __name__=="__main__":
    raise SystemExit(main())
