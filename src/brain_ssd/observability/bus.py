from __future__ import annotations

import threading
import time
from collections import deque

from brain_ssd.observability.events import BrainEvent


class BrainEventBus:
    """Bounded, non-blocking, in-process event stream.

    Publishing never waits for a browser. Slow consumers observe a dropped-event
    counter and can recover from the projected state snapshot.
    """

    def __init__(self, capacity: int = 1024) -> None:
        if capacity < 8:
            raise ValueError("capacity must be at least 8")
        self.capacity = capacity
        self._events: deque[BrainEvent] = deque(maxlen=capacity)
        self._condition = threading.Condition()
        self._next_sequence = 1
        self._dropped = 0
        self._closed = False

    @property
    def dropped_count(self) -> int:
        with self._condition:
            return self._dropped

    @property
    def latest_sequence(self) -> int:
        with self._condition:
            return self._next_sequence - 1

    def publish(self, event: BrainEvent) -> BrainEvent:
        with self._condition:
            if self._closed:
                return event
            if len(self._events) == self.capacity:
                self._dropped += 1
            sequenced = event.with_sequence(self._next_sequence)
            self._next_sequence += 1
            self._events.append(sequenced)
            self._condition.notify_all()
            return sequenced

    def events_since(self, sequence: int, limit: int = 256) -> list[BrainEvent]:
        with self._condition:
            return [event for event in self._events if event.sequence > sequence][:limit]

    def wait_for_events(self, sequence: int, timeout_s: float = 15.0) -> list[BrainEvent]:
        deadline = time.monotonic() + timeout_s
        with self._condition:
            while not self._closed:
                events = [event for event in self._events if event.sequence > sequence]
                if events:
                    return events[:256]
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return []
                self._condition.wait(timeout=remaining)
            return []

    def snapshot(self) -> list[BrainEvent]:
        with self._condition:
            return list(self._events)

    def close(self) -> None:
        with self._condition:
            self._closed = True
            self._condition.notify_all()
