from __future__ import annotations

import math
import re
import time
from dataclasses import asdict, dataclass
from typing import Any, Iterable

from brain_ssd.record_retrieval import ContextBuilder, tokenize


@dataclass(frozen=True)
class EvidenceUnit:
    text: str
    record_id: str
    source_id: str | None
    page_id: int
    title: str
    section: str
    start: int
    end: int
    position: int
    kind: str


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _is_code(text: str) -> bool:
    return bool(re.search(r"(^|\n)\s*(>>>|\.\.\.|\$ |[A-Za-z_]\w*\s*=|\w+\([^)]*\))", text))


def evidence_units(record: dict[str, Any]) -> list[EvidenceUnit]:
    """Split into traceable extractive units without splitting code paragraphs."""
    raw = str(record.get("text") or "")
    paragraphs = [match for match in re.finditer(r"\S(?:.*?\S)?(?=\n\s*\n|\Z)", raw, re.DOTALL)]
    units: list[EvidenceUnit] = []
    position = 0
    for paragraph in paragraphs:
        text = _normalize(paragraph.group())
        pieces: list[tuple[str, int, int, str]] = []
        if _is_code(paragraph.group()) or ContextBuilder.estimate_tokens(text) <= 96:
            pieces.append((text, paragraph.start(), paragraph.end(), "code_block" if _is_code(paragraph.group()) else "paragraph"))
        else:
            cursor = paragraph.start()
            for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z*\"'])", text):
                sentence = sentence.strip()
                if not sentence:
                    continue
                found = raw.find(sentence, cursor)
                start = found if found >= 0 else cursor
                end = start + len(sentence)
                pieces.append((sentence, start, end, "sentence"))
                cursor = end
        for text, start, end, kind in pieces:
            units.append(EvidenceUnit(
                text=text, record_id=str(record["record_id"]), source_id=record.get("source_id"),
                page_id=int(record["page_id"]), title=str(record.get("title") or "Knowledge"),
                section=str(record.get("section") or "KnowledgeRecord"), start=start, end=end,
                position=position, kind=kind,
            ))
            position += 1
    if not units and raw.strip():
        units.append(EvidenceUnit(_normalize(raw), str(record["record_id"]), record.get("source_id"), int(record["page_id"]), str(record.get("title") or "Knowledge"), str(record.get("section") or "KnowledgeRecord"), 0, len(raw), 0, "record"))
    return units


def _jaccard(left: str, right: str) -> float:
    a, b = set(tokenize(left)), set(tokenize(right))
    return len(a & b) / max(1, len(a | b))


class ContextDistiller:
    """Cheap deterministic extractive selector. It never uses evaluation labels."""

    def __init__(self, budget_tokens: int) -> None:
        if budget_tokens < 64:
            raise ValueError("context budget too small")
        self.budget_tokens = budget_tokens

    @staticmethod
    def _score(unit: EvidenceUnit, query: str, record_score: float) -> float:
        query_terms = set(tokenize(query))
        body_terms = set(tokenize(unit.text))
        heading_terms = set(tokenize(f"{unit.title} {unit.section}"))
        lexical = len(query_terms & body_terms) / max(1, len(query_terms))
        heading = len(query_terms & heading_terms) / max(1, len(query_terms))
        structural = 0.06 if unit.kind == "code_block" and any(term in query.casefold() for term in ("code", "api", "placeholder", "execute", "command")) else 0.0
        early = 0.025 / (1 + unit.position)
        return 0.60 * lexical + 0.24 * record_score + 0.10 * heading + structural + early

    def build(self, query: str, records: list[dict[str, Any]], record_scores: dict[str, float] | None = None) -> dict[str, Any]:
        started_wall = time.perf_counter_ns(); started_cpu = time.process_time_ns()
        scores = record_scores or {}
        candidates: list[tuple[float, EvidenceUnit]] = []
        for record in records:
            for unit in evidence_units(record):
                candidates.append((self._score(unit, query, float(scores.get(unit.record_id, 0.0))), unit))
        candidates.sort(key=lambda item: (-item[0], item[1].position, item[1].record_id))
        selected: list[tuple[float, EvidenceUnit, str, int]] = []
        duplicate_tokens_removed = 0
        used = 0
        for score, unit in candidates:
            block = f"[SOURCE: {unit.record_id}] {unit.title} — {unit.section}\n{unit.text}"
            tokens = ContextBuilder.estimate_tokens(block)
            duplicate = next((prior for _, prior, _, _ in selected if _jaccard(prior.text, unit.text) >= 0.90), None)
            if duplicate is not None:
                duplicate_tokens_removed += tokens
                continue
            if used + tokens > self.budget_tokens:
                continue
            selected.append((score, unit, block, tokens)); used += tokens
        # Runtime order is evidence-first and deterministic. An ordering-only
        # ablation can reconstruct original order from provenance positions.
        text = "\n\n".join(item[2] for item in selected)
        retained_records = list(dict.fromkeys(item[1].record_id for item in selected))
        wall_ms = (time.perf_counter_ns() - started_wall) / 1e6
        cpu_ms = (time.process_time_ns() - started_cpu) / 1e6
        return {
            "text": text, "estimated_tokens": used, "bytes": len(text.encode()),
            "source_ids": retained_records, "records_retained": retained_records,
            "records_pruned": [str(record["record_id"]) for record in records if str(record["record_id"]) not in retained_records],
            "sentences_retained": len(selected), "duplicate_tokens_removed": duplicate_tokens_removed,
            "provenance": [{**asdict(unit), "score": score, "estimated_tokens": tokens} for score, unit, _, tokens in selected],
            "distiller_wall_ms": wall_ms, "distiller_cpu_ms": cpu_ms,
            "startup_wall_ms": 0.0, "metadata_bytes": 0,
            "selection_policy": "lexical+frozen_record_score+heading+structural; deterministic; no evaluation labels",
        }


