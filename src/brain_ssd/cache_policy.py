from __future__ import annotations

import math
import sys
from collections import Counter, OrderedDict, defaultdict, deque
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class CacheEvent:
    turn_id: int
    query_id: str
    page_id: int
    logical_timestamp: int
    domain: str
    topics: tuple[str, ...]
    activation_provenance: tuple[str, ...]
    required: bool | None
    optional: bool | None
    route_confidence: float
    cognitive_state: dict
    physical_page_size: int
    logical_page_size: int
    phase_label: str = ""
    topic_transition: bool = False
    reload_cost: float = 1.0


@dataclass(frozen=True)
class CacheDecision:
    hit: bool
    admitted: bool
    evicted_pages: tuple[int, ...]
    action: str
    score_components: dict[str, float] = field(default_factory=dict)


class CachePolicy(Protocol):
    name: str
    budget_pages: int
    resident: set[int]
    def observe_access(self, event: CacheEvent) -> CacheDecision: ...
    def choose_evictions(self, event: CacheEvent, count: int = 1) -> tuple[int, ...]: ...
    def update_state(self, turn_id: int, cognitive_state: dict) -> None: ...
    def stats(self) -> dict: ...


class BaseCachePolicy:
    name = "base"

    def __init__(self, budget_pages: int):
        if budget_pages < 0:
            raise ValueError("budget_pages must be non-negative")
        self.budget_pages = budget_pages
        self.resident: set[int] = set()
        self.accesses = self.hits = self.misses = self.evictions = 0
        self.current_turn = 0
        self.current_state: dict = {}
        self.last_choose_ns = 0

    def update_state(self, turn_id: int, cognitive_state: dict) -> None:
        self.current_turn = turn_id
        self.current_state = dict(cognitive_state)

    def observe_access(self, event: CacheEvent) -> CacheDecision:
        self.last_choose_ns = 0
        self.accesses += 1
        self.current_turn = event.turn_id
        hit = event.page_id in self.resident
        if hit:
            self.hits += 1
            self._on_hit(event)
            return CacheDecision(True, False, (), "KEEP")
        self.misses += 1
        if self.budget_pages == 0:
            return CacheDecision(False, False, (), "MISS_NO_CACHE")
        evicted: tuple[int, ...] = ()
        if len(self.resident) >= self.budget_pages:
            import time
            choose_started = time.perf_counter_ns()
            evicted = self.choose_evictions(event, len(self.resident) - self.budget_pages + 1)
            self.last_choose_ns = time.perf_counter_ns() - choose_started
            for page_id in evicted:
                self.resident.remove(page_id)
                self._on_evict(page_id)
            self.evictions += len(evicted)
        self.resident.add(event.page_id)
        self._on_admit(event)
        return CacheDecision(False, True, evicted, "PROMOTE" if not evicted else "PROMOTE_EVICT")

    def choose_evictions(self, event: CacheEvent, count: int = 1) -> tuple[int, ...]:
        raise NotImplementedError

    def _on_hit(self, event: CacheEvent) -> None: pass
    def _on_admit(self, event: CacheEvent) -> None: pass
    def _on_evict(self, page_id: int) -> None: pass

    def stats(self) -> dict:
        return {"policy": self.name, "budget_pages": self.budget_pages, "accesses": self.accesses, "hits": self.hits, "misses": self.misses, "evictions": self.evictions, "resident_pages": len(self.resident), "metadata_bytes_estimated": self.metadata_bytes()}

    def metadata_bytes(self) -> int:
        seen: set[int] = set()
        def size(value):
            if id(value) in seen:
                return 0
            seen.add(id(value))
            total = sys.getsizeof(value)
            if isinstance(value, dict):
                total += sum(size(key) + size(item) for key, item in value.items())
            elif isinstance(value, (list, tuple, set, deque, OrderedDict, Counter, defaultdict)):
                total += sum(size(item) for item in value)
            return total
        return size(self._metadata_objects())

    def _metadata_objects(self):
        return {"resident": self.resident, "state": self.current_state}


class NoCachePolicy(BaseCachePolicy):
    name = "no_cache"
    def __init__(self, budget_pages: int = 0): super().__init__(0)
    def choose_evictions(self, event: CacheEvent, count: int = 1) -> tuple[int, ...]: return ()


