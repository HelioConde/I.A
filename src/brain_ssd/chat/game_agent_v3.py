"""Luna GameDev v3: generate native source, not JSON-with-escaped-code.

Output is untrusted. It is never executed, only passed to node --check
for syntax validation on a temporary disposable file.
"""
from __future__ import annotations

import re
from typing import Any, Callable

from brain_ssd.chat.game_coding_trial import check_js_syntax

GOAL = (
    "Você é a Luna GameDev, programadora de jogos HTML5 Canvas. "
    "Escreva UM arquivo JavaScript original e válido, sem HTML e sem CSS. "
    "Responda SOMENTE código-fonte JavaScript bruto, sem JSON, Markdown ou explicações. "
    'A página contém <canvas id="game" width="800" height="480"></canvas>. '
    "Implemente: obter canvas e contexto 2D, um objeto player com x, y, vy, altura, "
    "teclado ArrowRight/ArrowLeft, salto Space apenas no chão, gravidade, "
    "colisão com chão em y=420, limpeza e desenho do jogador no Canvas por frame, "
    "loop requestAnimationFrame com delta-time limitado. O código deve rodar com defer. "
    "Sem bibliotecas, import/export, eval, fetch, APIs de rede ou tags script. "
    "Escreva código conciso e funcional; não afirme que rodou testes."
)
CHECKS = ("canvas", "getContext", "player", "ArrowLeft", "ArrowRight", "Space", "requestAnimationFrame")
BLOCKED = re.compile(r"\b(?:eval|Function|fetch|importScripts|WebSocket|XMLHttpRequest|Worker|SharedWorker)\b|"
                     r"\bimport\s*\(|\brequire\s*\(|\blocalStorage\b|\bindexedDB\b", re.I)


def strip_code_wrapper(raw: str) -> str:
    if not isinstance(raw, str) or not raw.strip() or len(raw) > 40000:
        raise ValueError("empty_or_excessive_output")
    text = raw.strip()
    if re.search(r"</?think>", text, re.I):
        raise ValueError("reasoning_tokens_exposed")
    fence = re.fullmatch(r"\x60\x60\x60(?:javascript|js)?\s*\n(.*?)\n\x60\x60\x60",
                         text, re.I | re.S)
    if fence:
        text = fence.group(1).strip()
    if re.search(r"^<script\b|</script>|^\x60", text, re.I):
        raise ValueError("not_standalone_javascript")
    return text


def inspect_code(raw: str, *, syntax_check: Callable[[str], bool] = check_js_syntax) -> dict[str, Any]:
    try:
        source = strip_code_wrapper(raw)
    except ValueError as exc:
        return {"accepted": False, "reason": str(exc), "missing": list(CHECKS), "source": None}
    if BLOCKED.search(source):
        return {"accepted": False, "reason": "prohibited_api", "missing": [], "source": None}
    missing = [token for token in CHECKS if token not in source]
    if missing:
        return {"accepted": False, "reason": "missing_game_features", "missing": missing, "source": None}
    if not syntax_check(source):
        return {"accepted": False, "reason": "javascript_syntax_error", "missing": [], "source": None}
    return {"accepted": True, "reason": "static_candidate_ready", "missing": [], "source": source}


def coding_prompt(feedback: str = "") -> str:
    output = "/no_think\n" + GOAL
    if feedback:
        output += ("\nNa tentativa anterior, o validador encontrou este erro: " +
                   feedback[:200] + ". Reescreva TODO o arquivo em JavaScript válido, sem explicação.")
    return output


def run_native_game_js_trial(generate: Callable[[str, int], dict[str, Any]],
                             *, attempts: int = 2, save_source: bool = False) -> dict[str, Any]:
    if not 1 <= attempts <= 3:
        raise ValueError("attempts must be from 1 to 3")
    feedback = ""
    rows = []
    accepted = None
    for i in range(attempts):
        try:
            result = generate(coding_prompt(feedback), 1200)
            real = result.get("model_generated") is True
            checked = inspect_code(str(result.get("answer") or "")) if real else {
                "accepted": False, "reason": "not_real_inference", "missing": list(CHECKS), "source": None
            }
            if result.get("finish_reason") == "length":
                checked["accepted"] = False
                checked["reason"] = "native_token_limit"
                checked["source"] = None
            rows.append({"attempt": i+1, "model_generated": real, "accepted": checked["accepted"],
                         "reason": checked["reason"], "missing": checked["missing"],
                         "answer_chars": len(str(result.get("answer") or ""))})
            if checked["accepted"]:
                accepted = checked["source"]
                break
            feedback = checked["reason"] + (":" + ",".join(checked["missing"]) if checked["missing"] else "")
        except Exception as exc:
            feedback = "native_runtime_" + type(exc).__name__
            rows.append({"attempt": i+1, "model_generated": False, "accepted": False,
                         "reason": feedback, "missing": [], "answer_chars": 0})
    score = {
        "benchmark": "Luna GameDev Native JavaScript v3",
        "stage": "s1-movement",
        "prompt_format": "RAW_JAVASCRIPT",
        "status": "CANDIDATE_FOR_HUMAN_REVIEW" if accepted is not None else "INCOMPLETE",
        "attempts": rows, "attempt_count": len(rows),
        "accepted_source": accepted is not None, "gameplay_verified": False,
        "code_executed": False, "workspace_modified": False,
        "note": "Only Node JavaScript syntax and static signals, not functional gameplay verification.",
    }
    if accepted is not None and save_source:
        score["source"] = accepted
    return score
