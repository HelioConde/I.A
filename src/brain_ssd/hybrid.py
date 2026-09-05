from __future__ import annotations

import json
import math
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from brain_ssd.progressive import ALIASES, NOISE_TERMS
from brain_ssd.router import SemanticIndex, normalize

SEMANTIC_GLOSSES = {
    "python.json": "texto estruturado objetos serializar decodificar chave valor documento",
    "python.files": "carregar gravar caminho conteúdo diretório leitura escrita",
    "python.sqlite": "persistir registros tabela consulta banco relacional local",
    "python.asyncio": "execução cooperativa não bloqueante paralelo simultâneo tarefa assíncrona",
    "processes": "programa execução tarefa pid serviço sistema",
    "networking": "conectividade servidor interface endereço comunicação",
    "nvme": "armazenamento flash baixa latência unidade estado sólido",
    "checksums": "soma criptográfica validar dano corrupção impressão digital",
    "dns": "resolver endereço internet site nome localização",
    "http": "serviço web endpoint protocolo requisição resposta",
    "genetics": "hereditariedade genes dna características biológicas",
}
CONTEXTUAL_ALIASES = {
    "server": {"linux": "servidor", "networking": "servidor"},
    "servidor": {"linux": "servidor", "networking": "servidor"},
    "base": {"programming": "sqlite", "storage": "filesystem"},
}
CONNECTORS = {"e", "depois", "tambem", "voltando", "agora", "entao"}
PRONOUNS = {"isso", "essa", "dessa", "isto", "assim", "ele", "ela"}


def _plain(text: str) -> str:
    return unicodedata.normalize("NFKD", text.casefold()).encode("ascii", "ignore").decode()


def _ngrams(text: str, size: int = 3) -> set[str]:
    compact = " " + " ".join(normalize(text)) + " "
    return {compact[index:index + size] for index in range(max(0, len(compact) - size + 1))}


def _edit_distance(left: str, right: str, limit: int = 2) -> int:
    if abs(len(left) - len(right)) > limit:
        return limit + 1
    previous = list(range(len(right) + 1))
    for row, a in enumerate(left, 1):
        current = [row]
        row_min = row
        for column, b in enumerate(right, 1):
            value = min(current[-1] + 1, previous[column] + 1, previous[column - 1] + (a != b))
            current.append(value)
            row_min = min(row_min, value)
        if row_min > limit:
            return limit + 1
        previous = current
    return previous[-1]


@dataclass
class ContextConcept:
    topic: str
    confidence: float = 1.0
    age: int = 0
    support_count: int = 1
    last_seen: int = 0
    current_query_support: float = 0.0


@dataclass
class HybridContextState:
    concepts: dict[str, ContextConcept] = field(default_factory=dict)
    turn_index: int = 0

    def begin_turn(self) -> None:
        self.turn_index += 1
        for concept in self.concepts.values():
            concept.age += 1
            concept.confidence *= 0.68
            concept.current_query_support = 0.0
        self.concepts = {topic: concept for topic, concept in self.concepts.items() if concept.confidence >= 0.08}

    def update(self, topics: tuple[str, ...], current_support: dict[str, float]) -> None:
        for topic in topics:
            support = min(1.0, current_support.get(topic, 0.5))
            if topic in self.concepts:
                concept = self.concepts[topic]
                concept.confidence = max(concept.confidence, support)
                concept.age = 0
                concept.support_count += 1
                concept.last_seen = self.turn_index
                concept.current_query_support = support
            else:
                self.concepts[topic] = ContextConcept(topic, support, 0, 1, self.turn_index, support)


@dataclass(frozen=True)
class CandidateEvidence:
    page_id: int
    topic: str
    lexical_score: float
    semantic_score: float
    context_score: float
    alias_score: float
    fuzzy_score: float
    domain_score: float
    coverage_contribution: float
    inhibition_score: float
    redundancy_penalty: float
    provenance: tuple[str, ...]
    combined_score: float


@dataclass(frozen=True)
class HybridResult:
    router: str
    activate_pages: tuple[int, ...]
    topics: tuple[str, ...]
    domains: tuple[str, ...]
    status: str
    resolved_level: str
    cascade_levels: tuple[str, ...]
    pre_rescue_confidence: float
    post_rescue_confidence: float
    pre_rescue_pages: tuple[int, ...]
    pre_rescue_topics: tuple[str, ...]
    partial_probability: float
    partial_signals: dict
    semantic_used: bool
    semantic_method: str
    semantic_rescue_without_budget_expansion: bool
    final_budget_mib: int
    expansion_count: int
    all_domain_used: bool
    reason_for_all_domain: str | None
    evidence: tuple[CandidateEvidence, ...]
    page_provenance: dict[int, tuple[str, ...]]
    current_query_topics: tuple[str, ...]
    context_expansion_topics: tuple[str, ...]
    alias_expansion_count: int
    fuzzy_match_count: int
    unknown_tokens: tuple[str, ...]
    timings_ms: dict