class LRUPolicy(BaseCachePolicy):
    name = "lru"
    def __init__(self, budget_pages: int):
        super().__init__(budget_pages); self.order: OrderedDict[int, None] = OrderedDict()
    def _on_hit(self, event): self.order.move_to_end(event.page_id)
    def _on_admit(self, event): self.order[event.page_id] = None
    def _on_evict(self, page_id): self.order.pop(page_id, None)
    def choose_evictions(self, event, count=1): return tuple(list(self.order)[:count])
    def _metadata_objects(self): return {"resident": self.resident, "order": self.order}


class LFUPolicy(BaseCachePolicy):
    name = "lfu"
    def __init__(self, budget_pages: int):
        super().__init__(budget_pages); self.frequency: Counter[int] = Counter(); self.last_access: dict[int, int] = {}
    def _record(self, event): self.frequency[event.page_id] += 1; self.last_access[event.page_id] = event.logical_timestamp
    def _on_hit(self, event): self._record(event)
    def _on_admit(self, event): self._record(event)
    def choose_evictions(self, event, count=1): return tuple(sorted(self.resident, key=lambda page: (self.frequency[page], self.last_access.get(page, -1), page))[:count])
    def _metadata_objects(self): return {"resident": self.resident, "frequency": self.frequency, "last_access": self.last_access}


class LRFUPolicy(LFUPolicy):
    name = "lrfu"
    def __init__(self, budget_pages: int, frequency_weight: float = 0.55, recency_weight: float = 0.45):
        super().__init__(budget_pages); self.frequency_weight = frequency_weight; self.recency_weight = recency_weight
    def _score(self, page: int, now: int) -> float:
        age = max(0, now - self.last_access.get(page, now))
        return self.frequency_weight * math.log1p(self.frequency[page]) + self.recency_weight / (1 + age)
    def choose_evictions(self, event, count=1): return tuple(sorted(self.resident, key=lambda page: (self._score(page, event.logical_timestamp), page))[:count])


