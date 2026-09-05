from __future__ import annotations

import copy
import threading
import time
from collections import deque
from typing import Any

from brain_ssd.observability.bus import BrainEventBus
from brain_ssd.observability.events import BrainEvent
from brain_ssd.observability.narrator import EventNarrator


PIPELINE_COMPONENTS = ("INPUT", "ROUTER", "GATE", "BRAIN", "CONTEXT", "CORE", "ANSWER")


def _pipeline() -> dict[str, dict[str, Any]]:
    return {name: {"status": "WAITING", "duration_ms": None} for name in PIPELINE_COMPONENTS}


def _initial_state() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "mode": "IDLE",
        "data_source": "WAITING",
        "demo_data": False,
        "validation": {
            "track": "NONE",
            "platform": "UNCLASSIFIED",
            "canonical_phase4e": False,
            "target_8gb": "NOT_TESTED",
        },
        "run_id": "",
        "query_id": "",
        "query": "Aguardando uma consulta ou replay.",
        "answer": "",
        "current_event": "WAITING",
        "current_component": "SYSTEM",
        "current_message": "O HUD está pronto e não altera o Brain-SSD.",
        "pipeline": _pipeline(),
        "brain": {
            "total_bytes": 0,
            "total_pages": 0,
            "active_bytes": 0,
            "active_pages": 0,
            "active_rate": 0.0,
            "pages": [],
        },
        "knowledge": {"records": [], "selected": 0, "retrieved": 0, "expected": None},
        "context": {
            "tokens": 0, "token_budget": 4096, "bytes": 0,
            "records_used": 0, "records_discarded": 0,
            "records_retrieved": 0, "records_retained": 0, "records_pruned": 0,
            "v0_tokens": None, "tokens_avoided": None, "evidence_bytes": None,
            "required_facts_found": None, "required_facts_total": None, "grounding": None,
        },
        "core": {
            "model": "Qwen3-0.6B Q8_0",
            "mode": "CPU ONLY",
            "status": "IDLE",
            "ttft_ms": None,
            "tokens_per_second": None,
            "input_tokens": None,
            "output_tokens": None,
            "total_latency_ms": None,
            "residency": "NOT_RESIDENT",
            "model_loads": 0,
            "queries_served": 0,
            "reloads_avoided": 0,
            "core_reuse_ratio": 0.0,
            "persistent_core_ready_ms": None,
        },
        "resources": {
            "cpu_current_percent": None,
            "cpu_average_percent": None,
            "cpu_peak_percent": None,
            "threads_used": None,
            "threads_total": None,
            "ram_bytes": None,
            "working_set_peak_bytes": None,
            "private_bytes": None,
            "available_system_ram_bytes": None,
            "memory_growth_bytes": None,
            "pss_bytes": None,
            "anonymous_bytes": None,
            "file_backed_bytes": None,
            "temperature_c": None,
            "pressure": "UNKNOWN",
        },
        "storage": {
            "logical_bytes": 0,
            "physical_bytes": 0,
            "resident_pages": None,
            "nonresident_pages": None,
            "kernel_bonus_pages": None,
            "cache_state": "UNKNOWN",
            "major_faults": None,
            "minor_faults": None,
        },
        "quality": {"required_fact_score": None, "source_correct": None, "status": "UNKNOWN"},
        "bottleneck": {"component": "WAITING", "label": "Aguardando dados", "share_percent": None, "duration_ms": None},
        "work_avoided": {"sleeping_pages": 0, "sleeping_rate": 0.0, "inhibited_candidates": 0, "semantic_rescue_skipped": False},
        "components": {"worked": [], "sleeping": ["PREFETCH", "HIPPOCAMPUS", "SKILLS", "CONNECTIVITY"]},
        "timeline": [],
        "warnings": [],
        "errors": [],
        "phases": [],
        "updated_at": time.time(),
    }


