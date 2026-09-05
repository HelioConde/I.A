from __future__ import annotations

from pathlib import Path

import pytest

from brain_ssd.context_distillation import (
    ContextDistiller,
    RecordPruner,
    context_fact_recall,
    evidence_units,
    oracle_minimal_context,
)
from brain_ssd.local_runtime.phase4fw import BUDGETS, ENVIRONMENT, EXPERIMENT, deterministic_matrix_order


ROOT = Path(__file__).resolve().parents[1]


def record(record_id: str, text: str, page: int = 1) -> dict:
    return {"record_id": record_id, "source_id": record_id, "page_id": page, "title": "Thread safety", "section": "API", "text": text, "length": len(text.encode())}


def test_identity_is_windows_experimental_not_canonical() -> None:
    assert EXPERIMENT == "PHASE_4F_W"
    assert ENVIRONMENT == "WINDOWS_NATIVE_FUNCTIONAL"
    source = (ROOT / "src/brain_ssd/local_runtime/phase4fw.py").read_text(encoding="utf-8")
    assert '"phase4f_windows_experimental": True' in source
    assert '"phase4f_canonical": False' in source


def test_v0_builder_source_was_not_changed_by_phase4fw() -> None:
    source = (ROOT / "src/brain_ssd/record_retrieval.py").read_text(encoding="utf-8")
    assert "class ContextBuilder:" in source
    assert "ContextBuilderV1" not in source


def test_evidence_units_preserve_code_block_and_provenance() -> None:
    value = record("r1", 'Thread safety\n\n>>> cur.execute("SELECT ?", (year,))\n... print(year)')
    units = evidence_units(value)
    assert units[-1].kind == "code_block"
    assert units[-1].record_id == "r1" and units[-1].page_id == 1
    assert "cur.execute" in units[-1].text


def test_distiller_is_extractive_and_preserves_source_marker() -> None:
    records = [record("r1", "Use parameter substitution. A placeholder binds a value safely. Extra unrelated sentence."), record("r2", "The moon is visible at night.")]
    result = ContextDistiller(128).build("How does a placeholder bind a parameter?", records, {"r1": 1.0, "r2": 0.1})
    assert "[SOURCE: r1]" in result["text"]
    assert all(item["text"] in next(row["text"] for row in records if row["record_id"] == item["record_id"]) for item in result["provenance"])


def test_distiller_budget_selects_units_not_prefix_truncation() -> None:
    text = "Irrelevant introduction. " + "Useful placeholder parameter substitution sentence. " * 5
    result = ContextDistiller(64).build("placeholder parameter", [record("r1", text)], {"r1": 1.0})
    assert result["estimated_tokens"] <= 64
    assert not result["text"].endswith("Useful place")


def test_deduplication_marks_removed_tokens() -> None:
    sentence = "Use a placeholder and parameter substitution for safe SQL execution."
    result = ContextDistiller(256).build("safe placeholder SQL", [record("r1", sentence), record("r2", sentence, 2)], {"r1": 1, "r2": .9})
    assert result["duplicate_tokens_removed"] > 0
    assert len(result["records_retained"]) == 1


def test_record_pruner_protects_unique_query_evidence() -> None:
    records = [record("r1", "question mark placeholder"), record("r2", "SQLITE_BUSY locked file"), record("r3", "generic sqlite information")]
    result = RecordPruner(1).prune("placeholder and SQLITE_BUSY", records, {"r1": .9, "r2": .8, "r3": 1.0})
    assert {"r1", "r2"}.issubset(set(result["retained_record_ids"]))
    assert any(item["contains_unique_evidence"] for item in result["contribution"])


def test_context_and_answer_fact_recall_are_separate_metrics() -> None:
    result = context_fact_recall("The default is SQLITE_BUSY.", [["sqlite_busy"], ["timeout"]])
    assert result["recall"] == 0.5
    source = (ROOT / "src/brain_ssd/local_runtime/phase4fw.py").read_text(encoding="utf-8")
    assert '"context_fact_recall"' in source and '"answer_fact_recall"' in source


def test_oracle_is_evaluation_only_and_uses_minimal_units() -> None:
    records = [record("r1", "The unrelated first fact. SQLITE_BUSY is returned by default."), record("r2", "Use sqlite3_busy_timeout to wait."), record("r3", "Noise only.")]
    query = {"required_fact_groups": [["sqlite_busy"], ["sqlite3_busy_timeout"]], "expected_record_ids": ["r1", "r2"]}
    oracle = oracle_minimal_context(query, records)
    assert oracle["evaluation_only"] is True and oracle["oracle_runtime_allowed"] is False
    assert oracle["context_fact_recall"] == 1.0
    assert "Noise only" not in oracle["text"]


def test_budget_matrix_matches_protocol() -> None:
    assert BUDGETS == (256, 384, 512, 768, 1024, 1280, 1536)


def test_randomization_is_deterministic() -> None:
    items = list(range(50))
    assert deterministic_matrix_order(items) == deterministic_matrix_order(items)
    assert deterministic_matrix_order(items) != items


def test_runtime_does_not_use_second_llm_embeddings_cache_or_prefetch() -> None:
    combined = (ROOT / "src/brain_ssd/context_distillation.py").read_text(encoding="utf-8") + (ROOT / "src/brain_ssd/local_runtime/phase4fw.py").read_text(encoding="utf-8")
    for forbidden in ("openai", "sentence_transformers", "cache_prompt=True", "WILLNEED"):
        assert forbidden not in combined
    assert '"prefetch_enabled": False' in combined


def test_runner_supports_dry_run_quick_resume_and_required_modes() -> None:
    source = (ROOT / "tools/run_phase4fw_context_efficiency.py").read_text(encoding="utf-8")
    for flag in ("audit", "baseline", "oracle", "distillation", "budgets", "pruning", "ablation", "quality", "all", "dry-run", "quick", "resume-matrix"):
        assert flag in source


def test_raw_run_schema_preserves_context_answer_and_no_cot() -> None:
    source = (ROOT / "src/brain_ssd/local_runtime/phase4fw.py").read_text(encoding="utf-8")
    assert '"context": context' in source
    assert '"answer": answer' in source
    assert '"chain_of_thought_stored": False' in source


def test_global_default_and_future_phases_remain_unchanged() -> None:
    source = (ROOT / "src/brain_ssd/local_runtime/phase4fw.py").read_text(encoding="utf-8")
    assert '"default_global_changed": False' in source
    assert '"phase5_status": "NOT_STARTED"' in source
    assert '"prefetch_status": "NOT_STARTED"' in source


def test_hud_exposes_context_funnel_and_quality_together() -> None:
    html = (ROOT / "hud/index.html").read_text(encoding="utf-8")
    app = (ROOT / "hud/app.js").read_text(encoding="utf-8")
    state = (ROOT / "src/brain_ssd/hud/state.py").read_text(encoding="utf-8")
    for field in ("funnelBrain", "funnelRecords", "funnelEvidence", "funnelCore", "tokensAvoided", "contextQuality"):
        assert field in html and field in app
    for metric in ("records_retained", "tokens_avoided", "required_facts_found", "grounding"):
        assert metric in state
