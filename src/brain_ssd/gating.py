from __future__ import annotations

from dataclasses import dataclass, field

from brain_ssd.router import RouteResult, SemanticIndex


@dataclass
class CognitiveState:
    current_domain: str | None = None
    current_topics: tuple[str, ...] = ()
    recent_pages: tuple[int, ...] = ()
    page_strength: dict[int, float] = field(default_factory=dict)
    page_age: dict[int, int] = field(default_factory=dict)
    topic_confidence: float = 0.0
    age: int = 0
    turn_index: int = 0

    def decay(self, factor: float = 0.72) -> None:
        self.turn_index += 1
        self.age += 1
        for page_id in list(self.page_strength):
            self.page_strength[page_id] *= factor
            self.page_age[page_id] = self.page_age.get(page_id, 0) + 1
            if self.page_strength[page_id] < 0.05:
                self.page_strength.pop(page_id)
                self.page_age.pop(page_id, None)

    def update(self, route: RouteResult, activated: tuple[int, ...]) -> None:
        previous_domain = self.current_domain
        if route.domains:
            self.current_domain = route.domains[0][0]
            self.topic_confidence = route.confidence
            self.age = 0 if self.current_domain != previous_domain else self.age
        self.current_topics = tuple(topic for topic, _ in route.topics[:4])
        self.recent_pages = activated
        scores = {page_id: score for page_id, score, _ in route.candidate_pages}
        for page_id in activated:
            self.page_strength[page_id] = max(self.page_strength.get(page_id, 0), min(1.0, scores.get(page_id, 0.5)))
            self.page_age[page_id] = 0


@dataclass(frozen=True)
class ActivationPlan:
    activate_pages: tuple[int, ...]
    keep_hot_pages: tuple[int, ...]
    inhibit_pages: tuple[int, ...]
    rejected_candidates: tuple[int, ...]
    reasons: tuple[tuple[int, str, float], ...]
    activation_budget_pages: int
    activation_budget_bytes: int


class GatingBackend:
    def apply(self, route_result: RouteResult, budget_mib: int, cognitive_state: CognitiveState | None = None) -> ActivationPlan:
        raise NotImplementedError


class BasalGate(GatingBackend):
    def __init__(self, index: SemanticIndex, page_size_bytes: int = 1024**2, activation_threshold: float = 0.01, deactivation_threshold: float = 0.18, dwell_turns: int = 1, hysteresis_budget_fraction: float = 0.25):
        self.index = index
        self.page_size_bytes = page_size_bytes
        self.activation_threshold = activation_threshold
        self.deactivation_threshold = deactivation_threshold
        self.dwell_turns = dwell_turns
        self.hysteresis_budget_fraction = hysteresis_budget_fraction

    def apply(self, route_result: RouteResult, budget_mib: int, cognitive_state: CognitiveState | None = None) -> ActivationPlan:
        budget_pages = max(0, budget_mib * 1024**2 // self.page_size_bytes)
        inhibited_domains = set(route_result.inhibited_domains)
        inhibited, eligible = [], []
        for page_id, score, reason in route_result.candidate_pages:
            if page_id not in self.index.pages:
                raise ValueError(f"invalid candidate page id: {page_id}")
            if self.index.pages[page_id]["domain"] in inhibited_domains:
                inhibited.append(page_id)
            elif score >= self.activation_threshold:
                eligible.append((page_id, score, reason))
        retained = []
        if cognitive_state is not None:
            for page_id, strength in cognitive_state.page_strength.items():
                age = cognitive_state.page_age.get(page_id, 0)
                if strength >= self.deactivation_threshold or age <= self.dwell_turns:
                    retained.append((page_id, strength, "hysteresis"))
        retained = sorted(retained, key=lambda item: (-item[1], item[0]))
        retained_limit = min(len(retained), int(budget_pages * self.hysteresis_budget_fraction))
        selected = retained[:retained_limit]
        selected_ids = {page_id for page_id, _, _ in selected}
        fresh = sorted(eligible, key=lambda item: (-item[1], item[0]))
        selected.extend(item for item in fresh if item[0] not in selected_ids)
        selected = selected[:budget_pages]
        selected_ids = {page_id for page_id, _, _ in selected}
        ranked_ids = {page_id for page_id, _, _ in [*eligible, *retained]}
        activated = tuple(page_id for page_id, _, _ in selected)
        keep = tuple(page_id for page_id, _, reason in selected if reason == "hysteresis")
        rejected = tuple(sorted(ranked_ids - selected_ids))
        return ActivationPlan(
            activated, keep, tuple(inhibited), rejected,
            tuple((page_id, reason, score) for page_id, score, reason in selected),
            budget_pages, budget_pages * self.page_size_bytes,
        )
