from __future__ import annotations

import time

from brain_ssd.observability.events import BrainEvent


MIB = 1024**2


def build_demo_events(base_timestamp: float | None = None) -> list[BrainEvent]:
    """Deterministic fake run used only to validate the HUD presentation."""
    base = base_timestamp or time.time()
    common = {"run_id": "demo-sqlite-python", "query_id": "demo-sqlite-python", "demo_data": True}

    def event(offset_ms: float, event_type: str, component: str, status: str, **kwargs) -> BrainEvent:
        return BrainEvent(
            event_type=event_type,
            component=component,
            status=status,
            timestamp=base + offset_ms / 1000,
            **common,
            **kwargs,
        )

    return [
        event(0, "QUERY_RECEIVED", "INPUT", "SUCCESS", payload_summary={"query": "Como abrir um banco SQLite usando Python?"}),
        event(10, "REFLEX_SKIPPED", "REFLEX", "SKIPPED", payload_summary={"reason": "requires knowledge retrieval"}),
        event(20, "ROUTER_STARTED", "ROUTER", "RUNNING"),
        event(60, "ROUTER_CANDIDATES", "ROUTER", "INFO", metrics={"candidate_count": 8}, payload_summary={"domains": ["Python", "SQLite"]}),
        event(95, "ROUTER_COMPLETED", "ROUTER", "SUCCESS", duration_ms=0.18, metrics={"confidence": 0.91}),
        event(110, "GATE_STARTED", "GATE", "RUNNING"),
        event(140, "PAGE_ACTIVATED", "BRAIN", "SUCCESS", payload_summary={"page_id": 3, "domain": "PROGRAMMING", "topic": "Python", "reasons": ["termo Python", "CURRENT_QUERY"], "provenance": ["CURRENT_QUERY"], "scores": {"lexical": 0.93}}),
        event(170, "PAGE_ACTIVATED", "BRAIN", "SUCCESS", payload_summary={"page_id": 5, "domain": "PROGRAMMING", "topic": "SQLite", "reasons": ["termo SQLite", "SEMANTIC_RESCUE"], "provenance": ["SEMANTIC_RESCUE"], "scores": {"semantic": 0.88}}),
        event(200, "PAGE_ACTIVATED", "BRAIN", "SUCCESS", payload_summary={"page_id": 8, "domain": "SYSTEM", "topic": "Database files", "reasons": ["Record relevante"], "provenance": ["CURRENT_QUERY"], "scores": {"lexical": 0.71}}),
        event(220, "PAGE_INHIBITED", "BRAIN", "SUCCESS", payload_summary={"page_id": 12, "domain": "SCIENCE", "topic": "Biology", "reasons": ["domínio incompatível"]}),
        event(250, "GATE_COMPLETED", "GATE", "SUCCESS", duration_ms=0.14, metrics={"active_brain_bytes": 3 * MIB, "total_brain_bytes": 1024 * MIB, "active_pages": 3, "total_pages": 1024}),
        event(270, "STORAGE_READ_STARTED", "STORAGE", "RUNNING"),
        event(390, "STORAGE_READ_COMPLETED", "STORAGE", "SUCCESS", duration_ms=3.8, metrics={"logical_bytes": 3 * MIB, "physical_bytes": MIB, "cache_state": "WARM", "resident_pages": 2, "nonresident_pages": 1, "kernel_bonus_pages": 1, "major_faults": 1, "minor_faults": 36}),
        event(410, "KNOWLEDGE_RECORD_SELECTED", "CONTEXT", "SUCCESS", payload_summary={"record_id": "demo-connect", "source": "Python docs", "section": "sqlite3.connect", "excerpt": "Open a connection to an SQLite database file.", "score": 0.94, "reason": "CURRENT_QUERY"}),
        event(430, "KNOWLEDGE_RECORD_SELECTED", "CONTEXT", "SUCCESS", payload_summary={"record_id": "demo-cursor", "source": "Python docs", "section": "Cursor", "excerpt": "Create a cursor and execute SQL statements through the connection.", "score": 0.82, "reason": "SEMANTIC_RESCUE"}),
        event(450, "KNOWLEDGE_RECORD_SELECTED", "CONTEXT", "SUCCESS", payload_summary={"record_id": "demo-transaction", "source": "SQLite docs", "section": "Transactions", "excerpt": "Commit the transaction when changes should be persisted.", "score": 0.78, "reason": "PAGE_LOCALITY"}),
        event(470, "CONTEXT_BUILD_STARTED", "CONTEXT", "RUNNING"),
        event(620, "CONTEXT_BUILD_COMPLETED", "CONTEXT", "SUCCESS", duration_ms=7.1, metrics={"tokens": 1204, "token_budget": 4096, "bytes": 4816, "records_used": 3, "records_discarded": 2, "records_retrieved": 5, "records_expected": 2}),
        event(640, "CORE_STARTED", "CORE", "RUNNING", metrics={"model": "Qwen3-0.6B Q8_0", "mode": "CPU ONLY"}),
        event(680, "CORE_PROMPT_PROCESSING", "CORE", "RUNNING"),
        event(1660, "CORE_GENERATING", "CORE", "RUNNING"),
        event(2350, "CORE_COMPLETED", "CORE", "SUCCESS", duration_ms=1710, metrics={"model": "Qwen3-0.6B Q8_0", "mode": "CPU ONLY", "ttft_ms": 1020.0, "tokens_per_second": 31.4, "input_tokens": 1204, "output_tokens": 58, "total_latency_ms": 1710.0, "cpu_average_percent": 73.0, "cpu_peak_percent": 91.0, "ram_bytes": 1204 * MIB, "pss_bytes": 1175 * MIB, "anonymous_bytes": 532 * MIB, "file_backed_bytes": 621 * MIB, "threads_used": 4, "threads_total": 16}),
        event(2370, "PRESSURE_CHANGED", "RESOURCES", "INFO", metrics={"pressure": "LOW"}),
        event(2390, "ANSWER_READY", "ANSWER", "SUCCESS", payload_summary={"answer": "Use sqlite3.connect('arquivo.db') para abrir a conexão, crie um cursor e execute seus comandos SQL. [DEMO DATA]"}, metrics={"required_fact_score": 1.0, "source_correct": True, "quality_status": "DEMO"}),
    ]
