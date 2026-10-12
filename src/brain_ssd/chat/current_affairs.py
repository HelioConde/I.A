"""High-precision trigger for time-sensitive Brazil queries.

No hidden network access: this only explains when permission and recent sources
are needed. Historical or encyclopedic Brazil questions remain normal chat.
"""
from __future__ import annotations

import re
import unicodedata


def needs_brazil_news(question: str) -> bool:
    if not isinstance(question, str):
        return False
    lower = unicodedata.normalize("NFKD", question.casefold())
    lower = "".join(char for char in lower if not unicodedata.combining(char))
    lower = re.sub(r"\s+", " ", lower).strip()
    if not re.search(r"\bbrasil\b", lower):
        return False
    return bool(re.search(
        r"\b(situacao|atualidade|atual|atualmente|hoje|agora|"
        r"noticias?|ultimas?|acontecendo|andando|"
        r"economia|politica|governo|cenario|panorama)\b"
        r"|como\s+esta\b|como\s+anda\b", lower
    ))


def needs_recent_public_sources(question: str) -> bool:
    """Broad recent-news intent; never mistake encyclopedia for live reporting."""
    if not isinstance(question, str):
        return False
    lower = unicodedata.normalize("NFKD", question.casefold())
    lower = "".join(c for c in lower if not unicodedata.combining(c))
    lower = re.sub(r"\s+", " ", lower).strip()
    if re.search(r"\b(?:historia|historico|conceito|o que significa)\b", lower):
        return False
    if needs_brazil_news(question):
        return True
    return bool(re.search(r"\b(?:noticias?|noticiario|novidades|atualizacoes)\b", lower)
                and re.search(r"\b(?:pesquise|pesquisar|busque|busca|procure|sobre|de |do |da |"
                              r"ultimas?|recentes?|hoje|agora|atual)\b", lower))



def time_sensitive_local_intent(question: str) -> str | None:
    """Identify vague daily and live-weather requests before offline Qwen."""
    if not isinstance(question, str):
        return None
    text = unicodedata.normalize("NFKD", question.casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"\s+", " ", text).strip(" ?!.")
    if re.fullmatch(
        r"(?:quais? (?:sao )?(?:as )?informacoes de hoje|o que tem de novo hoje|"
        r"me atualize sobre hoje|me de as informacoes de hoje|"
        r"quais? as novidades de hoje)", text
    ):
        return "ambiguous_today"
    if (re.search(r"\b(?:clima|previsao(?: do tempo)?|tempo)\b", text)
            and re.search(
                r"\b(?:hoje|amanha|agora|esta semana|essa semana|vai ser|vai estar|"
                r"previsao|esta fazendo|estara)\b", text
            )):
        return "live_weather"
    return None

def explicit_web_research(question: str) -> bool:
    """Only an explicit command can request browser consent for general topics."""
    if not isinstance(question, str):
        return False
    simple = unicodedata.normalize("NFKD", question.casefold())
    simple = "".join(ch for ch in simple if not unicodedata.combining(ch)).strip()
    return bool(re.match(
        r"^(?:/pesquisar|pesquise(?:\s+na\s+internet)?|"
        r"busque\s+na\s+(?:internet|web)|procure\s+na\s+web)\s+\S",
        simple,
    ))


def strip_research_command(question: str) -> str:
    """Keep only the topic sent to a provider, with no synthetic system text."""
    if not explicit_web_research(question):
        return question
    trimmed = re.sub(
        r"^\s*(?:/pesquisar|pesquise(?:\s+na\s+internet)?|"
        r"busque\s+na\s+(?:internet|web)|procure\s+na\s+web)"
        r"\s+(?:sobre\s+)?",
        "", question, flags=re.I,
    ).strip()
    return trimmed or question

# Games with frequent patches require a genuinely current news/search provider.
# The no-key 'auto' provider falls back to encyclopedia results outside Brazil;
# it must not present unrelated Wikipedia biographies as "latest updates".
_GAME_RE = re.compile(r"\b(overwatch|valorant|league\s+of\s+legends|lol)\b")
_FRESH_RE = re.compile(
    r"\b(ultim[aos]*|atualizac[a-z]*|notici[a-z]*|recent[a-z]*|hoje|"
    r"agora|patch|patches|novidade[s]?|mudanca[s]?|temporada)\b"
)


def current_game_request(question: str) -> bool:
    if not isinstance(question, str):
        return False
    normalized = unicodedata.normalize("NFKD", question.casefold())
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return bool(_GAME_RE.search(normalized) and _FRESH_RE.search(normalized))


def result_matches_game(question: str, title: str, snippet: str) -> bool:
    """Reject clearly unrelated wiki hits from the current-games router."""
    normalized = unicodedata.normalize("NFKD", question.casefold())
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    target = _GAME_RE.search(normalized)
    if not target:
        return True
    content = unicodedata.normalize("NFKD", (title + " " + snippet).casefold())
    content = "".join(ch for ch in content if not unicodedata.combining(ch))
    name = target.group(1)
    if name in ("lol", "league of legends"):
        return bool(re.search(r"\b(?:league\s+of\s+legends|lol|cblol)\b", content))
    return bool(re.search(r"\b" + re.escape(name) + r"\b", content))
