#!/usr/bin/env python3
"""Ask genuine local Qwen to fix a real reference-game defect. Do not apply patch."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from brain_ssd.backend import GenerationRequest
from brain_ssd.chat.game_outperform_v1 import run_first_fix
from brain_ssd.local_runtime.pipeline import clean_answer


def main() -> int:
    parser = argparse.ArgumentParser(description="Luna vs reference: evidence-based bugfix trial")
    parser.add_argument("--model-file", default="Qwen3-4B-Q4_K_M.gguf")
    parser.add_argument("--profile", choices=("economia", "equilibrado"), default="equilibrado")
    parser.add_argument("--attempts", type=int, choices=(1, 2, 3), default=2)
    parser.add_argument("--report", type=Path,
                        default=Path("results/game_agent/outperform-touch-v1.json"))
    args = parser.parse_args()
    if os.name != "nt":
        print("This real inference trial requires Windows and installed verified GGUF.", file=sys.stderr)
        return 2
    from brain_ssd.chat.runtime import LocalChatRuntime
    engine = None
    report = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "model": args.model_file,
        "status": "ERROR",
        "code_executed": False,
        "baseline_modified": False,
        "gameplay_improvement_verified": False,
    }
    try:
        game_path = ROOT / "site" / "arcade" / "game.js"
        source = game_path.read_text(encoding="utf-8")
        engine = LocalChatRuntime(ROOT, profile=args.profile, model_file=args.model_file)
        def infer(prompt: str, max_tokens: int) -> dict:
            reply = engine.core_backend.generate(GenerationRequest(
                prompt=prompt, max_tokens=max_tokens, temperature=0.1,
            ))
            if reply.get("return_code") != 0:
                raise RuntimeError("NATIVE_INFERENCE_FAILED")
            answer = clean_answer(str(reply.get("stdout") or ""))
            metrics = reply.get("metrics") or {}
            return {"answer": answer, "model_generated": bool(answer),
                    "finish_reason": metrics.get("finish_reason")}
        report.update(run_first_fix(source, infer, attempts=args.attempts))
        # A single reviewable one-line result contains no secrets or private data.
        if report["status"] == "CANDIDATE_FOR_REVIEW":
            print("MODEL_AUTHORED_CANDIDATE: " + str(report["model_authored_line"]), flush=True)
        return 0 if report["status"] == "CANDIDATE_FOR_REVIEW" else 1
    except Exception as exc:
        report["error_type"] = type(exc).__name__
        return 2
    finally:
        if engine is not None:
            engine.close()
        dest = args.report if args.report.is_absolute() else ROOT / args.report
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