class RecordPruner:
    """Post-retrieval record selector with unique-query-evidence protection."""

    def __init__(self, max_records: int = 3) -> None:
        self.max_records = max_records

    def prune(self, query: str, records: list[dict[str, Any]], record_scores: dict[str, float]) -> dict[str, Any]:
        started_wall = time.perf_counter_ns(); started_cpu = time.process_time_ns()
        query_terms = set(tokenize(query))
        per_record = {str(record["record_id"]): set(tokenize(str(record.get("text") or ""))) & query_terms for record in records}
        protected: set[str] = set()
        for record_id, terms in per_record.items():
            others = set().union(*(value for key, value in per_record.items() if key != record_id)) if len(per_record) > 1 else set()
            if terms - others:
                protected.add(record_id)
        ranked = sorted(records, key=lambda record: (-float(record_scores.get(str(record["record_id"]), 0.0)), -len(per_record[str(record["record_id"])]), str(record["record_id"])))
        retained_ids = list(dict.fromkeys([str(record["record_id"]) for record in ranked if str(record["record_id"]) in protected] + [str(record["record_id"]) for record in ranked]))[:max(self.max_records, len(protected))]
        retained = [record for record in records if str(record["record_id"]) in retained_ids]
        details = [{"record_id": str(record["record_id"]), "score": float(record_scores.get(str(record["record_id"]), 0.0)), "contains_unique_evidence": str(record["record_id"]) in protected, "query_terms": sorted(per_record[str(record["record_id"])])} for record in records]
        return {
            "records": retained, "retained_record_ids": [str(record["record_id"]) for record in retained],
            "pruned_record_ids": [str(record["record_id"]) for record in records if str(record["record_id"]) not in retained_ids],
            "contribution": details, "wall_ms": (time.perf_counter_ns() - started_wall) / 1e6,
            "cpu_ms": (time.process_time_ns() - started_cpu) / 1e6,
        }


def context_fact_recall(text: str, required_fact_groups: list[list[str]]) -> dict[str, Any]:
    lower = text.casefold()
    matched = [any(alternative.casefold() in lower for alternative in group) for group in required_fact_groups]
    return {"matched": matched, "found": sum(matched), "total": len(matched), "recall": sum(matched) / len(matched) if matched else 1.0}


def oracle_minimal_context(
    query_spec: dict[str, Any],
    corpus_records: Iterable[dict[str, Any]],
    *,
    prebuilt_units: list[EvidenceUnit] | None = None,
) -> dict[str, Any]:
    """Evaluation-only approximate set cover over corpus sentences."""
    started = time.perf_counter_ns()
    groups = query_spec.get("required_fact_groups", [])
    all_units = list(prebuilt_units) if prebuilt_units is not None else [unit for record in corpus_records for unit in evidence_units(record)]
    selected: list[EvidenceUnit] = []
    covered: set[int] = set()
    while len(covered) < len(groups):
        best: tuple[float, int, EvidenceUnit, set[int]] | None = None
        for unit in all_units:
            newly: set[int] = set()
            unit_terms = set(tokenize(unit.text))
            lower = unit.text.casefold()
            for index, alternatives in enumerate(groups):
                if index in covered:
                    continue
                for alternative in alternatives:
                    terms = set(tokenize(alternative))
                    if alternative.casefold() in lower or (terms and len(terms & unit_terms) / len(terms) >= 0.75):
                        newly.add(index); break
            if not newly:
                continue
            cost = ContextBuilder.estimate_tokens(unit.text)
            expected_bonus = 0.20 if unit.record_id in query_spec.get("expected_record_ids", []) else 0.0
            value = len(newly) / max(1, cost) + expected_bonus
            candidate = (value, -cost, unit, newly)
            if best is None or candidate[:2] > best[:2]:
                best = candidate
        if best is None:
            break
        unit, newly = best[2], best[3]
        selected.append(unit); covered.update(newly); all_units.remove(unit)
    blocks = [f"[SOURCE: {unit.record_id}] {unit.title} — {unit.section}\n{unit.text}" for unit in selected]
    text = "\n\n".join(blocks)
    return {
        "text": text, "estimated_tokens": ContextBuilder.estimate_tokens(text) if text else 0,
        "bytes": len(text.encode()), "source_ids": list(dict.fromkeys(unit.record_id for unit in selected)),
        "provenance": [asdict(unit) for unit in selected], "context_fact_recall": len(covered) / len(groups) if groups else 1.0,
        "covered_fact_groups": sorted(covered), "required_fact_groups": len(groups),
        "oracle_runtime_allowed": False, "evaluation_only": True,
        "oracle_wall_ms": (time.perf_counter_ns() - started) / 1e6,
    }
