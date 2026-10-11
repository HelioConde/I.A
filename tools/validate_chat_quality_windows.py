#!/usr/bin/env python3
"""Real Qwen quality smoke test on Windows; no history, memory or fake backend.

Run on the user's PC only, after installation. Default report stores no prompts,
answers, private notes, or personal paths. This is a small regression check,
NOT a claim of general factual accuracy or scientific quality.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brain_ssd.chat.runtime import LocalChatRuntime
from brain_ssd.chat.server import ChatEngine


CASES = (
    # Use a free-form question; "O que você consegue fazer?" is a Python
    # /ajuda alias and would falsely pass without testing Qwen inference.
    ("capabilities", "Dê dois exemplos de como uma IA local pode ajudar com programação."),
    ("ssd_ram", "Explique como você usa o SSD e a RAM."),
    ("basic_reasoning", "Quanto é 2 + 2? Responda com o resultado."),
)


def check_response(case: str, answer: str) -> bool:
    content = " ".join(answer.casefold().split())
    if not content or content.strip(" .!?") in ("não soube", "não sei", "nao soube", "nao sei"):
        return False
    if content.startswith("não sou um assistente, estou apenas criando"):
        return False
    if case == "capabilities":
        return len(content) >= 50 and any(word in content for word in ("explicar", "texto", "código", "codigo", "convers", "ajudar", "program"))
    if case == "ssd_ram":
        return len(content) >= 60 and "ssd" in content and "ram" in content
    if case == "basic_reasoning":
        return "4" in content
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Real Windows Qwen quality smoke test")
    parser.add_argument("--profile", choices=("economia", "equilibrado"), default="economia")
    parser.add_argument("--include-answers", action="store_true",
                        help="Print and save the generated answers locally (opt-in)")
    args = parser.parse_args()
    if os.name != "nt":
        print("Este teste exige Windows com Qwen3 real e llama.cpp instalados.")
        return 2
    engine = ChatEngine(lambda: LocalChatRuntime(ROOT, profile=args.profile))
    report = {"platform": "Windows", "profile": args.profile, "cases": [], "status": "FAIL"}
    answers = []
    try:
        engine.start()
        if engine.status()["status"] != "ready":
            report["error_type"] = "PreflightFailed"
            return 1
        report["knowledge_available"] = bool(engine.status().get("knowledge_available"))
        for name, question in CASES:
            # Fresh context on purpose: do not contaminate prompts with past
            # non-answers and never access the user's personal history.
            try:
                data = engine.ask(question, [])
                answer = data["answer"].strip()
                answers.append(answer)
                item = {
                    "case": name, "chars": len(answer),
                    "passed_heuristic": check_response(name, answer) and data.get("mode") != "local_command",
                    "inference_verified": bool(engine.status().get("inference_verified")),
                    "model_generated": data.get("mode") != "local_command",
                    "sources_from_ssd": int(data.get("sources_from_ssd") or 0),
                }
                if args.include_answers:
                    item["answer"] = answer
                report["cases"].append(item)
            except Exception as exc:
                report["cases"].append({
                    "case": name, "passed_heuristic": False, "error_type": type(exc).__name__
                })
        unique = len({answer.casefold().strip() for answer in answers}) == len(CASES)
        report["distinct_answers"] = unique
        report["status"] = ("PASS" if unique and all(item["passed_heuristic"] for item in report["cases"]) else "FAIL")
        report["note"] = (
            "Heuristicas simples para detectar não-respostas e repetição; "
            "não comprovam precisão factual nem ganho do Brain-SSD em relação ao Qwen."
        )
        return 0 if report["status"] == "PASS" else 1
    finally:
        engine.close()
        output = ROOT / "results" / "chat_validation" / "latest-quality-windows.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    raise SystemExit(main())
