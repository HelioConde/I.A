from __future__ import annotations

import math
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from brain_ssd.gating import CognitiveState
from brain_ssd.router import LexicalRouter, RouteResult, SemanticIndex, normalize

ALIASES = {
    "pyhton": "python", "abriir": "abrir", "carregar": "arquivo", "caminho": "pathlib",
    "documento": "json", "decodificar": "parse", "persistir": "salvar", "registros": "sqlite",
    "base": "banco", "hash": "checksum", "validando": "integridade", "conectividade": "rede",
    "sem": "asyncio", "bloquear": "asyncio", "nonblocking": "asyncio", "assincrono": "asyncio",
    "concorrentemente": "concorrencia", "executar": "asyncio", "atraves": "http", "script": "python",
    "processos": "processo", "conteudo": "arquivo", "detectar": "integridade", "genes": "gene",
}
PARTIAL_MARKERS = {"e", "isso", "essa", "dessa", "depois", "tambem", "voltando", "agora"}
NOISE_TERMS = {"favor", "obrigado", "talvez", "agora", "depois", "isso", "por", "numa", "usando", "dados", "tarefa", "fazer", "ver"}


@dataclass(frozen=True)
class QueryAnalysis:
    raw_tokens: tuple[str, ...]
    expanded_tokens: tuple[str, ...]
    known_tokens: tuple[str, ...]
    unknown_tokens: tuple[str, ...]
    concepts: tuple[str, ...]
    domains: tuple[str, ...]
    groups: tuple[tuple[str, ...], ...]
    partial_cue: bool
    context_terms: tuple[str, ...]
    new_topic_score: float
    timings_ms: dict


@dataclass(frozen=True)
class ConfidenceSignals:
    absolute_top_score: float
    score_gap: float
    concept_count: int
    domain_count: int
    query_coverage: float
    unknown_token_ratio: float
    domain_conflict: float
    partial_cue: bool
    state_used: bool
    topic_stability: float
    confidence: float


@dataclass(frozen=True)
class ProgressiveResult:
    router: str
    activate_pages: tuple[int, ...]
    candidate_pages: tuple[tuple[int, float, str], ...]
    domains: tuple[str, ...]
    topics: tuple[str, ...]
    initial_budget_mib: int
    final_budget_mib: int
    budget_used_mib: int
    expansion_count: int
    expansion_reasons: tuple[str, ...]
    fallback_levels: tuple[str, ...]
    status: str
    analysis: QueryAnalysis
    signals: ConfidenceSignals
    hysteresis_budget_fraction: float
    kept_by_hysteresis: tuple[int, ...]
    timings_ms: dict


