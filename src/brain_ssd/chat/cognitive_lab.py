"""Bounded cognitive mechanisms for opt-in *experiments*.

No neural simulator, consciousness, self-editing model, background daemon or
network I/O. All inference-time changes are SHADOW and do not alter the Qwen
prompts, canonical retrieval, GGUF, or frozen research baselines.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
import math
import time
from typing import Any, Iterable

from brain_ssd.chat.episodic import words


@dataclass(frozen=True)
class AttentionPlan:
    selected_ids: tuple[str, ...]
    inhibited_ids: tuple[str, ...]
    activation_bytes: int
    reason: str = "lexical_attention_shadow_not_an_activated_neural_circuit"


def select_attention(query: str, records: Iterable[dict[str, Any]], *,
                     max_records: int = 3, max_bytes: int = 1600) -> AttentionPlan:
    """Cheap gating with abstention and a hard UTF-8 activation budget.

    Candidates are metadata + short text. No page is loaded and no hidden
    state is modified. Doesn't assert that omitted evidence is unnecessary.
    """
    if not 0 <= max_records <= 12 or not 0 <= max_bytes <= 8192:
        raise ValueError("Invalid activation budget")
    cue = words(query)
    ranked: list[tuple[float, str, int]] = []
    seen: set[str] = set()
    for row in records:
        ident = row.get("id")
        text = row.get("text")
        if not isinstance(ident, str) or not ident or not isinstance(text, str):
            raise ValueError("Every candidate needs id and text")
        if ident in seen:
            raise ValueError("Duplicate candidate id")
        seen.add(ident)
        overlap = len(cue & words(text))
        if not overlap:
            ranked.append((0.0, ident, len(text.encode("utf-8"))))
            continue
        # Intersection over cue favors coverage. Never infer truth from ranking.
        score = overlap / max(1, len(cue))
        ranked.append((score, ident, len(text.encode("utf-8"))))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    chosen: list[str] = []
    spent = 0
    for score, ident, size in ranked:
        if score > 0 and len(chosen) < max_records and spent + size <= max_bytes:
            chosen.append(ident)
            spent += size
    excluded = sorted(seen - set(chosen))
    return AttentionPlan(tuple(chosen), tuple(excluded), spent)


@dataclass(frozen=True)
class WorkingState:
    """Short-lived compact topic metadata, not a copy of the conversation."""
    topics: tuple[str, ...]
    latest_user_topics: tuple[str, ...]
    history_turns: int
    approx_bytes: int
    source: str = "recent_chat_metadata"

    def to_dict(self) -> dict[str, Any]:
        return {"topics": list(self.topics),
                "latest_user_topics": list(self.latest_user_topics),
                "history_turns": self.history_turns,
                "approx_bytes": self.approx_bytes,
                "source": self.source}


def working_state(messages: list[dict[str, str]], *, max_messages: int = 8,
                  max_topics: int = 8) -> WorkingState:
    """Build and discard an attention-like activity-silent sketch per turn.

    Recent cue terms win; no chat text is persisted outside existing history.
    """
    if not 1 <= max_messages <= 32 or not 1 <= max_topics <= 20:
        raise ValueError("Invalid working-memory limits")
    recent = messages[-max_messages:]
    counts: Counter[str] = Counter()
    for weight, message in enumerate(recent, 1):
        if message.get("role") not in ("user", "assistant"):
            continue
        for token in words(str(message.get("content", ""))[:700]):
            counts[token] += weight
    ranked = sorted(counts, key=lambda term: (-counts[term], term))[:max_topics]
    latest_user = next((row for row in reversed(recent)
                        if row.get("role") == "user"), None)
    latest = sorted(words(latest_user["content"]))[:max_topics] if latest_user else []
    approximate_size = sum(len(t.encode("utf-8")) for t in ranked + latest)
    return WorkingState(tuple(ranked), tuple(latest), len(recent), approximate_size)


@dataclass(frozen=True)
class Association:
    left_id: str
    right_id: str
    shared_cues: tuple[str, ...]
    overlap: float
    status: str = "SHADOW_ONLY"


def propose_associations(notes: list[dict[str, Any]], *, max_pairs: int = 50,
                         min_shared: int = 2) -> list[Association]:
    """Read-only co-cue proposals; never merge episodes or invent causality."""
    if not 1 <= max_pairs <= 100 or not 1 <= min_shared <= 10:
        raise ValueError("Invalid association limits")
    records = []
    for note in notes[:1000]:
        if note.get("confirmed") is not True or note.get("source") != "explicit_user":
            continue
        if not isinstance(note.get("id"), str) or not isinstance(note.get("content"), str):
            continue
        records.append((note["id"], words(note["content"])))
    proposals: list[Association] = []
    for i, (left, a) in enumerate(records):
        for right, b in records[i+1:]:
            shared = a & b
            if len(shared) >= min_shared:
                proposals.append(Association(
                    left, right, tuple(sorted(shared)),
                    round(len(shared) / max(1, len(a | b)), 4),
                ))
    proposals.sort(key=lambda x: (-x.overlap, x.left_id, x.right_id))
    return proposals[:max_pairs]


@dataclass(frozen=True)
class ReplayPreview:
    candidate_ids: tuple[str, ...]
    associations: tuple[Association, ...]
    reviewed_at: int
    mode: str = "READ_ONLY_OFFLINE_PREVIEW"
    writes_to_model: bool = False


def replay_preview(notes: list[dict[str, Any]], *, max_notes: int = 12) -> ReplayPreview:
    """Bounded offline preview: no autonomous sleep/consolidation or learning."""
    if not 1 <= max_notes <= 50:
        raise ValueError("Invalid replay limit")
    confirmed = [x for x in notes if x.get("confirmed") is True
                 and x.get("source") == "explicit_user"][:max_notes]
    associations = propose_associations(confirmed)
    return ReplayPreview(tuple(x["id"] for x in confirmed),
                         tuple(associations), int(time.time()))


@dataclass(frozen=True)
class PredictionObservation:
    probability: float
    observed: bool
    error: float
    brier: float


def prediction_error(probability: float, observed: bool) -> PredictionObservation:
    """A numerical feedback signal ONLY when real ground truth is supplied."""
    if not isinstance(observed, bool):
        raise ValueError("Observed outcome must be explicitly verified boolean")
    if not isinstance(probability, (float, int)) or not math.isfinite(probability) or not 0 <= probability <= 1:
        raise ValueError("Probability must be finite and within [0,1]")
    target = float(observed)
    error = target - float(probability)
    return PredictionObservation(float(probability), observed, error, error ** 2)


@dataclass
class GridWorld:
    """Closed synthetic perception/action loop; NO PC automation or robotics.

    One-cell-limited perception. Actions change ONLY in-memory coordinates.
    """
    width: int = 5
    height: int = 5
    walls: frozenset[tuple[int, int]] = field(
        default_factory=lambda: frozenset({(2, 1), (2, 2), (2, 3)}))
    goal: tuple[int, int] = (4, 4)
    position: tuple[int, int] = (0, 0)
    actions: int = 0
    finished: bool = False
    trace: list[dict[str, Any]] = field(default_factory=list)

    _MOVES = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}

    def __post_init__(self) -> None:
        if not 2 <= self.width <= 30 or not 2 <= self.height <= 30:
            raise ValueError("World size outside safe bound")
        coords = (*self.walls, self.goal, self.position)
        if any(not (0 <= x < self.width and 0 <= y < self.height) for x, y in coords):
            raise ValueError("Invalid world coordinates")
        if self.goal in self.walls or self.position in self.walls:
            raise ValueError("Goal/agent cannot be a wall")

    def observe(self) -> dict[str, Any]:
        x, y = self.position
        local = {}
        for direction, (dx, dy) in self._MOVES.items():
            dest = (x + dx, y + dy)
            local[direction] = ("wall" if dest in self.walls
                                or not (0 <= dest[0] < self.width and 0 <= dest[1] < self.height)
                                else "free")
        return {"position": [x, y], "local": local, "goal_visible": self.goal == self.position,
                "finished": self.finished, "actions": self.actions}

    def step(self, action: str) -> dict[str, Any]:
        if action not in self._MOVES:
            raise ValueError("Action outside closed four-action vocabulary")
        if self.finished:
            raise RuntimeError("Episode ended; create a new GridWorld")
        if self.actions >= 100:
            self.finished = True
            raise RuntimeError("Safe action budget reached")
        perception = self.observe()
        dx, dy = self._MOVES[action]
        x, y = self.position
        target = (x + dx, y + dy)
        blocked = perception["local"][action] == "wall"
        if not blocked:
            self.position = target
        self.actions += 1
        reached = self.position == self.goal
        self.finished = reached or self.actions >= 100
        result = {"action": action, "observation": perception,
                  "next_position": list(self.position), "blocked": blocked,
                  "reward": 1.0 if reached else (-0.2 if blocked else -0.01),
                  "goal_reached": reached, "finished": self.finished}
        self.trace.append(result)
        return result
