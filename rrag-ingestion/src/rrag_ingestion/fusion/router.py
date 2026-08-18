"""ADR-0008: Adaptive Complexity-Based Query Routing.

Four-agent pipeline:
  Agent 1: QueryRouter    — intent + entity + domain classification
  Agent 2: ComplexityAnalyzer — weighted 0.0–1.0 complexity score
  Agent 3: StrategySelector   — engine selection from score + domain
  Agent 4: RetryEscalation    — escalate if quality below threshold

Routing table:
  < 0.3  → LightRAG local only           (50–200ms)
  0.3–0.5 → LightRAG high-level only     (100–500ms)
  0.5–0.7 → CoRAG greedy + LightRAG      (500ms–2s)
  ≥ 0.7  → full parallel (all engines)   (2–5s)

Domain override: healthcare / legal / finance always include KAG.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

_CLASSIFICATION_PROMPT = """\
Classify the following query across three dimensions.
Respond in this exact format, one item per line:
INTENT: <factual|analytical|comparative|exploratory>
ENTITIES: <comma-separated list of named entities, or NONE>
DOMAIN: <healthcare|legal|finance|general>

Query: {query}"""

_COMPLEXITY_PROMPT = """\
Score the following query on a 0.0–1.0 complexity scale.
Consider: entity count, temporal/numerical constraints, multi-hop indicators,
domain specificity, and query length.
Respond with only a single decimal number, e.g. 0.65

