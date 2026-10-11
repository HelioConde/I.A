"""Small high-precision gate for the currently bundled Python/SQLite SSD corpus.

Until the index contains other domains, unqualified everyday questions should
not receive unrelated Python/SQLite documentation. This module never creates
an answer, modifies memory, or claims successful retrieval.
"""
from __future__ import annotations

import re
import unicodedata


_TOPIC = re.compile(
    r"\b(?:python|py3|pip|venv|virtualenv|sqlite|sqlite3|sql|pragma|"
    r"pandas|tkinter|asyncio|pytest|pylint|pipenv|database|"
    r"banco\s+de\s+dados|bancos\s+de\s+dados|consulta\s+sql|"
    r"tabela\s+sql|tabelas\s+sql)\b"
)


def relevant_to_ssd_corpus(question: str) -> bool:
    if not isinstance(question, str):
        return False
    normalized = unicodedata.normalize("NFKD", question.casefold())
    normalized = "".join(x for x in normalized if not unicodedata.combining(x))
    return bool(_TOPIC.search(normalized))
