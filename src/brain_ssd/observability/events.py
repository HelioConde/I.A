from __future__ import annotations

import json
import math
import time
from dataclasses import asdict, dataclass, field, replace
from enum import StrEnum
from typing import Any, Mapping


class BrainEventType(StrEnum):
    QUERY_RECEIVED = "QUERY_RECEIVED"
    REFLEX_STARTED = "REFLEX_STARTED"
    REFLEX_SKIPPED = "REFLEX_SKIPPED"
    REFLEX_COMPLETED = "REFLEX_COMPLETED"
    ROUTER_STARTED = "ROUTER_STARTED"
    ROUTER_CANDIDATES = "ROUTER_CANDIDATES"
    ROUTER_COMPLETED = "ROUTER_COMPLETED"
    SEMANTIC_RESCUE_STARTED = "SEMANTIC_RESCUE_STARTED"
    SEMANTIC_RESCUE_COMPLETED = "SEMANTIC_RESCUE_COMPLETED"
    GATE_STARTED = "GATE_STARTED"
    PAGE_ACTIVATED = "PAGE_ACTIVATED"
    PAGE_INHIBITED = "PAGE_INHIBITED"
    GATE_COMPLETED = "GATE_COMPLETED"
    STORAGE_READ_STARTED = "STORAGE_READ_STARTED"
    STORAGE_READ_COMPLETED = "STORAGE_READ_COMPLETED"
    KNOWLEDGE_RECORD_SELECTED = "KNOWLEDGE_RECORD_SELECTED"
    CONTEXT_BUILD_STARTED = "CONTEXT_BUILD_STARTED"
    CONTEXT_BUILD_COMPLETED = "CONTEXT_BUILD_COMPLETED"
    CORE_STARTED = "CORE_STARTED"
    CORE_PROCESS_STARTING = "CORE_PROCESS_STARTING"
    CORE_MODEL_LOADING = "CORE_MODEL_LOADING"
    CORE_READY = "CORE_READY"
    CORE_REQUEST_STARTED = "CORE_REQUEST_STARTED"
    CORE_REQUEST_COMPLETED = "CORE_REQUEST_COMPLETED"
    CORE_REUSED = "CORE_REUSED"
    CORE_SHUTDOWN = "CORE_SHUTDOWN"
    CORE_PROMPT_PROCESSING = "CORE_PROMPT_PROCESSING"
    CORE_GENERATING = "CORE_GENERATING"
    CORE_COMPLETED = "CORE_COMPLETED"
    ANSWER_READY = "ANSWER_READY"
    PRESSURE_CHANGED = "PRESSURE_CHANGED"
    WARNING = "WARNING"
    ERROR = "ERROR"


class EventStatus(StrEnum):
    WAITING = "WAITING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    ERROR = "ERROR"
    SKIPPED = "SKIPPED"
    INFO = "INFO"


def _json_value(value: Any) -> Any:
    """Return a bounded JSON-safe copy without retaining mutable input objects."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Mapping):
        return {str(key)[:120]: _json_value(item) for key, item in list(value.items())[:100]}
    if isinstance(value, (list, tuple, set)):
        return [_json_value(item) for item in list(value)[:200]]
    return str(value)[:500]


@dataclass(frozen=True, slots=True)
class BrainEvent:
    event_type: str
    component: str
    status: str = EventStatus.INFO
    timestamp: float = field(default_factory=time.time)
    sequence: int = 0
    run_id: str = ""
    query_id: str = ""
    turn_id: str = ""
    duration_ms: float | None = None
    metrics: dict[str, Any] = field(default_factory=dict)
    payload_summary: dict[str, Any] = field(default_factory=dict)
    demo_data: bool = False

    def __post_init__(self) -> None:
        if not self.event_type or len(self.event_type) > 80:
            raise ValueError("event_type must be 1..80 characters")
        if not self.component or len(self.component) > 80:
            raise ValueError("component must be 1..80 characters")
        if self.duration_ms is not None and self.duration_ms < 0:
            raise ValueError("duration_ms cannot be negative")
        object.__setattr__(self, "event_type", str(self.event_type).upper())
        object.__setattr__(self, "component", str(self.component).upper())
        object.__setattr__(self, "status", str(self.status).upper())
        object.__setattr__(self, "metrics", _json_value(self.metrics))
        object.__setattr__(self, "payload_summary", _json_value(self.payload_summary))

    @property
    def known_type(self) -> bool:
        return self.event_type in {event.value for event in BrainEventType}

    def with_sequence(self, sequence: int) -> "BrainEvent":
        return replace(self, sequence=sequence)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, separators=(",", ":"), sort_keys=True)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "BrainEvent":
        allowed = {
            "event_type", "component", "status", "timestamp", "sequence", "run_id",
            "query_id", "turn_id", "duration_ms", "metrics", "payload_summary", "demo_data",
        }
        return cls(**{key: value for key, value in payload.items() if key in allowed})

    @classmethod
    def from_json(cls, payload: str) -> "BrainEvent":
        parsed = json.loads(payload)
        if not isinstance(parsed, dict):
            raise ValueError("BrainEvent JSON must be an object")
        return cls.from_dict(parsed)
