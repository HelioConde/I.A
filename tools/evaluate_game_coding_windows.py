#!/usr/bin/env python3
"""Measure genuine Luna Qwen game-code generation; never applies files."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))

from brain_ssd.chat.game_coding_trial import run_coding_trial


def main() -> int:
    parser=argparse.ArgumentParser(description="Luna GameDev real Qwen coding ability")
    parser.add_argument("--profile",choices=("economia","equilibrado"),default="economia")
    parser.add_argument("--model-file",default=None,help="GGUF local filename for the comparison; not downloaded")
    parser.add_argument("--trials",type=int,choices=(1,2,3),default=2)
    parser.add_argument("--report",type=Path,default=Path("results/game_agent/latest.json"))
    args=parser.parse_args()
    if os.name!="nt":
        print("Real-Qwen evaluation requires a Windows CPU installation, not a mock.",file=sys.stderr)
        return 2
    from brain_ssd.chat.runtime import LocalChatRuntime
    from brain_ssd.chat.server import ChatEngine
    engine=ChatEngine(lambda:LocalChatRuntime(ROOT,profile=args.profile,model_file=args.model_file))
    output={"status":"ERROR","benchmark":"Luna GameDev Coding Check v1",
            "created_utc":datetime.now(timezone.utc).isoformat(),"profile":args.profile,
            "model_requested":args.model_file or "default_model",
            "inference_verified":False,"code_executed":False,"workspace_modified":False}
    try:
        engine.start()
        if engine.status().get("status")!="ready":
            output["error"]="MODEL_PRECHECK_FAILED"
            return 2
        output["runtime_model"]=engine.status().get("model")
        result=run_coding_trial(engine,trials=args.trials)
        output.update(result)
        output["inference_verified"]=any(a.get("model_generated") for a in result["attempts"])
        return 0 if result["accepted_model_proposal"] else 1
    except Exception as exc:
        output["error_type"]=type(exc).__name__
        return 2
    finally:
        engine.close()
        path=args.report if args.report.is_absolute() else ROOT/args.report
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(json.dumps(output,ensure_ascii=False,indent=2),flush=True)


if __name__=="__main__":
    raise SystemExit(main())
