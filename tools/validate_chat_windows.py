#!/usr/bin/env python3
"""Run a genuine Windows CPU inference, with a local JSON report."""
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=tuple(PROFILES), default="economia")
    args = parser.parse_args()
    if os.name != "nt":
        print("ATENÇÃO: a validação de Windows precisa ser executada em Windows.")
        return 2
    engine = ChatEngine(lambda: LocalChatRuntime(ROOT, profile=args.profile))
    engine.start()
    report: dict = {"platform": "Windows", "profile": args.profile, "status": "FAILED"}
    try:
        if engine.status()["status"] != "ready":
            raise RuntimeError(engine.status().get("error") or "Falha no preflight")
        started = time.perf_counter()
        response = engine.ask("Olá!", [])
        report.update({
            "status": "PASS" if response["answer"].strip() else "FAIL",
            "question": "Olá!",
            "answer": response["answer"],
            "elapsed_s": round(time.perf_counter() - started, 3),
            "metrics": response["metrics"],
            "inference_verified": engine.status()["inference_verified"],
            "knowledge_available": engine.status().get("knowledge_available"),
            "core_mode": response["core_mode"],
            "note": "Inferência real no Windows; não valida qualidade geral nem leitura física SSD.",
        })
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        engine.close()
    output = ROOT / "results" / "chat_validation" / "latest-local-windows.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
