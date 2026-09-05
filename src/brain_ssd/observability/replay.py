from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from brain_ssd.observability.events import BrainEvent


MIB = 1024**2
SOURCE_PATTERN = re.compile(r"\[SOURCE:\s*([^\]]+)\]\s*(.*?)(?=\n\n\[SOURCE:|\Z)", re.DOTALL)


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"result must be a JSON object: {path}")
    return payload


def phase_catalog(root: Path) -> list[dict[str, Any]]:
    phases = [
        ("1", "CPU Core", "results/baseline_cold_5x.json", "Core CPU-only executou dentro do envelope de memória."),
        ("2", "Storage Brain", "results/phase2/analysis_v2.json", "mmap manteve memória proporcional às páginas tocadas."),
        ("2.5", "Page Refinement", "results/phase2_5/analysis.json", "1 MiB logical / 4 MiB extent tornou-se o baseline equilibrado."),
        ("3", "Router / Gating", "results/phase3/summary.json", "Router e Gate ativaram uma pequena fração do cérebro."),
        ("3.5", "Recall Shield", "results/phase3_5/summary.json", "Recuperação progressiva aumentou recall com custo adicional."),
        ("3.75", "Semantic Rescue", "results/phase3_75/summary.json", "HYBRID + TF-IDF melhorou recall, precisão e esparsidade."),
        ("4A", "Cognitive Cache", "results/phase4a/summary.json", "Cache cognitivo venceu LRU logicamente em condições específicas."),
        ("4B", "Physical Residency", "results/phase4b/summary.json", "KernelOnly venceu o controle físico agressivo."),
        ("4C", "Memory Pressure", "results/phase4c/summary.json", "COLD pressure-aware ajudou apenas sob pressão específica."),
        ("4D", "Real Knowledge", "results/phase4d/end-to-end.json", "O primeiro pipeline real end-to-end passou."),
    ]
    result = []
    for phase, name, relative, proof in phases:
        result.append({"phase": phase, "name": name, "status": "COMPLETE" if (root / relative).is_file() else "UNVERIFIED", "proof": proof, "source": relative})
    status_path = root / "results/phase4e/STATUS.md"
    status = status_path.read_text(encoding="utf-8") if status_path.is_file() else ""
    result.append({
        "phase": "4E",
        "name": "Physical Validation",
        "status": "NEXT" if "NOT EXECUTED" in status and "NOT TESTED" in status else "UNVERIFIED",
        "proof": "Validação física TARGET_8GB preparada; execução ainda não realizada.",
        "source": "results/phase4e/STATUS.md",
    })
    phase4ew_summary = root / "results/phase4ew/summary.json"
    phase4ew_status = "IN PROGRESS"
    phase4ew_proof = "Matriz Windows intermediária preparada; não equivale à Fase 4E canônica."
    if phase4ew_summary.is_file():
        try:
            phase4ew = json.loads(phase4ew_summary.read_text(encoding="utf-8"))
            phase4ew_status = str(phase4ew.get("status", "IN PROGRESS"))
            phase4ew_proof = f"Windows Native Validation: {phase4ew_status}; canonical Phase 4E = false."
        except (OSError, ValueError, TypeError):
            phase4ew_status = "UNVERIFIED"
    result.append({
        "phase": "4E-W",
        "name": "Windows Native Validation",
        "status": phase4ew_status,
        "proof": phase4ew_proof,
        "source": "results/phase4ew/summary.json",
    })
    return result


def _snippets(context_text: str) -> dict[str, str]:
    return {
        record_id.strip(): " ".join(text.strip().split())[:280]
        for record_id, text in SOURCE_PATTERN.findall(context_text or "")
    }


def _source_label(record_id: str, text: str) -> str:
    lower = text.lower()
    if "sqlite" in lower:
        return "SQLite documentation"
    if "python" in lower or record_id:
        return "Python documentation"
    return "Official documentation snapshot"