class HudStateStore:
    def __init__(self, history_size: int = 50, narrator: EventNarrator | None = None) -> None:
        self._lock = threading.RLock()
        self._state = _initial_state()
        self._history: deque[dict[str, Any]] = deque(maxlen=history_size)
        self.narrator = narrator or EventNarrator()

    def reset(
        self,
        *,
        data_source: str,
        demo_data: bool,
        phases: list[dict[str, Any]] | None = None,
        validation: dict[str, Any] | None = None,
    ) -> None:
        with self._lock:
            previous_phases = phases if phases is not None else self._state.get("phases", [])
            self._state = _initial_state()
            self._state["data_source"] = data_source
            self._state["demo_data"] = demo_data
            self._state["phases"] = copy.deepcopy(previous_phases)
            if validation is not None:
                self._state["validation"].update(copy.deepcopy(validation))

    def set_phases(self, phases: list[dict[str, Any]]) -> None:
        with self._lock:
            self._state["phases"] = copy.deepcopy(phases)

    def _set_stage(self, component: str, status: str, duration_ms: float | None) -> None:
        if component in self._state["pipeline"]:
            self._state["pipeline"][component]["status"] = status
            if duration_ms is not None:
                self._state["pipeline"][component]["duration_ms"] = duration_ms

    def _worked(self, component: str) -> None:
        worked = self._state["components"]["worked"]
        if component not in worked and component not in {"SYSTEM", "INPUT", "ANSWER"}:
            worked.append(component)

    def _append_timeline(self, event: BrainEvent, message: str) -> None:
        self._state["timeline"].append({
            "sequence": event.sequence,
            "timestamp": event.timestamp,
            "event_type": event.event_type,
            "component": event.component,
            "status": event.status,
            "duration_ms": event.duration_ms,
            "message": message,
        })
        self._state["timeline"] = self._state["timeline"][-120:]

    def _update_bottleneck(self) -> None:
        labels = {
            "ROUTER": "Roteamento",
            "GATE": "Seleção do cérebro",
            "BRAIN": "Leitura do conhecimento",
            "CONTEXT": "Construção de contexto",
            "CORE": "Processamento do Core",
        }
        durations = {
            name: details.get("duration_ms")
            for name, details in self._state["pipeline"].items()
            if name in labels and isinstance(details.get("duration_ms"), (int, float))
        }
        if not durations:
            return
        component = max(durations, key=durations.get)
        total = sum(durations.values())
        duration = durations[component]
        self._state["bottleneck"] = {
            "component": component,
            "label": labels[component],
            "share_percent": (100.0 * duration / total) if total else None,
            "duration_ms": duration,
        }

    def _finalize_history(self) -> None:
        brain = self._state["brain"]
        core = self._state["core"]
        self._history.appendleft({
            "run_id": self._state["run_id"],
            "query_id": self._state["query_id"],
            "query": self._state["query"],
            "active_bytes": brain["active_bytes"],
            "active_rate": brain["active_rate"],
            "ttft_ms": core["ttft_ms"],
            "physical_bytes": self._state["storage"]["physical_bytes"],
            "quality": self._state["quality"]["required_fact_score"],
            "status": self._state["quality"]["status"],
            "demo_data": self._state["demo_data"],
        })

    def apply(self, event: BrainEvent) -> None:
        with self._lock:
            payload, metrics = event.payload_summary, event.metrics
            message = self.narrator.narrate(event)
            self._state["updated_at"] = time.time()
            self._state["run_id"] = event.run_id or self._state["run_id"]
            self._state["query_id"] = event.query_id or self._state["query_id"]
            self._state["demo_data"] = event.demo_data
            self._state["current_event"] = event.event_type
            self._state["current_component"] = event.component
            self._state["current_message"] = message
            self._worked(event.component)
            self._append_timeline(event, message)

            event_type = event.event_type
            if event_type == "QUERY_RECEIVED":
                self._state["mode"] = "RUNNING"
                self._state["query"] = payload.get("query", "Consulta ocultada")
                self._set_stage("INPUT", "SUCCESS", event.duration_ms)
            elif event_type == "ROUTER_STARTED":
                self._set_stage("ROUTER", "RUNNING", None)
            elif event_type == "ROUTER_COMPLETED":
                self._set_stage("ROUTER", event.status, event.duration_ms)
            elif event_type == "GATE_STARTED":
                self._set_stage("GATE", "RUNNING", None)
            elif event_type == "PAGE_ACTIVATED":
                page = {
                    "page_id": payload.get("page_id"),
                    "domain": payload.get("domain", "Knowledge"),
                    "topic": payload.get("topic", "Relevant knowledge"),
                    "state": "ACTIVE",
                    "reasons": payload.get("reasons", []),
                    "provenance": payload.get("provenance", []),
                    "scores": payload.get("scores", {}),
                    "resident": payload.get("resident"),
                }
                if not any(existing.get("page_id") == page["page_id"] for existing in self._state["brain"]["pages"]):
                    self._state["brain"]["pages"].append(page)
                self._set_stage("BRAIN", "RUNNING", None)
            elif event_type == "PAGE_INHIBITED":
                self._state["brain"]["pages"].append({
                    "page_id": payload.get("page_id"),
                    "domain": payload.get("domain", "Knowledge"),
                    "topic": payload.get("topic", "Candidate"),
                    "state": "INHIBITED",
                    "reasons": payload.get("reasons", []),
                    "provenance": payload.get("provenance", []),
                    "scores": payload.get("scores", {}),
                    "resident": payload.get("resident"),
                })
                self._state["work_avoided"]["inhibited_candidates"] += 1
            elif event_type == "GATE_COMPLETED":
                brain = self._state["brain"]
                brain["active_bytes"] = metrics.get("active_brain_bytes", brain["active_bytes"])
                brain["total_bytes"] = metrics.get("total_brain_bytes", brain["total_bytes"])
                brain["active_pages"] = metrics.get("active_pages", len([p for p in brain["pages"] if p["state"] == "ACTIVE"]))
                brain["total_pages"] = metrics.get("total_pages", brain["total_pages"])
                brain["active_rate"] = (brain["active_bytes"] / brain["total_bytes"]) if brain["total_bytes"] else 0.0
                sleeping = max(0, brain["total_pages"] - brain["active_pages"])
                self._state["work_avoided"]["sleeping_pages"] = sleeping
                self._state["work_avoided"]["sleeping_rate"] = sleeping / brain["total_pages"] if brain["total_pages"] else 0.0
                self._set_stage("GATE", event.status, event.duration_ms)
            elif event_type == "STORAGE_READ_STARTED":
                self._set_stage("BRAIN", "RUNNING", None)
            elif event_type == "STORAGE_READ_COMPLETED":
                storage = self._state["storage"]
                for key in ("logical_bytes", "physical_bytes", "resident_pages", "nonresident_pages", "kernel_bonus_pages", "cache_state", "major_faults", "minor_faults"):
                    if key in metrics:
                        storage[key] = metrics[key]
                self._set_stage("BRAIN", event.status, event.duration_ms)
            elif event_type == "KNOWLEDGE_RECORD_SELECTED":
                record = {
                    "record_id": payload.get("record_id", "unknown"),
                    "source": payload.get("source", "unknown"),
                    "section": payload.get("section", "KnowledgeRecord"),
                    "excerpt": str(payload.get("excerpt", ""))[:320],
                    "score": payload.get("score"),
                    "reason": payload.get("reason", "Selected by retrieval"),
                }
                if not any(existing["record_id"] == record["record_id"] for existing in self._state["knowledge"]["records"]):
                    self._state["knowledge"]["records"].append(record)
                self._state["knowledge"]["selected"] = len(self._state["knowledge"]["records"])
            elif event_type == "CONTEXT_BUILD_STARTED":
                self._set_stage("CONTEXT", "RUNNING", None)
            elif event_type == "CONTEXT_BUILD_COMPLETED":
                context = self._state["context"]
                for key in (
                    "tokens", "token_budget", "bytes", "records_used", "records_discarded",
                    "records_retrieved", "records_retained", "records_pruned", "v0_tokens",
                    "tokens_avoided", "evidence_bytes", "required_facts_found",
                    "required_facts_total", "grounding",
                ):
                    if key in metrics:
                        context[key] = metrics[key]
                self._state["knowledge"]["retrieved"] = metrics.get("records_retrieved", self._state["knowledge"]["retrieved"])
                self._state["knowledge"]["expected"] = metrics.get("records_expected", self._state["knowledge"]["expected"])
                self._set_stage("CONTEXT", event.status, event.duration_ms)
            elif event_type in {"CORE_STARTED", "CORE_PROCESS_STARTING"}:
                self._state["core"]["status"] = "LOADING"
                self._set_stage("CORE", "RUNNING", None)
            elif event_type == "CORE_MODEL_LOADING":
                self._state["core"]["status"] = "MODEL LOADING"
            elif event_type == "CORE_READY":
                core = self._state["core"]
                core["status"] = "READY"
                core["residency"] = "RESIDENT"
                core["model_loads"] = metrics.get("model_loads", core["model_loads"])
                core["persistent_core_ready_ms"] = metrics.get("persistent_core_ready_ms")
            elif event_type == "CORE_REUSED":
                core = self._state["core"]
                core["status"] = "REUSED"
                core["residency"] = "RESIDENT"
                core["queries_served"] = metrics.get("queries_served", core["queries_served"])
                core["model_loads"] = metrics.get("model_loads", core["model_loads"])
            elif event_type == "CORE_REQUEST_STARTED":
                self._state["core"]["status"] = "PROCESSING"
            elif event_type == "CORE_REQUEST_COMPLETED":
                core = self._state["core"]
                for key in ("model_loads", "queries_served", "reloads_avoided", "core_reuse_ratio"):
                    if key in metrics:
                        core[key] = metrics[key]
                if metrics.get("core_mode") == "PERSISTENT_CORE":
                    core["residency"] = "RESIDENT"
            elif event_type == "CORE_SHUTDOWN":
                self._state["core"]["status"] = "SHUTDOWN"
                self._state["core"]["residency"] = "NOT_RESIDENT"
            elif event_type == "CORE_PROMPT_PROCESSING":
                self._state["core"]["status"] = "READING CONTEXT"
            elif event_type == "CORE_GENERATING":
                self._state["core"]["status"] = "GENERATING"
            elif event_type == "CORE_COMPLETED":
                core = self._state["core"]
                for key in ("model", "mode", "ttft_ms", "tokens_per_second", "input_tokens", "output_tokens", "total_latency_ms"):
                    if key in metrics:
                        core[key] = metrics[key]
                core["status"] = "IDLE" if event.status == "SUCCESS" else event.status
                resources = self._state["resources"]
                for key in ("cpu_average_percent", "cpu_peak_percent", "ram_bytes", "working_set_peak_bytes", "private_bytes", "available_system_ram_bytes", "memory_growth_bytes", "pss_bytes", "anonymous_bytes", "file_backed_bytes", "threads_used", "threads_total", "temperature_c"):
                    if key in metrics:
                        resources[key] = metrics[key]
                self._set_stage("CORE", event.status, event.duration_ms or metrics.get("total_latency_ms"))
            elif event_type == "PRESSURE_CHANGED":
                self._state["resources"]["pressure"] = metrics.get("pressure", payload.get("pressure", "UNKNOWN"))
            elif event_type == "WARNING":
                self._state["warnings"].append(payload.get("message", message))
            elif event_type == "ERROR":
                self._state["errors"].append({"component": event.component, "message": payload.get("message", message)})
                self._state["mode"] = "ERROR"
            elif event_type == "ANSWER_READY":
                self._state["answer"] = payload.get("answer", "Resposta ocultada")
                quality = self._state["quality"]
                quality["required_fact_score"] = metrics.get("required_fact_score")
                quality["source_correct"] = metrics.get("source_correct")
                quality["status"] = metrics.get("quality_status", "OK")
                self._state["mode"] = "COMPLETE"
                self._set_stage("ANSWER", event.status, event.duration_ms)
                self._update_bottleneck()
                self._finalize_history()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._state)

    def history(self) -> list[dict[str, Any]]:
        with self._lock:
            return copy.deepcopy(list(self._history))


class HudRuntime:
    """Small façade joining the bounded stream and read-only state projection."""

    def __init__(self, bus: BrainEventBus | None = None, state: HudStateStore | None = None) -> None:
        self.bus = bus or BrainEventBus()
        self.state = state or HudStateStore()

    def emit(self, event: BrainEvent) -> BrainEvent:
        sequenced = self.bus.publish(event)
        self.state.apply(sequenced)
        return sequenced

    def close(self) -> None:
        self.bus.close()
