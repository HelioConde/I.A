from __future__ import annotations

import math
import random
import re
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Protocol

TOKEN_RE = re.compile(r"[a-z0-9+#]+")
STOPWORDS = {"a", "ao", "as", "com", "como", "da", "de", "do", "e", "em", "no", "o", "os", "para", "por", "um", "uma", "isso"}


def normalize(text: str) -> list[str]:
    plain = unicodedata.normalize("NFKD", text.casefold()).encode("ascii", "ignore").decode()
    return [token for token in TOKEN_RE.findall(plain) if token not in STOPWORDS]


@dataclass(frozen=True)
class RouteResult:
    router: str
    domains: tuple[tuple[str, float], ...]
    topics: tuple[tuple[str, float], ...]
    candidate_pages: tuple[tuple[int, float, str], ...]
    confidence: float
    inhibited_domains: tuple[str, ...] = ()
    predicted_next_pages: tuple[int, ...] = ()
    metadata: dict = field(default_factory=dict)


class RouterBackend(Protocol):
    name: str
    def route(self, query: str, cognitive_state=None) -> RouteResult: ...


class SemanticIndex:
    def __init__(self, manifest: dict):
        self.pages = {page["page_id"]: page for page in manifest["pages"]}
        self.page_count = len(self.pages)
        self.inverted: dict[str, list[int]] = defaultdict(list)
        self.domain_pages: dict[str, list[int]] = defaultdict(list)
        self.topic_pages: dict[str, list[int]] = defaultdict(list)
        for page in manifest["pages"]:
            self.domain_pages[page["domain"]].append(page["page_id"])
            for topic in page["topics"]:
                self.topic_pages[topic].append(page["page_id"])
            terms = set(normalize(" ".join([page["domain"], *page["topics"], *page["keywords"]])))
            for term in terms:
                self.inverted[term].append(page["page_id"])
        self.serialized_size_bytes = len(__import__("json").dumps(manifest, ensure_ascii=False, separators=(",", ":")).encode())

    def estimated_resident_bytes(self) -> int:
        seen = set()
        def size(obj):
            identity = id(obj)
            if identity in seen:
                return 0
            seen.add(identity)
            total = sys.getsizeof(obj)
            if isinstance(obj, dict):
                total += sum(size(k) + size(v) for k, v in obj.items())
            elif isinstance(obj, (list, tuple, set)):
                total += sum(size(item) for item in obj)
            return total
        return size({"pages": self.pages, "inverted": self.inverted, "domains": self.domain_pages, "topics": self.topic_pages})


class LexicalRouter:
    name = "lexical"
    def __init__(self, index: SemanticIndex, candidate_limit: int = 256):
        self.index = index
        self.candidate_limit = candidate_limit

    def route(self, query: str, cognitive_state=None) -> RouteResult:
        tokens = normalize(query)
        scores: Counter[int] = Counter()
        reasons: dict[int, list[str]] = defaultdict(list)
        for token in tokens:
            postings = self.index.inverted.get(token, ())
            if not postings:
                continue
            idf = math.log1p(self.index.page_count / len(postings))
            for page_id in postings:
                scores[page_id] += idf
                reasons[page_id].append(token)
        if cognitive_state is not None:
            for page_id, strength in cognitive_state.page_strength.items():
                scores[page_id] += 0.35 * strength
                reasons[page_id].append("state")
            if cognitive_state.current_domain:
                for page_id in self.index.domain_pages.get(cognitive_state.current_domain, ()):
                    scores[page_id] += 0.08 * cognitive_state.topic_confidence
        ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:self.candidate_limit]
        domain_scores: Counter[str] = Counter()
        topic_scores: Counter[str] = Counter()
        for page_id, score in ranked:
            page = self.index.pages[page_id]
            domain_scores[page["domain"]] += score
            for topic in page["topics"]:
                topic_scores[topic] += score
        domains = tuple(domain_scores.most_common())
        topics = tuple(topic_scores.most_common())
        total = sum(domain_scores.values())
        confidence = domains[0][1] / total if domains and total else 0.0
        inhibited = tuple(domain for domain in self.index.domain_pages if domains and domain != domains[0][0] and confidence >= 0.45)
        candidates = tuple((page_id, score, "+".join(sorted(set(reasons[page_id])))) for page_id, score in ranked)
        predicted = tuple(self.index.pages[page_id]["related_pages"][0] for page_id, _ in ranked[:8])
        return RouteResult(self.name, domains, topics, candidates, confidence, inhibited, predicted, {"tokens": tokens})


class BenchmarkRouter:
    def __init__(self, name: str, index: SemanticIndex, queries: list[dict], seed: int = 20260807):
        self.name, self.index, self.seed = name, index, seed
        self.truth = {item["query"]: item for item in queries}

    def route(self, query: str, cognitive_state=None) -> RouteResult:
        truth = self.truth[query]
        if self.name == "oracle":
            ids = [*truth["required_pages"], *truth["optional_pages"]]
            candidates = tuple((page_id, 1.0 if page_id in truth["required_pages"] else 0.8, "ground_truth") for page_id in ids)
        elif self.name == "all_domain":
            ids = self.index.domain_pages.get(truth["expected_domain"], [])
            candidates = tuple((page_id, 1.0, "expected_domain") for page_id in ids)
        elif self.name == "all_brain":
            candidates = tuple((page_id, 1.0, "all_brain") for page_id in range(self.index.page_count))
        elif self.name == "random_k":
            ids = list(range(self.index.page_count))
            random.Random(self.seed ^ sum(query.encode())).shuffle(ids)
            candidates = tuple((page_id, 1.0, "random") for page_id in ids)
        else:
            raise ValueError(self.name)
        domain = truth["expected_domain"]
        domains = ((domain, 1.0),) if domain else ()
        topics = tuple((topic, 1.0) for topic in truth["expected_topics"])
        return RouteResult(self.name, domains, topics, candidates, 1.0 if candidates else 0.0)
