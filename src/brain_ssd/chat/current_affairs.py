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
