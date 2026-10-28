"""Luna's first *real* improvement challenge: diagnose a bug in the reference game.

The baseline file is read-only; the generated patch is NEVER applied to a game
automatically. A small single-line suggestion is reviewed with a strict contract.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from hashlib import sha256
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any, Callable

BUGGY_LINE = "const end=e=>{e.preventDefault();keys.delete(code);touchDown=false};"
TASK = (
    "Você é Luna, programadora de jogos 2D. O jogo funciona mas o navegador "
    "lança ReferenceError ao soltar um botão virtual no celular. "
    "Dentro de uma função com uma variável local 'code', este é o manipulador original:\n"
    + BUGGY_LINE
    + "\nA variável 'touchDown' não foi declarada. "
    "Corrija APENAS esse manipulador; mantenha e.preventDefault() e keys.delete(code). "
    "Responda com APENAS UMA linha JavaScript de substituição completa, começando com "
    "'const end=', sem markdown, sem explicações e sem criar estado global. "
    "Não inclua código de outros sistemas, APIs de rede ou arquivos."
)
TASK_V2 = TASK + ("\nA nova linha deve ter exclusivamente DUAS operações: cancelar o evento "
                  "com e.preventDefault() e remover a tecla de keys com keys.delete(code). "
                  "Não utilize quaisquer outras variáveis ou efeitos colaterais. "
                  "Use apenas JavaScript em uma linha. Não repita o trecho original. ")
FORBIDDEN = re.compile(r"\b(?:eval|Function|fetch|import|require|WebSocket|XMLHttpRequest|Worker)\s*\(|"
                       r"\b(?:localStorage|sessionStorage|document|window|globalThis)\b", re.I)
ONE_LINE = re.compile(
    r"^\s*const end\s*=\s*e\s*=>\s*\{\s*e\.preventDefault\(\)\s*;\s*"
    r"keys\.delete\(code\)\s*;?\s*\}\s*;?\s*$"
)


def validate_candidate(line: str, source: str, checker: Callable[[str], bool]) -> tuple[bool, str]:
    if source.count(BUGGY_LINE) != 1:
        return False, "reference_source_changed"
    if not isinstance(line, str) or not (10 <= len(line) <= 240):
        return False, "invalid_size"
    if "\n" in line or "\r" in line or "\x00" in line:
        return False, "multiline_or_control"
    if line.strip() == BUGGY_LINE:
        return False, "unchanged_bug"
    if "touchDown" in line:
        return False, "undeclared_reference_remains"
    if FORBIDDEN.search(line):
        return False, "blocked_code"
    if not ONE_LINE.fullmatch(line):
        return False, "handler_contract_mismatch"
    updated = source.replace(BUGGY_LINE, line.strip())
    if not checker(updated):
        return False, "javascript_syntax_error"
    return True, "candidate_requires_browser_review"


def node_syntax(code: str, executable: str = "node") -> bool:
    # Node --check only parses; never evaluates model-produced code.
    with tempfile.TemporaryDirectory(prefix="luna-fix-") as folder:
        path = Path(folder) / "game.js"
        path.write_text(code, encoding="utf-8")
        try:
            result = subprocess.run([executable, "--check", str(path)], check=False,
                                    capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return False


def run_first_fix(
    source: str,
    infer: Callable[[str, int], dict[str, Any]],
    *, attempts: int = 2,
    checker: Callable[[str], bool] = node_syntax
) -> dict[str, Any]:
    """No files written and no generated code executed, even on model success."""
    if attempts not in (1, 2, 3):
        raise ValueError("attempts must be in 1..3")
    original_hash = sha256(source.encode("utf-8")).hexdigest()
    rows: list[dict[str, Any]] = []
    accepted: str | None = None
    feedback = ""
    for i in range(attempts):
        prompt = "/no_think\n" + TASK_V2
        if feedback:
            prompt += "\nTentativa anterior recusada: " + feedback + ". Responda somente a linha corrigida."
        try:
            result = infer(prompt, 210)
            raw = result.get("answer", "")
            verified = result.get("model_generated") is True
            proposed = str(raw).strip()
            if not verified:
                ok, why = False, "not_real_model"
            elif result.get("finish_reason") == "length":
                ok, why = False, "token_limit"
            else:
                ok, why = validate_candidate(proposed, source, checker)
            rows.append({"attempt": i+1, "real_model": verified, "accepted": ok,
                         "reason": why, "chars": len(proposed),
                         "model_output_excerpt": proposed[:400]})
            if ok:
                accepted = proposed
                break
            feedback = why
        except Exception as exc:
            feedback = "runtime_" + type(exc).__name__
            rows.append({"attempt": i+1, "real_model": False, "accepted": False, "reason": feedback})
    return {
        "benchmark": "Luna Outperform Reference — Touch Release Bug v1.1",
        "prompt_revision": 2,
        "baseline_sha256": original_hash,
        "original_line": BUGGY_LINE,
        "status": "CANDIDATE_FOR_REVIEW" if accepted else "INCOMPLETE",
        "attempts": rows,
        "model_authored_line": accepted,
        "code_executed": False,
        "browser_test_executed": False,
        "baseline_modified": False,
        "gameplay_improvement_verified": False,
        "note": "A model-authored patch is not credited until a controlled browser regression passes.",
    }
