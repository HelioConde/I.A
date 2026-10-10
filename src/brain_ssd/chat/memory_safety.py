"""Conservative warnings about conflicting *episodic notes*, not fact adjudication.

Human experiences can differ by day, context or speaker. This checker never
deletes a note, chooses a winner or asserts that two memories are false.
It detects one narrow case: same lexical anchors and different weekdays.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from typing import Any

from brain_ssd.chat.episodic import words

_WEEKDAYS = {
    "segunda": "segunda", "terca": "terca", "quarta": "quarta",
    "quinta": "quinta", "sexta": "sexta", "sabado": "sabado", "domingo": "domingo",
}
_WEEKDAY_PHRASE = re.compile(
    r"\b(?:segunda|terca|quarta|quinta|sexta|sabado|domingo)(?:[- ]feira)?\b"
)


def _day_names(text: str) -> frozenset[str]:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    normalized = "".join(c for c in normalized if not unicodedata.combining(c))
    return frozenset(_WEEKDAYS[match.group(0).split("-")[0].split(" ")[0]]
                     for match in _WEEKDAY_PHRASE.finditer(normalized))


@dataclass(frozen=True)
class MemoryWarning:
    source_ids: tuple[str, str]
    category: str = "POSSIBLE_DIFFERENT_WEEKDAY"


def check_memory_ambiguities(episodes: list[dict[str, Any]], *, max_pairs: int = 10
                             ) -> list[MemoryWarning]:
    """Flag weekday variation for strongly overlapping *confirmed* episodes.

    This is a warning to ask for clarification, never a claim of contradiction.
    Cost is bounded to the first 3 recalled notes in ordinary chat.
    """
    if not 1 <= max_pairs <= 30:
        raise ValueError("Limite de avaliação inválido.")
    clean: list[tuple[str, frozenset[str], frozenset[str]]] = []
    for row in episodes[:12]:
        if row.get("source") != "explicit_user" or row.get("confirmed") is not True:
            continue
        identifier, content = row.get("id"), row.get("content")
        if not isinstance(identifier, str) or not isinstance(content, str):
            continue
        weekday = _day_names(content)
        if len(weekday) != 1:
            # An episode describing two different events is already nuanced.
            continue
        anchors = words(content) - set(_WEEKDAYS) - {"feira"}
        clean.append((identifier, anchors, weekday))
    warnings: list[MemoryWarning] = []
    for i, (first, left, day_left) in enumerate(clean):
        for second, right, day_right in clean[i + 1:]:
            if first == second or day_left == day_right:
                continue
            if len(left & right) < 2:
                continue
            warnings.append(MemoryWarning((first, second)))
            if len(warnings) >= max_pairs:
                return warnings
    return warnings


AMBIGUITY_PROMPT = (
    "[ATENÇÃO: estas notas possivelmente descrevem datas/eventos diferentes. "
    "Não escolha uma delas como verdade apenas pela ordem; peça esclarecimento "
    "quando a pergunta não identificar qual evento.]"
)