Query: {query}
Classification context: intent={intent}, entities={entities}, domain={domain}
Score:"""


@dataclass
class QueryClassification:
    intent: str = "factual"          # factual | analytical | comparative | exploratory
    entities: list[str] = field(default_factory=list)
    domain: str = "general"          # healthcare | legal | finance | general
    complexity: float = 0.0


@dataclass
class RoutingDecision:
    strategy: str                    # lightrag_local | lightrag_global | corag_lightrag | full_parallel
    engines: list[str]               # subset of: lightrag, corag, kag
    lightrag_mode: str = "local"     # local | global | hybrid
    corag_strategy: str = "greedy"   # greedy | best_of_n | tree
    classification: QueryClassification = field(default_factory=QueryClassification)
    escalation_level: int = 0        # 0=initial, 1=first escalation, 2=max


_DOMAIN_KAG_OVERRIDE = {"healthcare", "legal", "finance"}

_INTENT_COMPLEXITY_BOOST = {
    "factual": 0.0,
    "exploratory": 0.05,
    "analytical": 0.1,
    "comparative": 0.15,
}


class QueryRouter:
    """Four-agent adaptive complexity router (ADR-0008)."""

    def __init__(self, llm_client: object | None = None, model: str = "gpt-4o-mini") -> None:
        self._llm = llm_client
        self._model = model

    def _get_llm(self) -> object:
        if self._llm is not None:
            return self._llm
        from rrag_ingestion.services.openai_client import get_openai_client
        return get_openai_client()

    # ── Agent 1: Query Router ─────────────────────────────────────────────

    async def _classify_query(self, query: str) -> QueryClassification:
        """Extract intent, entities, and domain."""
        client = self._get_llm()
        prompt = _CLASSIFICATION_PROMPT.format(query=query)
        try:
            resp = await client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=128,
            )
            raw = resp.choices[0].message.content or ""
            intent = "factual"
            entities: list[str] = []
            domain = "general"

            for line in raw.strip().splitlines():
                line = line.strip()
                if line.startswith("INTENT:"):
                    val = line.split(":", 1)[1].strip().lower()
                    if val in ("factual", "analytical", "comparative", "exploratory"):
                        intent = val
                elif line.startswith("ENTITIES:"):
                    val = line.split(":", 1)[1].strip()
                    if val.upper() != "NONE":
                        entities = [e.strip() for e in val.split(",") if e.strip()]
                elif line.startswith("DOMAIN:"):
                    val = line.split(":", 1)[1].strip().lower()
                    if val in ("healthcare", "legal", "finance", "general"):
                        domain = val

            return QueryClassification(intent=intent, entities=entities, domain=domain)

        except Exception as e:
            logger.warning(f"Query classification failed, using defaults: {e}")
            return QueryClassification()

    # ── Agent 2: Complexity Analyzer ──────────────────────────────────────

    async def _score_complexity(self, query: str, cls: QueryClassification) -> float:
        """Weighted complexity scoring (0.0–1.0)."""
        # Heuristic pre-score (fast, no LLM)
        score = 0.0

        # Entity count weight: high
        score += min(len(cls.entities) * 0.08, 0.32)

        # Temporal/numerical indicators: high
        if re.search(r"\b(when|date|year|month|before|after|since|until|between|how many|how much|percent|%|\$|€|£)\b", query, re.I):
            score += 0.20

        # Multi-hop indicators: high
        if re.search(r"\b(because|therefore|caused by|leads to|result of|compared to|relationship between|difference between|why|how does|effect of)\b", query, re.I):
            score += 0.20

        # Domain specificity: medium
        if cls.domain in _DOMAIN_KAG_OVERRIDE:
            score += 0.10

        # Intent type: medium
        score += _INTENT_COMPLEXITY_BOOST.get(cls.intent, 0.0)

        # Query length proxy: low
        words = len(query.split())
        score += min(words / 100, 0.10)

        heuristic = min(score, 1.0)

        # LLM refinement for borderline scores (0.3–0.7)
        if 0.3 <= heuristic <= 0.7:
            try:
                client = self._get_llm()
                prompt = _COMPLEXITY_PROMPT.format(
                    query=query,
                    intent=cls.intent,
                    entities=", ".join(cls.entities) or "none",
                    domain=cls.domain,
                )
                resp = await client.chat.completions.create(
                    model=self._model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0,
                    max_tokens=8,
                )
                llm_score = float((resp.choices[0].message.content or "").strip())
                # Blend: 40% heuristic, 60% LLM
                return min(0.4 * heuristic + 0.6 * llm_score, 1.0)
            except Exception as e:
                logger.debug(f"LLM complexity scoring failed: {e}")

        return heuristic

    # ── Agent 3: Strategy Selector ────────────────────────────────────────

    def _select_strategy(
        self, complexity: float, cls: QueryClassification, escalation_level: int = 0
    ) -> RoutingDecision:
        """Map complexity score + domain to concrete routing."""
        # Apply escalation
        effective_complexity = min(complexity + escalation_level * 0.25, 1.0)

        engines: list[str]
        strategy: str
        lightrag_mode: str
        corag_strategy: str

        if effective_complexity < 0.3:
            strategy = "lightrag_local"
            engines = ["lightrag"]
            lightrag_mode = "local"
            corag_strategy = "greedy"
        elif effective_complexity < 0.5:
            strategy = "lightrag_global"
            engines = ["lightrag"]
            lightrag_mode = "global"
            corag_strategy = "greedy"
        elif effective_complexity < 0.7:
            strategy = "corag_lightrag"
            engines = ["corag", "lightrag"]
            lightrag_mode = "hybrid"
            corag_strategy = "greedy"
        else:
            strategy = "full_parallel"
            engines = ["lightrag", "corag", "kag"]
            lightrag_mode = "hybrid"
            corag_strategy = "best_of_n"

        # Domain override: always include KAG for regulated domains
        if cls.domain in _DOMAIN_KAG_OVERRIDE and "kag" not in engines:
            engines.append("kag")
            strategy += "+kag_domain_override"

        cls.complexity = effective_complexity

        return RoutingDecision(
            strategy=strategy,
            engines=engines,
            lightrag_mode=lightrag_mode,
            corag_strategy=corag_strategy,
            classification=cls,
            escalation_level=escalation_level,
        )

    # ── Agent 4: Retry & Escalation ───────────────────────────────────────

    def escalate(self, decision: RoutingDecision) -> RoutingDecision | None:
        """Escalate to next complexity tier. Returns None if already at max."""
        if decision.escalation_level >= 2:
            return None
        return self._select_strategy(
            decision.classification.complexity,
            decision.classification,
            escalation_level=decision.escalation_level + 1,
        )

    # ── Public API ────────────────────────────────────────────────────────

    async def route(self, query: str) -> RoutingDecision:
        """Classify query and return a routing decision."""
        cls = await self._classify_query(query)
        complexity = await self._score_complexity(query, cls)
        cls.complexity = complexity
        return self._select_strategy(complexity, cls)
