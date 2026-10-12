#!/usr/bin/env python3
"""Reproducible baseline measurement; experimental streaming is not invoked."""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from brain_ssd.chat.runtime import LocalChatRuntime, PROFILES
from brain_ssd.chat.server import ChatEngine
from brain_ssd.weight_streaming_runtime import unsupported_inference_message


def build_report(response: dict, *, profile: str, prompt: str, elapsed_s: float) -> dict:
    """Keep prompt parameters and metrics, never generated text, in reports."""
    return {
        "schema": 1, "type": "qwen_runtime_comparison", "status": "baseline_measured",
        "conditions": {
            "baseline_llama_cpp": {
                "status": "measured", "profile": profile,
                "prompt_chars": len(prompt), "temperature": 0.7,
                "max_tokens": response.get("generation_limit"),
                "elapsed_seconds": round(elapsed_s, 6),
                "answer_chars": len(response.get("answer", "")),
                "metrics": response.get("metrics", {}),
                "core_mode": response.get("core_mode"),
            },
            "brain_ssd_weight_streaming": {
                "status": "not_implemented",
                "reason": unsupported_inference_message(),
                "logit_integrity": "not_measured",
                "token_integrity": "not_measured",
            },
        },
        "measurement_limits": {
            "physical_ssd_read": "not measured on native Windows runtime",
            "vram": "not required and not measured by CPU baseline",
            "quality": "not scored; answer text intentionally omitted",
            "cache_state": "OS page cache is uncontrolled; cold/warm state is recorded as unknown",
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Measure conventional local Qwen; no streaming inference.")
    parser.add_argument("--profile", choices=tuple(PROFILES), default="economia")
    parser.add_argument("--model-file", default=None)
    parser.add_argument("--prompt", default="Quanto é 19 mais 23? Responda somente com o resultado.")
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "weight_lab" / "qwen-baseline.json")
    args = parser.parse_args(argv)
    if os.name != "nt":
        parser.exit(2, "This baseline runner is for the native Windows runtime.\n")
    engine = ChatEngine(lambda: LocalChatRuntime(ROOT, profile=args.profile, model_file=args.model_file))
    engine.start()
    try:
        if engine.status().get("status") != "ready":
            raise RuntimeError("Conventional Qwen runtime did not become ready.")
        started = time.perf_counter()
        response = engine.ask(args.prompt, [])
        elapsed = time.perf_counter() - started
        if response.get("mode") == "local_command" or not engine.status().get("inference_verified"):
            raise RuntimeError("No real conventional Qwen inference occurred.")
        report = build_report(response, profile=args.profile, prompt=args.prompt, elapsed_s=elapsed)
    finally:
        engine.close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "output": str(args.output),
                      "experimental": report["conditions"]["brain_ssd_weight_streaming"]["status"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