class AdaptiveTwoQueuePolicy(BaseCachePolicy):
    """Small validated 2Q equivalent: first hits stay recent; reuse promotes to frequent."""
    name = "adaptive_2q"
    def __init__(self, budget_pages: int):
        super().__init__(budget_pages); self.recent: OrderedDict[int, None] = OrderedDict(); self.frequent: OrderedDict[int, None] = OrderedDict(); self.target_recent = max(1, budget_pages // 4) if budget_pages else 0
    def _on_admit(self, event): self.recent[event.page_id] = None
    def _on_hit(self, event):
        if event.page_id in self.recent:
            self.recent.pop(event.page_id); self.frequent[event.page_id] = None
        else:
            self.frequent.move_to_end(event.page_id)
    def _on_evict(self, page_id): self.recent.pop(page_id, None); self.frequent.pop(page_id, None)
    def choose_evictions(self, event, count=1):
        victims = []
        recent_keys, frequent_keys = list(self.recent), list(self.frequent)
        for _ in range(count):
            if recent_keys and (len(recent_keys) > self.target_recent or not frequent_keys): victims.append(recent_keys.pop(0))
            elif frequent_keys: victims.append(frequent_keys.pop(0))
            elif recent_keys: victims.append(recent_keys.pop(0))
        return tuple(victims)
    def _metadata_objects(self): return {"resident": self.resident, "recent": self.recent, "frequent": self.frequent}


@dataclass
class CognitivePageState:
    frequency: int = 0
    last_timestamp: int = 0
    last_turn: int = 0
    topics: tuple[str, ...] = ()
    provenance: tuple[str, ...] = ()
    reload_cost: float = 1.0
    admitted_turn: int = 0
    hot_since_turn: int = 0


DEFAULT_COGNITIVE_WEIGHTS = {
    "recency": 0.28, "frequency": 0.20, "topic": 0.20, "transition": 0.12,
    "reload": 0.05, "provenance": 0.08, "hysteresis": 0.10, "age": 0.03,
}


class CognitiveCacheV0(BaseCachePolicy):
    name = "cognitive_v0"
    def __init__(self, budget_pages: int, weights: dict[str, float] | None = None, disabled_signals: set[str] | None = None):
        super().__init__(budget_pages)
        self.weights = dict(DEFAULT_COGNITIVE_WEIGHTS if weights is None else weights)
        self.disabled_signals = set(disabled_signals or ())
        self.pages: dict[int, CognitivePageState] = {}
        self.transitions: Counter[tuple[int, int]] = Counter()
        self.transition_outgoing: Counter[int] = Counter()
        self.coactivations: Counter[tuple[int, int]] = Counter()
        self.previous_page: int | None = None
        self.turn_pages: dict[int, set[int]] = defaultdict(set)
        self.last_score_components: dict[int, dict[str, float]] = {}

    def update_state(self, turn_id: int, cognitive_state: dict) -> None:
        super().update_state(turn_id, cognitive_state)
        # Association statistics use only already-observed pages and never trigger admission.
        pages = sorted(self.turn_pages.pop(turn_id - 1, ()))
        for left_index, left in enumerate(pages):
            for right in pages[left_index + 1:]:
                self.coactivations[(left, right)] += 1; self.coactivations[(right, left)] += 1

    def _record(self, event: CacheEvent) -> None:
        state = self.pages.setdefault(event.page_id, CognitivePageState())
        state.frequency += 1; state.last_timestamp = event.logical_timestamp; state.last_turn = event.turn_id
        state.topics = event.topics; state.provenance = event.activation_provenance; state.reload_cost = event.reload_cost
        self.turn_pages[event.turn_id].add(event.page_id)
        if self.previous_page is not None and self.previous_page != event.page_id:
            self.transitions[(self.previous_page, event.page_id)] += 1
            self.transition_outgoing[self.previous_page] += 1
        self.previous_page = event.page_id

    def _on_hit(self, event): self._record(event)
    def _on_admit(self, event):
        self._record(event); state = self.pages[event.page_id]; state.admitted_turn = event.turn_id; state.hot_since_turn = event.turn_id

    def _provenance_value(self, provenance: tuple[str, ...]) -> float:
        values = {"CURRENT_QUERY": 1.0, "CONTEXT_BOOST": 0.8, "CONTEXT_EXPANSION": 0.65, "SEMANTIC_RESCUE": 0.65, "ALIAS": 0.55, "FUZZY_MATCH": 0.25, "MULTI_DOMAIN": 0.75, "FALLBACK": 0.15}
        return max((values.get(item, 0.5) for item in provenance), default=0.5)

    def score_components(self, page: int, event: CacheEvent) -> dict[str, float]:
        state = self.pages[page]
        age_turns = max(0, event.turn_id - state.last_turn)
        active_topics = set(event.cognitive_state.get("topics", ())) | set(event.topics)
        topic = len(active_topics & set(state.topics)) / max(1, len(set(state.topics)))
        transition_count = self.transitions[(self.previous_page, page)] if self.previous_page is not None else 0
        outgoing = self.transition_outgoing[self.previous_page] if self.previous_page is not None else 0
        transition = transition_count / outgoing if outgoing else 0.0
        association = self.coactivations[(event.page_id, page)]
        transition = max(transition, association / max(1, state.frequency))
        components = {
            "recency": 1 / (1 + age_turns), "frequency": math.log1p(state.frequency) / 8,
            "topic": topic, "transition": min(1.0, transition), "reload": min(1.0, state.reload_cost / 2),
            "provenance": self._provenance_value(state.provenance),
            "hysteresis": min(1.0, (event.turn_id - state.hot_since_turn + 1) / max(1, self.budget_pages / 4)),
            "age": age_turns / (age_turns + 8),
        }
        return components

    def hot_score(self, page: int, event: CacheEvent) -> float:
        components = self.score_components(page, event); self.last_score_components[page] = components
        total = 0.0
        for name, value in components.items():
            if name in self.disabled_signals: continue
            weight = self.weights.get(name, 0.0)
            total += -weight * value if name == "age" else weight * value
        return total

    def choose_evictions(self, event, count=1): return tuple(sorted(self.resident, key=lambda page: (self.hot_score(page, event), page))[:count])
    def _metadata_objects(self): return {"resident": self.resident, "pages": self.pages, "transitions": self.transitions, "transition_outgoing": self.transition_outgoing, "coactivations": self.coactivations, "turn_pages": self.turn_pages}


class BeladyOraclePolicy(BaseCachePolicy):
    name = "belady_oracle"
    def __init__(self, budget_pages: int, events: list[CacheEvent]):
        super().__init__(budget_pages)
        self.future: dict[int, deque[int]] = defaultdict(deque)
        for position, event in enumerate(events): self.future[event.page_id].append(position)
        self.position = -1
    def observe_access(self, event):
        self.position += 1
        queue = self.future[event.page_id]
        if queue and queue[0] == self.position: queue.popleft()
        return super().observe_access(event)
    def choose_evictions(self, event, count=1):
        infinity = len(self.future) + 10**12
        return tuple(sorted(self.resident, key=lambda page: (self.future[page][0] if self.future[page] else infinity, page), reverse=True)[:count])
    def _metadata_objects(self): return {"resident": self.resident, "future": self.future}
