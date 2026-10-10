"""Provenance-aware *possible* episodic disagreements, never fact arbitration.

Checks narrowly formatted weekdays, calendar dates, clocks and explicitly
marked BRL amounts for confirmed *different* notes with >=2 topic cues.
Different observations can both be valid (e.g. separate appointments).
No automatic overwrite, forgetting, belief updates or confidence labels.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
import re
import unicodedata
from typing import Any

from brain_ssd.chat.episodic import words

_WEEKDAYS = frozenset({
    "segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo",
})
_WEEKDAY_PHRASE = re.compile(
    r"\b(?:segunda|terca|quarta|quinta|sexta|sabado|domingo)(?:[- ]feira)?\b"
)
_CLOCK = re.compile(r"\b(?P<h>[01]?\d|2[0-3])[:h](?P<m>[0-5]\d)\b")
_HOUR_ONLY = re.compile(r"\b(?P<h>[01]?\d|2[0-3])h\b")
_BR_DATE = re.compile(
    r"\b(?P<d>0?[1-9]|[12]\d|3[01])/(?P<m>0?[1-9]|1[0-2])/(?P<y>19\d\d|20\d\d)\b"
)
_ISO_DATE = re.compile(r"\b(?:19|20)\d\d-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])\b")
_BRL = re.compile(r"\br\$\s*(?P<value>\d{1,3}(?:\.\d{3})*(?:,\d{1,2})?|\d{1,10}(?:,\d{1,2})?)\b")


def _plain(text: str) -> str:
    value = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in value if not unicodedata.combining(c))


def _day_names(text: str) -> frozenset[str]:
    return frozenset(m.group(0).split("-")[0].split(" ")[0]
                     for m in _WEEKDAY_PHRASE.finditer(_plain(text)))


def _calendar_dates(text: str) -> frozenset[str]:
    plain = _plain(text)
    valid: set[str] = set()
    for m in _BR_DATE.finditer(plain):
        try:
            valid.add(date(int(m["y"]), int(m["m"]), int(m["d"])).isoformat())
        except ValueError:
            continue
    for m in _ISO_DATE.finditer(plain):
        try:
            valid.add(date.fromisoformat(m.group(0)).isoformat())
        except ValueError:
            continue
    return frozenset(valid)


def _times(text: str) -> frozenset[str]:
    plain = _plain(text)
    times = {f'{int(m["h"]):02d}:{int(m["m"]):02d}' for m in _CLOCK.finditer(plain)}
    # 14h and 14h00 describe the same clock time.
    times.update(f'{int(m["h"]):02d}:00' for m in _HOUR_ONLY.finditer(plain))
    return frozenset(times)


def _prices(text: str) -> frozenset[int]:
    plain = _plain(text)
    values: set[int] = set()
    for m in _BRL.finditer(plain):
        try:
            raw = m["value"].replace(".", "").replace(",", ".")
            cents = Decimal(raw) * 100
            if cents == cents.to_integral_value() and cents <= 10**12:
                values.add(int(cents))
        except (InvalidOperation, OverflowError, ValueError):
            continue
    return frozenset(values)


def _anchors(text: str) -> frozenset[str]:
    # Remove structured fields before comparing the *topic*. This prevents
    # different prices/dates themselves from creating artificial shared cues.
    plain = _plain(text)
    for pattern in (_BRL, _BR_DATE, _ISO_DATE, _CLOCK, _HOUR_ONLY, _WEEKDAY_PHRASE):
        plain = pattern.sub(" ", plain)
    return words(plain) - {"feira"}


@dataclass(frozen=True)
class MemoryWarning:
    source_ids: tuple[str, str]
    category: str = "POSSIBLE_DIFFERENT_WEEKDAY"


_FIELDS = (
    ("POSSIBLE_DIFFERENT_WEEKDAY", _day_names),
    ("POSSIBLE_DIFFERENT_DATE", _calendar_dates),
    ("POSSIBLE_DIFFERENT_TIME", _times),
    ("POSSIBLE_DIFFERENT_PRICE", _prices),
)


def check_memory_ambiguities(episodes: list[dict[str, Any]], *,
                             max_pairs: int = 10) -> list[MemoryWarning]:
    """Warn on different *singular* values for strongly overlapping episodes.

    It is impossible to infer whether notes refer to the same event from text
    alone. Never claim either note is factually false or replace old notes.
    """
    if not 1 <= max_pairs <= 30:
        raise ValueError("Limite de avaliação inválido.")
    clean: list[tuple[str, frozenset[str], str]] = []
    for row in episodes[:12]:
        if row.get("source") != "explicit_user" or row.get("confirmed") is not True:
            continue
        ident, content = row.get("id"), row.get("content")
        if not isinstance(ident, str) or not isinstance(content, str):
            continue
        clean.append((ident, _anchors(content), content))
    warnings: list[MemoryWarning] = []
    for i, (first, anchors1, text1) in enumerate(clean):
        for second, anchors2, text2 in clean[i + 1:]:
            if first == second or len(anchors1 & anchors2) < 2:
                continue
            for category, extractor in _FIELDS:
                a, b = extractor(text1), extractor(text2)
                # Different values may be *additional* appointments; this is
                # merely a prompt to clarify which one the user means.
                if len(a) == 1 and len(b) == 1 and a != b:
                    warnings.append(MemoryWarning((first, second), category))
                    if len(warnings) >= max_pairs:
                        return warnings
    return warnings




def disagrees_with_explicit_cue(query: str, note: str) -> bool:
    """Abstain on an explicit single-value mismatch, never choose a winner.

    If either side contains zero or multiple values of a category, do not
    assert a disagreement. Generic topical cues stay eligible for recall.
    This is conservative *retrieval filtering*, not semantic verification.
    """
    for _, extractor in _FIELDS:
        expected = extractor(query)
        observed = extractor(note)
        if len(expected) == 1 and len(observed) == 1 and expected != observed:
            return True
    return False

AMBIGUITY_PROMPT = (
    "[ATENÇÃO: estas notas podem descrever eventos, datas, horários ou preços "
    "diferentes. Não escolha uma delas como verdade apenas pela ordem; "
    "peça esclarecimento quando a pergunta não identificar qual evento.]"
)
