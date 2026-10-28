"""Luna GameDev AI coding checkpoint: small real-model JSON proposals.

Never executes generated code or writes to a game workspace. Syntax checking
uses node --check on a disposable file, with timeout and no generation run.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any, Callable

from brain_ssd.chat.code_studio import ProposalError, parse_proposal, review_proposal

FIXED_TASK = (
    "Desafio de programação de jogo em JavaScript. Produza apenas UM OBJETO JSON válido, "
    "sem markdown e sem texto extra, neste esquema exato: "
    '{"version":1,"goal":"definições de três classes","files":[{"path":"src/classes.js","content":"CÓDIGO JS"}]}. '
    "O conteúdo JavaScript deve definir const HERO_CLASSES com as propriedades melee, ranged e magic. "
    "Cada classe precisa ter hp, damage e speed numéricos positivos. "
    "Use somente JavaScript simples e o objeto const HERO_CLASSES, sem import/export/require, "
    "sem rede ou execução de comandos, sem texto de explicação fora do JSON. "
    "Entregue código pequeno que caiba em até 256 tokens."
)
TARGET_PATH="src/classes.js"
EXPECTED_WORDS=("const", "HERO_CLASSES", "melee", "ranged", "magic", "hp", "damage", "speed")


@dataclass(frozen=True)
class CodingAttempt:
    model_generated: bool
    accepted: bool
    code_syntax_valid: bool
    schema_valid: bool
    semantic_terms: dict[str, bool]
    response_chars: int
    generation_status: str | None
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "model_generated":self.model_generated,
            "accepted":self.accepted,
            "code_syntax_valid":self.code_syntax_valid,
            "schema_valid":self.schema_valid,
            "semantic_terms":dict(self.semantic_terms),
            "response_chars":self.response_chars,
            "generation_status":self.generation_status,
            "reason":self.reason,
        }


def check_js_syntax(code: str, *, node: str = "node") -> bool:
    """Syntax check only: never run generated program or dependency installs."""
    with tempfile.TemporaryDirectory(prefix="luna-syntax-") as folder:
        path=Path(folder)/"candidate.js"
        path.write_text(code,encoding="utf-8")
        try:
            run=subprocess.run([node,"--check",str(path)],capture_output=True,
                               timeout=10,check=False,text=True,encoding="utf-8",errors="replace")
            return run.returncode==0
        except (FileNotFoundError,subprocess.TimeoutExpired,OSError):
            return False


def evaluate_model_answer(answer: str, *, model_generated: bool,
                          generation_status: str | None = None,
                          syntax_checker: Callable[[str],bool] = check_js_syntax) -> CodingAttempt:
    terms={term:False for term in EXPECTED_WORDS}
    if not model_generated:
        return CodingAttempt(False,False,False,False,terms,len(answer),generation_status,"not_real_model")
    try:
        proposal=parse_proposal(answer)
    except ProposalError:
        return CodingAttempt(True,False,False,False,terms,len(answer),generation_status,"malformed_proposal")
    if len(proposal["files"])!=1 or proposal["files"][0]["path"]!=TARGET_PATH:
        return CodingAttempt(True,False,False,True,terms,len(answer),generation_status,"unexpected_files")
    review=review_proposal(proposal)
    code=proposal["files"][0]["content"]
    terms={term:bool(re.search(r"\b"+re.escape(term)+r"\b",code)) for term in EXPECTED_WORDS}
    syntax_ok=syntax_checker(code)
    accepted=(review["status"]=="READY_FOR_HUMAN_REVIEW" and syntax_ok
              and all(terms.values()) and generation_status not in ("truncated","suspected_truncated"))
    return CodingAttempt(True,accepted,syntax_ok,True,terms,len(answer),generation_status,
                         "candidate_ready_for_review" if accepted else "syntax_semantics_or_completeness_failure")


def run_coding_trial(engine: Any, *, trials: int = 2) -> dict[str, Any]:
    """Call the actual chat model. No canned answer and no application of files."""
    if not 1 <= trials <= 3:
        raise ValueError("Trials must be between 1 and 3")
    attempts=[]
    for index in range(trials):
        prompt=FIXED_TASK if index==0 else FIXED_TASK+" Sua tentativa anterior não passou no contrato; devolva apenas JSON válido e curto."
        try:
            result=engine.ask(prompt,[],response_tokens=256)
            real=result.get("mode")!="local_command" and engine.status().get("inference_verified") is True
            attempt=evaluate_model_answer(
                str(result.get("answer","")),
                model_generated=real,
                generation_status=result.get("generation_status"),
            )
            attempts.append(attempt.as_dict())
            if attempt.accepted:
                break
        except Exception as exc:
            attempts.append({"model_generated":False,"accepted":False,
                             "reason":"runtime_"+type(exc).__name__})
    accepted=any(row.get("accepted") for row in attempts)
    return {
        "benchmark":"Luna GameDev Coding Check v1",
        "test_type":"REAL_MODEL_IF_VERIFIED",
        "status":"PASS" if accepted else "FAIL",
        "attempts":attempts,
        "attempt_count":len(attempts),
        "accepted_model_proposal":accepted,
        "question_scope":"one small class-configuration JavaScript file",
        "limitations":"Static syntax and keyword check only, not running generated code or a real game; no claim of autonomous game creation.",
    }
