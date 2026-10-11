"""Describe response completeness separately from successful transport."""
from __future__ import annotations
import re
from typing import Any

_DANGLING = re.compile(
    r"(?:\b(?:a|o|as|os|um|uma|de|do|da|dos|das|e|ou|mas|que|para|por|"
    r"com|sem|porque|quando|onde|como|também|outro|outra|lado)\s*[,;:]?$"
    r"|[,;:=+\-*/(]\s*$)", re.I
)


def classify_completion(text: str, *, max_tokens: int,
                        generated_tokens: int | None = None,
                        finish_reason: str | None = None) -> dict[str, Any]:
    """Distinguish explicit stop, token limit, likely truncation, unknown."""
    if finish_reason == "length":
        return {"status": "truncated", "answer_complete": False,
                "needs_continuation": True, "reason": "token_limit"}
    if finish_reason in ("stop", "eos_token", "stop_sequence"):
        return {"status": "complete", "answer_complete": True,
                "needs_continuation": False, "reason": "model_stop"}
    stripped = text.strip()
    if not stripped:
        return {"status": "unverified", "answer_complete": None,
                "needs_continuation": False, "reason": "empty"}
    unfinished = bool(_DANGLING.search(stripped))
    unfinished |= stripped.count(chr(96) * 3) % 2 != 0
    unfinished |= stripped.count("(") > stripped.count(")")
    unfinished |= not bool(re.search(r"[.!?…»”)}]\s*$", stripped))
    near_limit = (type(generated_tokens) is int and generated_tokens >= max_tokens - 2)
    if near_limit:
        return {"status": "truncated" if unfinished else "suspected_truncated",
                "answer_complete": False if unfinished else None,
                "needs_continuation": True, "reason": "token_limit_probable"}
    if unfinished:
        return {"status": "suspected_truncated", "answer_complete": None,
                "needs_continuation": True, "reason": "unfinished_text"}
    return {"status": "unverified", "answer_complete": None,
            "needs_continuation": False, "reason": "no_native_finish_reason"}


def select_output_budget(question: str, default_tokens: int) -> int:
    """For the 4B CPU model, allow enough text for open-ended questions.

    Purely bounded token logic, no additional threads, model loads or RAM.
    Explicit UI lengths always override this helper in the ChatEngine.
    """
    if default_tokens > 112:
        return default_tokens
    normalized = question.casefold()
    open_ended = re.search(
        r"\b(explique|explica|descreva|compare|crie|escreva|detalhe|"
        r"diferença|diferenca|exemplo|aprendeu|funcionamento|"
        r"maneiras|motivos|razões|razoes)\b", normalized,
    )
    if open_ended or len(question.strip()) > 85:
        return 160
    return default_tokens
