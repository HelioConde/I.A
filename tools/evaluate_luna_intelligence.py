#!/usr/bin/env python3
"""Evaluate actual Qwen responses through Luna's ChatEngine on synthetic prompts.

Reports are diagnostic, NOT general IQ scores. Scoring uses deliberately narrow
checkable answers; all prompts and generated responses are non-personal fixtures.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import time
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


@dataclass(frozen=True)
class Case:
    ident: str
    category: str
    question: str
    expected: str


CASES = (
    Case("arithmetic", "raciocinio", "Calcule 17 + 8 * 3. Responda somente com o número.", "41"),
    Case("percentage", "raciocinio", "Um produto custa R$ 80 e recebeu desconto de 25%. Qual o preço final em reais? Responda de forma curta.", "60"),
    Case("deduction", "logica", "Todos os blofs são verdes. Nenhum objeto verde é vermelho. Um blof pode ser vermelho? Responda sim ou não.", "nao"),
    Case("python_sum", "programacao", "Em Python, qual saída de print(sum([2, 3, 5]))? Responda só o resultado.", "10"),
    Case("python_error", "programacao", "Em Python, qual é a exceção de x = [1, 2]; print(x[2])? Diga o nome exato da exceção.", "indexerror"),
    Case("grammar", "portugues", "Corrija apenas a concordância: 'Nós vai ao mercado amanhã'.", "nos vamos ao mercado amanha"),
    Case("instruction", "instrucoes", "Responda somente com a palavra AZUL. Não acrescente mais nada.", "azul"),
    Case("unknown", "incerteza", "Uma pessoa guardou uma senha secreta, mas não informou nenhum dígito. Qual é a senha? Evite inventar um valor.", "nao_informado"),
)

# This tests conversation context (not SQLite persistence, which has separate tests).
CONTEXT_INTRO = "Em um cenário fictício, um dragão chama-se Nimbo e um arqueiro chama-se Taro. Confirme brevemente."
CONTEXT_FOLLOW = "Qual é o nome do dragão mencionado na conversa anterior?"


def normalize(answer: str) -> str:
    plain = unicodedata.normalize("NFKD", answer.casefold())
    return "".join(c for c in plain if not unicodedata.combining(c)).strip()


def judge(case: Case, answer: str) -> tuple[bool, str]:
    a = normalize(answer)
    if not a:
        return False, "empty_answer"
    if case.ident in ("arithmetic", "percentage", "python_sum"):
        target = {"arithmetic": "41", "percentage": "60", "python_sum": "10"}[case.ident]
        # Numeric result must appear as an independent number, not 410/600/100.
        return bool(re.search(r"(?<![0-9])" + target + r"(?:[.,]00)?(?![0-9])", a)), "numeric_answer"
    if case.ident == "deduction":
        affirmative = bool(re.search(r"\bsim\b", a))
        negative = bool(re.search(r"\bnao\b", a) or "impossivel" in a)
        return negative and not affirmative, "logical_entailment_heuristic"
    if case.ident == "python_error":
        return "indexerror" in a, "exception_name"
    if case.ident == "grammar":
        return "nos vamos ao mercado amanha" in re.sub(r"\s+", " ", a), "grammar_phrase"
    if case.ident == "instruction":
        # Strict compliance, extra text or formatting counts as failure.
        return a == "azul", "exact_word"
    if case.ident == "unknown":
        expressions = ("nao sei", "nao foi informad", "nao foi fornecid",
                       "nao e possivel", "nao ha informac", "impossivel determinar",
                       "nao tenho como saber", "desconhecid")
        abstained = any(term in a for term in expressions)
        return abstained and not bool(re.search(r"\b\d{2,}\b", a)), "appropriate_abstention"
    if case.ident == "context":
        return "nimbo" in a, "named_entity_recall"
    raise ValueError("Unknown fixed case: " + case.ident)


def self_test() -> None:
    tests = (
        (CASES[0], "O resultado é 41.", True),
        (CASES[0], "O resultado é 410.", False),
        (CASES[1], "R$ 60,00", True),
        (CASES[2], "Não, é impossível.", True),
        (CASES[2], "Sim, pode.", False),
        (CASES[4], "IndexError: list index out of range", True),
        (CASES[5], "Nós vamos ao mercado amanhã.", True),
        (CASES[6], "AZUL", True),
        (CASES[6], "AZUL!", False),
        (CASES[7], "Não foi informada.", True),
        (CASES[7], "A senha é 1234.", False),
        (Case("context", "contexto", CONTEXT_FOLLOW, "nimbo"), "Nimbo", True),
    )
    for case, reply, expected in tests:
        actual, _ = judge(case, reply)
        assert actual == expected, (case.ident, reply, expected, actual)
    print("Evaluator self-test PASS (" + str(len(tests)) + " fixtures)")


def main() -> int:
    parser = argparse.ArgumentParser(description="Luna real-Qwen intelligence diagnostic")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--profile", choices=("economia", "equilibrado"), default="economia")
    parser.add_argument("--report", type=Path, default=Path("results/chat_validation/intelligence.json"))
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    if os.name != "nt":
        print("Real inference requires Windows with installed GGUF and CPU runtime.", file=sys.stderr)
        return 2

    from brain_ssd.chat.runtime import LocalChatRuntime
    from brain_ssd.chat.server import ChatEngine

    engine = ChatEngine(lambda: LocalChatRuntime(ROOT, profile=args.profile))
    report: dict = {
        "version": 1,
        "benchmark": "Luna Synthetic Ability Check v1",
        "validation_track": "REAL_QWEN_CPU_WINDOWS_RUNNER",
        "model": "Qwen3-0.6B-Q8_0.gguf",
        "platform": "windows-latest",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "score_interpretation": "Small fixed diagnostic, narrow heuristic scoring; not IQ or general intelligence.",
        "scores": {},
        "cases": [],
        "status": "ERROR",
    }
    try:
        engine.start()
        if engine.status().get("status") != "ready":
            raise RuntimeError("Model not ready")
        for case in CASES:
            t0 = time.perf_counter()
            row = {"id": case.ident, "category": case.category, "question": case.question, "expected": case.expected}
            try:
                data = engine.ask(case.question, [], response_tokens=96)
                answer = str(data.get("answer") or "").strip()
                verified = engine.status().get("inference_verified") is True and data.get("mode") != "local_command"
                correct, method = judge(case, answer)
                row.update({
                    "answer": answer, "actual_model_inference": verified,
                    "correct": bool(correct and verified), "judge": method,
                    "elapsed_s": round(time.perf_counter() - t0, 2),
                    "generation_status": data.get("generation_status"),
                })
            except Exception as exc:
                row.update({"correct": False, "actual_model_inference": False, "error_type": type(exc).__name__})
            report["cases"].append(row)
            print(case.ident + ": " + ("PASS" if row["correct"] else "FAIL")
                  + ", model=" + str(row["actual_model_inference"]), flush=True)

        # Memory of an explicitly supplied invented fact in a separate two-turn conversation.
        t0 = time.perf_counter()
        row = {"id": "context", "category": "contexto", "question": CONTEXT_FOLLOW,
               "setup": CONTEXT_INTRO, "expected": "nimbo"}
        try:
            initial = engine.ask(CONTEXT_INTRO, [], response_tokens=96)
            reply = engine.ask(
                CONTEXT_FOLLOW,
                [{"role": "user", "content": CONTEXT_INTRO},
                 {"role": "assistant", "content": initial["answer"]}],
                response_tokens=96,
            )
            answer = str(reply.get("answer") or "").strip()
            verified = bool(engine.status().get("inference_verified")) and (
                initial.get("mode") != "local_command" and reply.get("mode") != "local_command")
            correct, method = judge(Case("context", "contexto", CONTEXT_FOLLOW, "nimbo"), answer)
            row.update({"answer": answer, "actual_model_inference": verified,
                        "correct": bool(correct and verified), "judge": method,
                        "elapsed_s": round(time.perf_counter() - t0, 2),
                        "generation_status": reply.get("generation_status")})
        except Exception as exc:
            row.update({"correct": False, "actual_model_inference": False, "error_type": type(exc).__name__})
        report["cases"].append(row)
        print("context: " + ("PASS" if row["correct"] else "FAIL"), flush=True)
        total = len(report["cases"])
        correct = sum(1 for c in report["cases"] if c.get("correct"))
        inferred = sum(1 for c in report["cases"] if c.get("actual_model_inference"))
        categories = sorted({c["category"] for c in report["cases"]})
        report["scores"] = {
            "total": total, "correct": correct, "incorrect": total - correct,
            "real_model_cases": inferred,
            "score_percent": round(100 * correct / total, 1),
            "by_category": {
                k: {"correct": sum(bool(c.get("correct")) for c in report["cases"] if c["category"] == k),
                    "total": sum(c["category"] == k for c in report["cases"])}
                for k in categories
            },
        }
        report["status"] = "COMPLETED" if inferred == total else "INCOMPLETE"
        lines = [
            "## Luna — real Qwen intelligence diagnostic",
            "",
            "**" + str(correct) + "/" + str(total) + " checks passed** (" + str(report["scores"]["score_percent"]) + "%).",
            "This is a small, synthetic, heuristic evaluation; not IQ or a broad benchmark.",
            "Model-generated cases: " + str(inferred) + "/" + str(total) + ".",
            "", "| Case | Category | Correct? | Real inference? |", "|---|---|---|---|",
        ]
        for c in report["cases"]:
            lines.append("| " + c["id"] + " | " + c["category"] + " | " +
                         ("yes" if c.get("correct") else "no") + " | " +
                         ("yes" if c.get("actual_model_inference") else "no") + " |")
        summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary_file:
            with open(summary_file, "a", encoding="utf-8") as stream:
                stream.write("\n".join(lines) + "\n")
        print("RESULT " + str(correct) + "/" + str(total) + " | " + report["status"], flush=True)
        return 0 if report["status"] == "COMPLETED" else 1
    except Exception as exc:
        report["error_type"] = type(exc).__name__
        print("EVALUATOR ERROR: " + type(exc).__name__, flush=True)
        return 2
    finally:
        engine.close()
        target = args.report if args.report.is_absolute() else ROOT / args.report
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
