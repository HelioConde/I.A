"""Tiny auditable PT-BR lexical alias bridge, EXPERIMENTAL only.

Not embeddings, semantic understanding, a thesaurus, or neural plasticity.
Pairs are deliberately narrow, versioned, and never rewrite memory content.
No stemming or fuzzy edit distance: these can silently merge proper names.
"""
from __future__ import annotations

from typing import Iterable

BRIDGE_VERSION = "ptbr-narrow-v1"

# Each group is a closely related usage in common PT-BR. Even these aliases
# are contextual, so this feature must remain opt-in until quality A/B tests.
_GROUPS: tuple[tuple[str, ...], ...] = (
    ("reuniao", "encontro"),
    ("computador", "notebook", "laptop"),
    ("fotografia", "fotografias", "foto", "fotos"),
    ("cachorro", "cachorros", "cao", "caes"),
    ("bicicleta", "bike"),
    ("automovel", "carro"),
    ("celular", "smartphone"),
    ("medicamento", "remedio"),
    ("conserto", "reparo"),
    ("escola", "colegio"),
)

_TO_CANONICAL: dict[str, str] = {}
_BY_CANONICAL: dict[str, tuple[str, ...]] = {}
for _group in _GROUPS:
    canonical = _group[0]
    _BY_CANONICAL[canonical] = _group
    for _word in _group:
        if _word in _TO_CANONICAL:
            raise RuntimeError("Duplicate semantic alias entry")
        _TO_CANONICAL[_word] = canonical


def canonical(token: str) -> str:
    return _TO_CANONICAL.get(token, token)


def concepts(tokens: Iterable[str]) -> frozenset[str]:
    return frozenset(canonical(token) for token in tokens)


def expand_query(tokens: Iterable[str], *, max_terms: int = 96) -> tuple[str, ...]:
    """Expand *specific* query cues into indexable alternatives, bounded."""
    if not 1 <= max_terms <= 128:
        raise ValueError("Invalid alias expansion limit")
    expanded: list[str] = []
    visited: set[str] = set()
    for token in tokens:
        entries = _BY_CANONICAL.get(canonical(token), (token,))
        for term in entries:
            if term not in visited:
                visited.add(term)
                expanded.append(term)
                if len(expanded) >= max_terms:
                    return tuple(expanded)
    return tuple(expanded)