class SparseSemanticIndex:
    def __init__(self, index: SemanticIndex, method: str):
        if method not in {"tfidf", "char_ngram"}:
            raise ValueError(method)
        self.method = method
        self.documents: dict[str, str] = {}
        for topic, pages in index.topic_pages.items():
            page = index.pages[pages[0]]
            self.documents[topic] = " ".join([topic, page["domain"], *page["keywords"], SEMANTIC_GLOSSES.get(topic, "")])
        self.doc_tokens = {topic: Counter(normalize(text)) for topic, text in self.documents.items()}
        document_frequency = Counter(token for terms in self.doc_tokens.values() for token in terms)
        count = len(self.documents)
        self.idf = {token: math.log1p(count / frequency) for token, frequency in document_frequency.items()}
        self.doc_vectors = {topic: self._tfidf(terms) for topic, terms in self.doc_tokens.items()}
        self.char_vectors = {topic: _ngrams(text) for topic, text in self.documents.items()}
        self.serialized_size_bytes = len(json.dumps({"method": method, "documents": self.documents, "idf": self.idf}, sort_keys=True).encode())

    def _tfidf(self, terms: Counter[str]) -> dict[str, float]:
        return {token: count * self.idf.get(token, 0.0) for token, count in terms.items()}

    @staticmethod
    def _cosine(left: dict[str, float], right: dict[str, float]) -> float:
        numerator = sum(value * right.get(token, 0.0) for token, value in left.items())
        left_norm = math.sqrt(sum(value * value for value in left.values()))
        right_norm = math.sqrt(sum(value * value for value in right.values()))
        return numerator / (left_norm * right_norm) if left_norm and right_norm else 0.0

    def query(self, text: str) -> list[tuple[str, float]]:
        if self.method == "tfidf":
            query = self._tfidf(Counter(normalize(text)))
            scores = [(topic, self._cosine(query, vector)) for topic, vector in self.doc_vectors.items()]
        else:
            query = _ngrams(text)
            scores = [(topic, len(query & vector) / len(query | vector) if query | vector else 0.0) for topic, vector in self.char_vectors.items()]
        return sorted(scores, key=lambda item: (-item[1], item[0]))

    def estimated_resident_bytes(self) -> int:
        seen: set[int] = set()
        def size(value):
            if id(value) in seen:
                return 0
            seen.add(id(value))
            total = sys.getsizeof(value)
            if isinstance(value, dict):
                total += sum(size(key) + size(item) for key, item in value.items())
            elif isinstance(value, (list, tuple, set, Counter)):
                total += sum(size(item) for item in value)
            return total
        return size({"documents": self.documents, "idf": self.idf, "doc_vectors": self.doc_vectors, "char_vectors": self.char_vectors})