class LexicalProgressiveRouter:
    name = "lexical_progressive"

    def __init__(self, index: SemanticIndex, aliases: dict[str, str] | None = None):
        self.index = index
        self.lexical = LexicalRouter(index)
        self.aliases = dict(ALIASES if aliases is None else aliases)
        self.term_topics: dict[str, set[str]] = defaultdict(set)
        self.topic_terms: dict[str, set[str]] = defaultdict(set)
        self.topic_domains: dict[str, str] = {}
        for page in index.pages.values():
            topic = page["topics"][0]
            self.topic_domains[topic] = page["domain"]
            terms = set(normalize(" ".join([topic, *page["keywords"]])))
            self.topic_terms[topic].update(terms)
            for term in terms:
                self.term_topics[term].add(topic)

    def analyze(self, query: str, state: CognitiveState | None = None, use_context: bool = True) -> QueryAnalysis:
        started = time.perf_counter_ns()
        raw = tuple(normalize(query))
        normalized_plain = query.casefold()
        expanded = tuple(dict.fromkeys([self.aliases.get(token, token) for token in raw]))
        known = tuple(token for token in expanded if token in self.term_topics)
        unknown = tuple(token for token in expanded if token not in self.term_topics and token not in NOISE_TERMS)
        partial = len(raw) <= 4 and (bool(set(normalize(normalized_plain)) & PARTIAL_MARKERS) or len(known) <= 1)
        context_terms: list[str] = []
        if use_context and state is not None and (partial or len(known) <= 1):
            for topic in state.current_topics[:3]:
                context_terms.extend(part for part in normalize(topic) if part not in expanded)
            if state.current_domain and state.current_domain not in expanded:
                context_terms.append(state.current_domain)
            context_terms = list(dict.fromkeys(context_terms))[:4]
        effective = tuple(dict.fromkeys([*expanded, *context_terms]))
        topic_scores: Counter[str] = Counter()
        broad_terms = set(self.index.domain_pages)
        for token in effective:
            if token in broad_terms:
                continue
            for topic in self.term_topics.get(token, ()):
                topic_scores[topic] += 1
        if topic_scores:
            maximum = max(topic_scores.values())
            concepts = tuple(topic for topic, value in sorted(topic_scores.items(), key=lambda item: (-item[1], item[0])) if value >= max(1, maximum * 0.5))
        else:
            concepts = ()
        domains = tuple(dict.fromkeys(self.topic_domains[topic] for topic in concepts))
        groups = tuple(tuple(group) for group in self._groups(query, effective))
        previous_evidence = sum(1 for topic in concepts if state and topic in state.current_topics)
        new_evidence = sum(1 for topic in concepts if not state or topic not in state.current_topics)
        new_topic_score = new_evidence / max(1, previous_evidence + new_evidence)
        return QueryAnalysis(raw, effective, known, unknown, concepts, domains, groups, partial, tuple(context_terms), new_topic_score, {"decomposition": (time.perf_counter_ns() - started) / 1e6})

    @staticmethod
    def _groups(query: str, tokens: tuple[str, ...]) -> list[list[str]]:
        # Conjunction boundaries are recorded; retrieval still scores every group independently.
        chunks = query.casefold().replace(",", " e ").split(" e ")
        groups = [normalize(chunk) for chunk in chunks if normalize(chunk)]
        return groups or [list(tokens)]

    def _rank(self, analysis: QueryAnalysis) -> tuple[list[tuple[int, float, str]], dict[str, float]]:
        scores: Counter[int] = Counter()
        covered_by_page: dict[int, set[str]] = defaultdict(set)
        for token in analysis.expanded_tokens:
            postings = self.index.inverted.get(token, ())
            if not postings:
                continue
            weight = math.log1p(self.index.page_count / len(postings))
            for page_id in postings:
                scores[page_id] += weight
                covered_by_page[page_id].add(token)
        # Decomposed concepts receive independent representation, preventing one dense topic
        # from consuming the entire top-k of a multi-topic query.
        ranked: list[tuple[int, float, str]] = []
        seen: set[int] = set()
        concept_strength: dict[str, float] = {}
        topic_ranked: dict[str, list[int]] = {}
        for topic in analysis.concepts:
            pages = self.index.topic_pages[topic]
            topic_score = sum(1 for token in analysis.expanded_tokens if token in self.topic_terms[topic])
            concept_strength[topic] = float(topic_score)
            topic_ranked[topic] = sorted(pages, key=lambda pid: (-scores[pid], pid))[:4]
        for position in range(4):
            for topic in analysis.concepts:
                if position >= len(topic_ranked[topic]):
                    continue
                page_id = topic_ranked[topic][position]
                if page_id not in seen:
                    ranked.append((page_id, scores[page_id] + concept_strength[topic], f"concept:{topic}"))
                    seen.add(page_id)
        for page_id, value in scores.most_common():
            if page_id not in seen:
                ranked.append((page_id, value, "lexical:" + "+".join(sorted(covered_by_page[page_id]))))
                seen.add(page_id)
        return ranked, concept_strength

    def _signals(self, analysis: QueryAnalysis, ranked: list[tuple[int, float, str]], selected: list[int]) -> ConfidenceSignals:
        scores = [item[1] for item in ranked]
        top = scores[0] if scores else 0.0
        gap = top - scores[1] if len(scores) > 1 else top
        selected_terms = set()
        for page_id in selected:
            page = self.index.pages[page_id]
            selected_terms.update(normalize(" ".join([page["domain"], *page["topics"], *page["keywords"]])))
        informative = set(analysis.expanded_tokens) - NOISE_TERMS
        covered = len(informative & selected_terms) / len(informative) if informative else 0.0
        unknown_ratio = len(analysis.unknown_tokens) / max(1, len(analysis.raw_tokens))
        conflict = 1.0 - (1.0 / max(1, len(analysis.domains)))
        stability = 1.0 - analysis.new_topic_score
        confidence = max(0.0, min(1.0, 0.55 * covered + 0.20 * min(1.0, len(analysis.concepts) / 2) + 0.15 * (1 - unknown_ratio) + 0.10 * (1 - conflict)))
        return ConfidenceSignals(top, gap, len(analysis.concepts), len(analysis.domains), covered, unknown_ratio, conflict, analysis.partial_cue, bool(analysis.context_terms), stability, confidence)

    @staticmethod
    def _hysteresis_fraction(budget: int, confidence: float, new_topic_score: float) -> float:
        base = {4: 0.08, 8: 0.18, 16: 0.25, 32: 0.30}.get(budget, 0.20)
        if new_topic_score >= 0.75:
            return 0.0
        return base * confidence

    def route(self, query: str, state: CognitiveState | None = None, use_context: bool = True, use_hysteresis: bool = True) -> ProgressiveResult:
        total_start = time.perf_counter_ns()
        analysis = self.analyze(query, state, use_context)
        rank_start = time.perf_counter_ns()
        ranked, concept_strength = self._rank(analysis)
        rank_ms = (time.perf_counter_ns() - rank_start) / 1e6
        if not analysis.known_tokens and not analysis.context_terms:
            signals = self._signals(analysis, ranked, [])
            return ProgressiveResult(self.name, (), tuple(ranked), (), (), 4, 4, 0, 0, (), ("explicit_failure",), "NO_KNOWLEDGE", analysis, signals, 0.0, (), {**analysis.timings_ms, "ranking": rank_ms, "total": (time.perf_counter_ns() - total_start) / 1e6})

        selected: list[int] = []
        reasons: list[str] = []
        levels: list[str] = ["lexical"]
        stages = (4, 8, 16, 32)
        final_budget = 4
        expansion_count = 0
        confidence_ns = 0
        planning_ns = 0
        signal_started = time.perf_counter_ns()
        signals = self._signals(analysis, ranked, selected)
        confidence_ns += time.perf_counter_ns() - signal_started
        complete = False
        for stage_index, budget in enumerate(stages):
            planning_started = time.perf_counter_ns()
            final_budget = budget
            # Two pages per detected concept, with the stage as a ceiling rather than a target.
            desired = min(budget, max(1, 2 * len(analysis.concepts)))
            selected = [page_id for page_id, _, _ in ranked[:desired]]
            planning_ns += time.perf_counter_ns() - planning_started
            signal_started = time.perf_counter_ns()
            signals = self._signals(analysis, ranked, selected)
            confidence_ns += time.perf_counter_ns() - signal_started
            selected_topics = Counter(self.index.pages[page_id]["topics"][0] for page_id in selected)
            complete = signals.query_coverage >= 0.80 and all(selected_topics[topic] >= 2 for topic in analysis.concepts) and len(analysis.concepts) > 0 and signals.domain_conflict <= 0.5
            if complete:
                break
            if stage_index < len(stages) - 1:
                expansion_count += 1
                reasons.append("coverage_below_0.80" if signals.query_coverage < 0.80 else "concept_evidence_incomplete")
                levels.append("budget_expansion")

        status = "OK"
        if not complete:
            planning_started = time.perf_counter_ns()
            candidate_domains = analysis.domains[:2]
            if candidate_domains:
                levels.append("all_domain_limited")
                domain_lists = [self.index.domain_pages[domain] for domain in analysis.domains[:3]]
                for position in range(max(map(len, domain_lists), default=0)):
                    for pages in domain_lists:
                        if position < len(pages) and pages[position] not in selected and len(selected) < 32:
                            selected.append(pages[position])
                final_budget = 32
                planning_ns += time.perf_counter_ns() - planning_started
                signal_started = time.perf_counter_ns()
                signals = self._signals(analysis, ranked, selected)
                confidence_ns += time.perf_counter_ns() - signal_started
            if signals.query_coverage < 0.80:
                levels.append("explicit_failure")
                status = "INSUFFICIENT_RETRIEVAL_CONFIDENCE"

        fraction = self._hysteresis_fraction(final_budget, signals.confidence, analysis.new_topic_score) if state is not None and use_hysteresis else 0.0
        retained: list[int] = []
        if fraction > 0:
            planning_started = time.perf_counter_ns()
            capacity = min(final_budget - len(selected), int(final_budget * fraction))
            for page_id, strength in sorted(state.page_strength.items(), key=lambda item: (-item[1], item[0])):
                if page_id not in selected and strength >= 0.18 and len(retained) < capacity:
                    retained.append(page_id)
            selected.extend(retained)
            planning_ns += time.perf_counter_ns() - planning_started
        topics = tuple(analysis.concepts)
        domains = tuple(analysis.domains)
        timings = {**analysis.timings_ms, "ranking": rank_ms, "confidence": confidence_ns / 1e6, "activation_planning": planning_ns / 1e6, "confidence_and_fallback": (confidence_ns + planning_ns) / 1e6, "total": (time.perf_counter_ns() - total_start) / 1e6}
        return ProgressiveResult(self.name, tuple(selected), tuple(ranked), domains, topics, 4, final_budget, len(selected), expansion_count, tuple(reasons), tuple(levels), status, analysis, signals, fraction, tuple(retained), timings)

    def as_route_result(self, result: ProgressiveResult) -> RouteResult:
        candidates = tuple((page_id, score, reason) for page_id, score, reason in result.candidate_pages)
        return RouteResult(self.name, tuple((domain, 1.0) for domain in result.domains), tuple((topic, 1.0) for topic in result.topics), candidates, result.signals.confidence, metadata={"progressive": True})