def phase4d_replay_events(result_path: Path, root: Path, query_id: str | None = None) -> tuple[list[BrainEvent], list[dict[str, Any]], str]:
    result_path = result_path.resolve()
    end_to_end = _load(result_path)
    if "runs" not in end_to_end:
        raise ValueError("Phase 4D replay currently expects end-to-end.json")
    retrieval_path = result_path.with_name("retrieval-only.json")
    if not retrieval_path.is_file():
        raise FileNotFoundError(f"missing Phase 4D companion file: {retrieval_path}")
    retrieval = _load(retrieval_path)

    runs = [run for run in end_to_end.get("runs", []) if run.get("variant") == "brain_ssd"]
    if query_id:
        runs = [run for run in runs if run.get("query_id") == query_id]
    if not runs:
        raise ValueError(f"no Brain-SSD Phase 4D run found for query_id={query_id!r}")
    run = runs[0]
    query_id = str(run.get("query_id", "phase4d-replay"))

    rows = [
        row for row in retrieval.get("rows", [])
        if row.get("query_id") == query_id and row.get("layout") == "semantic" and row.get("retrieval_mode") == "brain"
    ]
    if not rows:
        raise ValueError(f"no semantic Brain retrieval row found for {query_id}")
    row = rows[0]

    manifest_path = root / "brain_data/real_knowledge/semantic/manifest.json"
    manifest = _load(manifest_path) if manifest_path.is_file() else {}
    total_pages = int(manifest.get("page_count") or 0)
    total_bytes = int(manifest.get("corpus_size_bytes") or 0)
    active_pages = list(row.get("activated_pages") or [])
    active_bytes = int(row.get("active_brain_bytes") or 0)
    context = row.get("context") or {}
    run_context = run.get("context") or {}
    storage = row.get("storage") or {}
    timings = row.get("timing_ms") or {}
    metrics = run.get("metrics") or {}
    score = run.get("score") or {}
    snippets = _snippets(str(context.get("text") or ""))
    record_ids = list(context.get("source_ids") or row.get("record_ids") or [])
    selected_ids = list(run_context.get("source_ids") or record_ids)
    base = time.time()
    run_id = f"phase4d-{query_id}"
    common = {"run_id": run_id, "query_id": query_id, "demo_data": False}

    def event(offset_ms: float, event_type: str, component: str, status: str, **kwargs) -> BrainEvent:
        return BrainEvent(event_type=event_type, component=component, status=status, timestamp=base + offset_ms / 1000, **common, **kwargs)

    routing_ms = float(timings.get("routing") or 0)
    storage_ms = float(timings.get("storage") or 0)
    context_ms = float(timings.get("context_build") or 0)
    retrieval_ms = float(timings.get("retrieval_total") or routing_ms + storage_ms + context_ms)
    ttft_ms = float(metrics.get("ttft_ms") or 0)
    latency_ms = float(metrics.get("latency_ms") or 0)
    generation_ms = max(0.0, latency_ms - ttft_ms)
    cursor = 0.0
    events: list[BrainEvent] = [event(cursor, "QUERY_RECEIVED", "INPUT", "SUCCESS", payload_summary={"query": row.get("query", "Query text unavailable")})]
    cursor += 0.01
    events.append(event(cursor, "REFLEX_SKIPPED", "REFLEX", "SKIPPED", payload_summary={"reason": "Phase 4D has no ReflexCore"}))
    events.append(event(cursor, "ROUTER_STARTED", "ROUTER", "RUNNING"))
    cursor += routing_ms
    events.append(event(cursor, "ROUTER_CANDIDATES", "ROUTER", "INFO", metrics={"candidate_count": int(row.get("record_retrieved") or len(record_ids))}, payload_summary={"retrieval_mode": row.get("retrieval_mode"), "layout": row.get("layout")}))
    events.append(event(cursor, "ROUTER_COMPLETED", "ROUTER", "SUCCESS", duration_ms=routing_ms, metrics={"record_recall": (row.get("record_true_positive") or 0) / max(1, row.get("record_expected") or 0)}))
    events.append(event(cursor, "GATE_STARTED", "GATE", "RUNNING"))
    for page_id in active_pages:
        events.append(event(cursor, "PAGE_ACTIVATED", "BRAIN", "SUCCESS", payload_summary={"page_id": page_id, "domain": "REAL KNOWLEDGE", "topic": "Python / SQLite documentation", "reasons": ["Record retrieval mapped to this page"], "provenance": ["PHASE4D_REPLAY"], "scores": {}}))
    events.append(event(cursor, "GATE_COMPLETED", "GATE", "SUCCESS", metrics={"active_brain_bytes": active_bytes, "total_brain_bytes": total_bytes, "active_pages": len(active_pages), "total_pages": total_pages}))
    events.append(event(cursor, "STORAGE_READ_STARTED", "STORAGE", "RUNNING"))
    cursor += storage_ms
    physical_bytes = int(storage.get("physical_read_bytes") or 0)
    events.append(event(cursor, "STORAGE_READ_COMPLETED", "STORAGE", "SUCCESS", duration_ms=storage_ms, metrics={"logical_bytes": int(storage.get("logical_page_bytes") or active_bytes), "physical_bytes": physical_bytes, "cache_state": "WARM" if physical_bytes == 0 else "COLD/BEST_EFFORT", "major_faults": storage.get("major_faults") if storage.get("major_faults") is not None else metrics.get("major_page_faults"), "minor_faults": storage.get("minor_faults") if storage.get("minor_faults") is not None else metrics.get("minor_page_faults")}))
    for record_id in selected_ids:
        excerpt = snippets.get(record_id, "Trecho não incluído neste resultado canônico.")
        events.append(event(cursor, "KNOWLEDGE_RECORD_SELECTED", "CONTEXT", "SUCCESS", payload_summary={"record_id": record_id, "source": _source_label(record_id, excerpt), "section": "KnowledgeRecord", "excerpt": excerpt, "score": None, "reason": "Selected by Phase 4D retrieval"}))
    events.append(event(cursor, "CONTEXT_BUILD_STARTED", "CONTEXT", "RUNNING"))
    cursor += context_ms
    records_retrieved = int(row.get("record_retrieved") or len(record_ids))
    events.append(event(cursor, "CONTEXT_BUILD_COMPLETED", "CONTEXT", "SUCCESS", duration_ms=context_ms, metrics={"tokens": int(run_context.get("estimated_tokens") or context.get("estimated_tokens") or 0), "token_budget": int((retrieval.get("configuration") or {}).get("context_budget_tokens") or 2048), "bytes": int(run_context.get("bytes") or context.get("bytes") or 0), "records_used": len(selected_ids), "records_discarded": max(0, records_retrieved - len(selected_ids)), "records_retrieved": records_retrieved, "records_expected": int(row.get("record_expected") or 0)}))
    events.append(event(cursor, "CORE_STARTED", "CORE", "RUNNING", metrics={"model": "Qwen3-0.6B Q8_0", "mode": "CPU ONLY"}))
    events.append(event(cursor, "CORE_PROMPT_PROCESSING", "CORE", "RUNNING"))
    cursor += ttft_ms
    events.append(event(cursor, "CORE_GENERATING", "CORE", "RUNNING"))
    cursor += generation_ms
    events.append(event(cursor, "CORE_COMPLETED", "CORE", "SUCCESS" if run.get("return_code") == 0 else "ERROR", duration_ms=latency_ms, metrics={"model": "Qwen3-0.6B Q8_0", "mode": "CPU ONLY", "ttft_ms": metrics.get("ttft_ms"), "tokens_per_second": metrics.get("tokens_per_second"), "input_tokens": int(run_context.get("estimated_tokens") or 0), "output_tokens": metrics.get("generated_tokens"), "total_latency_ms": metrics.get("latency_ms"), "cpu_average_percent": metrics.get("cpu_percent_avg_single_core_scale"), "cpu_peak_percent": metrics.get("cpu_percent_max_single_core_scale"), "ram_bytes": metrics.get("rss_bytes_max"), "pss_bytes": metrics.get("pss_bytes_max"), "anonymous_bytes": metrics.get("anonymous_bytes_max"), "file_backed_bytes": metrics.get("rss_file_bytes_max"), "threads_used": 4, "threads_total": None}))
    events.append(event(cursor, "PRESSURE_CHANGED", "RESOURCES", "INFO", metrics={"pressure": "UNKNOWN"}))
    quality_status = "OK" if run.get("return_code") == 0 else "ERROR"
    events.append(event(cursor, "ANSWER_READY", "ANSWER", "SUCCESS" if quality_status == "OK" else "ERROR", payload_summary={"answer": run.get("answer", "Answer unavailable")}, metrics={"required_fact_score": score.get("required_fact_score"), "source_correct": score.get("source_correct"), "quality_status": quality_status}))
    data_source = f"PHASE 4D REPLAY · {result_path.name} · {query_id}"
    return events, phase_catalog(root), data_source
