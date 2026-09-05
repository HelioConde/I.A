from __future__ import annotations

from brain_ssd.residency import AdvisoryResidencyController, MappedRegion


class CognitiveColdHintResidencyController(AdvisoryResidencyController):
    """One-shot MADV_COLD for policy victims; never PAGEOUT or forced eviction."""
    name = "cognitive_cold_hint"

    def __init__(self, region: MappedRegion, page_size: int):
        super().__init__(region, page_size, "madv_cold")
        self.name = "cognitive_cold_hint"
        self.hinted: set[int] = set()

    def evict(self, page_id: int) -> bool:
        if page_id in self.hinted: return False
        accepted = super().demote(page_id)
        if accepted: self.hinted.add(page_id)
        return accepted

    def keep(self, page_id: int) -> None:
        super().keep(page_id)
        self.hinted.discard(page_id)


class LRUColdHintResidencyController(CognitiveColdHintResidencyController):
    name = "lru_cold_hint"