class HybridRetrievalV0:
    name = "hybrid_retrieval_v0"

    def __init__(self, index: SemanticIndex, semantic_method: str = "tfidf", semantic_threshold: float = 0.18, semantic_margin: float = 0.025, partial_threshold: float = 0.55):
        self.index = index
        self.semantic = SparseSemanticIndex(index, semantic_method)
        self.semantic_method = semantic_method
        self.semantic_threshold = semantic_threshold
        self.semantic_margin = semantic_margin
        self.partial_threshold = partial_threshold
        self.topic_terms: dict[str, set[str]] = {}
        self.term_topics: dict[str, set[str]] = defaultdict(set)
        self.topic_domain: dict[str, str] = {}
        for topic, pages in index.topic_pages.items():
            page = index.pages[pages[0]]
            terms = set(normalize(" ".join([topic, page["domain"], *page["keywords"]])))
            self.topic_terms[topic] = terms
            self.topic_domain[topic] = page["domain"]
            for term in terms:
                self.term_topics[term].add(topic)
        self.vocabulary = tuple(sorted(self.term_topics))
        self.ngram_terms: dict[str, set[str]] = defaultdict(set)
        for term in self.vocabulary:
            for gram in _ngrams(term):
                self.ngram_terms[gram].add(term)
        self.fuzzy_index_serialized_bytes = len(json.dumps({gram: sorted(terms) for gram, terms in self.ngram_terms.items()}, sort_keys=True).encode())

    def _partial(self, query: str, recognized_concepts: int) -> tuple[float, dict]:
        raw_plain = _plain(query)
        raw_tokens = tuple(normalize(query))
        lexical_tokens = set(raw_plain.replace("?", " ? ").split())
        signals = {
            "short_query": len(raw_tokens) <= 4,
            "pronoun": bool(lexical_tokens & PRONOUNS),
            "connector": bool(lexical_tokens & CONNECTORS),
            "ellipsis": query.strip().endswith(("?", "...")) and len(raw_tokens) <= 5,
            "low_independent_concepts": recognized_concepts <= 1,
        }
        probability = min(1.0, 0.22 * signals["short_query"] + 0.25 * signals["pronoun"] + 0.24 * signals["connector"] + 0.10 * signals["ellipsis"] + 0.19 * signals["low_independent_concepts"])
        return probability, signals

    def _fuzzy(self, token: str) -> tuple[str | None, float]:
        if len(token) < 4:
            return None, 0.0
        best_term, best_score = None, 0.0
        token_grams = _ngrams(token)
        candidates = set().union(*(self.ngram_terms.get(gram, ()) for gram in token_grams))
        for term in candidates:
            limit = 1 if max(len(token), len(term)) <= 6 else 2
            distance = _edit_distance(token, term, limit)
            edit_score = 1.0 - distance / max(len(token), len(term)) if distance <= limit else 0.0
            term_grams = _ngrams(term)
            ngram_score = len(token_grams & term_grams) / len(token_grams | term_grams) if token_grams | term_grams else 0.0
            score = max(edit_score, ngram_score if ngram_score >= 0.45 else 0.0)
            if score > best_score:
                best_term, best_score = term, score
        return (best_term, best_score) if best_score >= 0.67 else (None, 0.0)

    def route(self, query: str, state: HybridContextState | None = None, semantic_enabled: bool = True) -> HybridResult:
        total_started = time.perf_counter_ns()
        timings: dict[str, float] = {}
        levels: list[str] = []
        raw_tokens = tuple(normalize(query))
        informative = tuple(token for token in raw_tokens if token not in NOISE_TERMS)
        topic_scores: Counter[str] = Counter()
        topic_sources: dict[str, set[str]] = defaultdict(set)
        anchored_topics: set[str] = set()
        token_recognized: set[str] = set()
        alias_count = fuzzy_count = 0

        lexical_started = time.perf_counter_ns()
        for token in informative:
            if token in self.term_topics:
                token_recognized.add(token)
                if token in self.index.domain_pages or len(self.term_topics[token]) > 2:
                    continue
                for topic in self.term_topics[token]:
                    topic_scores[topic] += 3.0
                    topic_sources[topic].add("CURRENT_QUERY")
                    anchored_topics.add(topic)
        timings["exact_lexical"] = (time.perf_counter_ns() - lexical_started) / 1e6
        levels.append("LEVEL_0_EXACT")

        rescue_started = time.perf_counter_ns()
        unresolved = [token for token in informative if token not in token_recognized]
        plain_words = set(_plain(query).split())
        linguistic_partial = len(informative) <= 4 and bool(plain_words & (CONNECTORS | PRONOUNS))
        state_domains = {self.topic_domain[topic] for topic in state.concepts if topic in self.topic_domain} if state else set()
        for token in unresolved:
            alias = None if token in CONTEXTUAL_ALIASES else ALIASES.get(token)
            contextual_alias = False
            if alias is None and linguistic_partial and token in CONTEXTUAL_ALIASES:
                for domain, candidate in CONTEXTUAL_ALIASES[token].items():
                    if domain in state_domains:
                        alias = candidate
                        contextual_alias = True
                        break
            if alias and alias in self.term_topics:
                alias_count += 1
                token_recognized.add(token)
                if len(self.term_topics[alias]) > 2:
                    continue
                for topic in self.term_topics[alias]:
                    topic_scores[topic] += 2.6
                    topic_sources[topic].update(("ALIAS", "CONTEXT_BOOST" if contextual_alias else "CURRENT_QUERY"))
                    anchored_topics.add(topic)
                continue
            matched, similarity = self._fuzzy(token)
            if matched:
                fuzzy_count += 1
                token_recognized.add(token)
                for topic in self.term_topics[matched]:
                    topic_scores[topic] += (1.2 if len(self.term_topics[matched]) > 2 else 2.2) * similarity
                    topic_sources[topic].update(("FUZZY_MATCH", "CURRENT_QUERY"))
                    anchored_topics.add(topic)
        timings["fuzzy_alias"] = (time.perf_counter_ns() - rescue_started) / 1e6
        levels.append("LEVEL_1_FUZZY")

        # Keep concepts within a relative band, then protect coverage diversity.
        current_topics = tuple(dict.fromkeys([*self._select_topics(topic_scores, 0.48), *sorted(anchored_topics)]))
        partial_probability, partial_signals = self._partial(query, len(current_topics))
        context_expansion: list[str] = []
        context_started = time.perf_counter_ns()
        if state is not None:
            # Modulation never introduces a new concept.
            for topic in current_topics:
                concept = state.concepts.get(topic)
                if concept:
                    topic_scores[topic] += 0.45 * concept.confidence
                    topic_sources[topic].add("CONTEXT_BOOST")
                    concept.current_query_support = 1.0
            # Expansion is gated by explicit partial probability and weak current evidence.
            if partial_probability >= self.partial_threshold and len(current_topics) <= 1:
                context_limit = 1
                for topic, concept in sorted(state.concepts.items(), key=lambda item: (-item[1].confidence, item[1].age, item[0])):
                    if topic not in current_topics and concept.confidence >= 0.20 and len(context_expansion) < context_limit:
                        context_expansion.append(topic)
                        topic_scores[topic] += 0.9 * concept.confidence
                        topic_sources[topic].add("CONTEXT_EXPANSION")
        timings["context"] = (time.perf_counter_ns() - context_started) / 1e6
        levels.append("LEVEL_2_CONTEXT")

        unknown = tuple(token for token in informative if token not in token_recognized)
        recognized_ratio = len(token_recognized) / max(1, len(informative))
        novelty_high = recognized_ratio <= 0.25 and len(unknown) >= 2
        # A lone generic anchor plus mostly OOD text is a nearest-neighbor trap.
        trap_anchors = {"rede", "servidor", "server"}
        generic_only = bool(token_recognized) and token_recognized <= trap_anchors and len(unknown) >= 2
        pre_confidence = self._confidence(topic_scores, recognized_ratio, len(current_topics), novelty_high or generic_only)
        pre_topics = () if generic_only else tuple(current_topics)
        pre_pages = tuple(page for topic in pre_topics for page in self.index.topic_pages[topic][:2])[:4]

        semantic_used = False
        semantic_success = False
        semantic_scores: dict[str, float] = {}
        semantic_started = time.perf_counter_ns()
        need_semantic = semantic_enabled and not generic_only and (not current_topics or recognized_ratio < 0.60 or len(current_topics) > 3)
        if need_semantic:
            semantic_used = True
            ranked_semantic = self.semantic.query(query)
            top_score = ranked_semantic[0][1] if ranked_semantic else 0.0
            second_score = ranked_semantic[1][1] if len(ranked_semantic) > 1 else 0.0
            if top_score >= self.semantic_threshold and top_score - second_score >= self.semantic_margin:
                for topic, score in ranked_semantic[:3]:
                    if score >= max(self.semantic_threshold, top_score * 0.72):
                        semantic_scores[topic] = score
                        topic_scores[topic] += 3.2 * score
                        topic_sources[topic].add("SEMANTIC_RESCUE")
                semantic_success = bool(semantic_scores)
        timings["semantic"] = (time.perf_counter_ns() - semantic_started) / 1e6
        if semantic_used:
            levels.append("LEVEL_3_SEMANTIC")

        topics = tuple(dict.fromkeys([*self._select_topics(topic_scores, 0.52), *sorted(anchored_topics)]))
        # If semantic rescue produced a clear concept, drop weak unrelated concepts rather than expand budget.
        if semantic_scores:
            semantic_best = max(semantic_scores.values())
            rescued = {topic for topic, score in semantic_scores.items() if score >= semantic_best * 0.8}
            strong_current = {topic for topic in topics if "CURRENT_QUERY" in topic_sources[topic] and topic_scores[topic] >= max(topic_scores.values()) * 0.72}
            topics = tuple(sorted(rescued | strong_current, key=lambda topic: (-topic_scores[topic], topic)))

        if novelty_high and not semantic_success and not context_expansion:
            topics = ()
        if generic_only:
            topics = ()

        selection_started = time.perf_counter_ns()
        evidence: list[CandidateEvidence] = []
        selected: list[int] = []
        budget = 4
        expansion_count = 0
        if topics:
            required_capacity = 2 * len(topics)
            for candidate_budget in (4, 8, 16, 32):
                budget = candidate_budget
                if required_capacity <= budget:
                    break
                expansion_count += 1
                levels.append("LEVEL_4_BUDGET")
            for position in range(2):
                for topic in topics:
                    pages = self.index.topic_pages[topic]
                    if position >= len(pages) or len(selected) >= budget:
                        continue
                    page_id = pages[position]
                    sources = set(topic_sources[topic])
                    if len(topics) > 1:
                        sources.add("MULTI_DOMAIN")
                    lexical_score = topic_scores[topic]
                    semantic_score = semantic_scores.get(topic, 0.0)
                    context_score = 1.0 if sources & {"CONTEXT_BOOST", "CONTEXT_EXPANSION"} else 0.0
                    alias_score = 1.0 if "ALIAS" in sources else 0.0
                    fuzzy_score = 1.0 if "FUZZY_MATCH" in sources else 0.0
                    redundancy = 0.18 * position
                    combined = lexical_score + semantic_score + context_score + alias_score + fuzzy_score - redundancy
                    evidence.append(CandidateEvidence(page_id, topic, lexical_score, semantic_score, context_score, alias_score, fuzzy_score, 1.0, 1.0, 0.0, redundancy, tuple(sorted(sources)), combined))
                    selected.append(page_id)
        timings["selection_gate"] = (time.perf_counter_ns() - selection_started) / 1e6

        all_domain_used = False
        reason_for_all_domain = None
        status = "OK" if selected else "NO_KNOWLEDGE"
        activated_sources = {source for item in evidence for source in item.provenance}
        if semantic_used and semantic_success:
            resolved_level = "LEVEL_3_SEMANTIC"
        elif activated_sources & {"CONTEXT_BOOST", "CONTEXT_EXPANSION"}:
            resolved_level = "LEVEL_2_CONTEXT"
        elif alias_count or fuzzy_count:
            resolved_level = "LEVEL_1_FUZZY"
        else:
            resolved_level = "LEVEL_0_EXACT"
        # Limited fallback exists as safety but is not forced for novelty/OOD.
        if topics and len(selected) < min(2 * len(topics), budget):
            all_domain_used = True
            reason_for_all_domain = "concept_pages_incomplete"
            levels.append("LEVEL_5_LIMITED_DOMAIN")
            resolved_level = levels[-1]
            status = "INSUFFICIENT_RETRIEVAL_CONFIDENCE"
        elif not selected and not (novelty_high or generic_only):
            levels.append("LEVEL_6_INSUFFICIENT")
            resolved_level = levels[-1]
            status = "INSUFFICIENT_RETRIEVAL_CONFIDENCE"

        post_confidence = self._confidence(topic_scores, recognized_ratio, len(topics), not selected)
        timings["total"] = (time.perf_counter_ns() - total_started) / 1e6
        domains = tuple(dict.fromkeys(self.topic_domain[topic] for topic in topics))
        return HybridResult(self.name, tuple(selected), tuple(topics), domains, status, resolved_level, tuple(levels), pre_confidence, post_confidence, pre_pages, pre_topics, partial_probability, partial_signals, semantic_used, self.semantic_method, semantic_used and semantic_success and expansion_count == 0 and not all_domain_used, budget, expansion_count, all_domain_used, reason_for_all_domain, tuple(evidence), {item.page_id: item.provenance for item in evidence}, tuple(topic for topic in topics if "CURRENT_QUERY" in topic_sources[topic]), tuple(context_expansion), alias_count, fuzzy_count, unknown, timings)

    @staticmethod
    def _select_topics(scores: Counter[str], relative_threshold: float) -> tuple[str, ...]:
        if not scores:
            return ()
        maximum = max(scores.values())
        return tuple(topic for topic, score in sorted(scores.items(), key=lambda item: (-item[1], item[0])) if score >= maximum * relative_threshold)

    @staticmethod
    def _confidence(scores: Counter[str], coverage: float, concept_count: int, novelty: bool) -> float:
        if not scores or novelty:
            return 0.0
        ranked = sorted(scores.values(), reverse=True)
        gap = (ranked[0] - ranked[1]) / ranked[0] if len(ranked) > 1 and ranked[0] else 1.0
        return max(0.0, min(1.0, 0.55 * coverage + 0.25 * gap + 0.20 * min(1.0, concept_count / 2)))
