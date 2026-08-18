"""ADR-0021: Generation & Synthesis Layer Architecture.

Four-component pipeline:
  1. ContextAggregator  — deduplicate, rank, and select evidence across engines
  2. ResponseSynthesizer — route to fast/capable model, adapt prompt by evidence type
  3. HallucinationGuard — claim extraction → verification → revision (ADR-0015)
  4. CitationLinker     — trace claims → KG nodes / chunks → source docs (ADR-0010)

Evidence ranking weights:
  retrieval_confidence 40%  — engine's relevance score
  engine_reliability   20%  — per-engine historical accuracy (static default)
  freshness            20%  — document recency (timestamp normalised)
  corroboration        20%  — count of engines that also returned this chunk

Quality threshold for retry/escalation: 0.70 (0.85 for regulated domains).
Cost target: 60–70% reduction via tiered model routing (fast for simple queries).
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from rrag_ingestion.generation.hallucination_guard import GuardResult, HallucinationGuard

logger = logging.getLogger(__name__)

_ENGINE_RELIABILITY: dict[str, float] = {
    "lightrag_local": 0.80,
    "lightrag_global": 0.75,
    "corag": 0.85,
    "kag": 0.90,
    "fusion": 0.88,
    "vector": 0.70,
    "graph": 0.75,
}

_SIMPLE_QUERY_PROMPT = """\
You are a precise research assistant. Answer the user's question using ONLY the
provided context. Cite document numbers inline as [1], [2], etc.

Context:
{context}

Question: {query}

Answer:"""

_COMPLEX_QUERY_PROMPT = """\
You are an expert research analyst. The question requires multi-step reasoning.
Using the provided evidence, construct a detailed, well-reasoned answer.
Cite each claim with document numbers [1], [2], etc. If evidence chains
exist, present them as a logical sequence.

Evidence:
{context}

Question: {query}

Detailed answer:"""

_KAG_PROOF_PROMPT = """\
You are synthesizing a response from structured knowledge graph reasoning results.
Present the findings as a logical argument with computation steps where applicable.
Cite each fact with document numbers [1], [2], etc.

Knowledge graph evidence:
{context}

Question: {query}

Reasoned answer:"""


@dataclass
class EvidencePiece:
    chunk_id: str
    content: str
    score: float
    source_id: str = ""
    document_id: str = ""
    engine: str = ""
    timestamp: float = 0.0
    metadata: dict = field(default_factory=dict)


@dataclass
class Citation:
    number: int
    chunk_id: str
    source_id: str
    document_id: str
    section: str = ""
    page: int = 0


@dataclass
class SynthesisResult:
    answer: str
    citations: list[Citation]
    quality_score: float
    quality_breakdown: dict
    guard_result: GuardResult | None
    evidence_count: int
    model_used: str
    duration_ms: float
    strategy: str = "synthesis"


class ContextAggregator:
    """Step 1: deduplicate and rank evidence across retrieval engines (ADR-0021)."""

    def __init__(self, max_context_tokens: int = 8000) -> None:
        self.max_context_tokens = max_context_tokens
        self._token_chars = 4

    def _estimate_tokens(self, text: str) -> int:
        return max(1, len(text) // self._token_chars)

    def _freshness_score(self, timestamp: float) -> float:
        """Normalise doc age: docs from the last 30 days score 1.0, older → 0.0."""
        if not timestamp:
            return 0.5
        age_days = (time.time() - timestamp) / 86400
        return max(0.0, 1.0 - age_days / 30.0)

    def _rank_score(self, piece: EvidencePiece, corroboration: int) -> float:
        reliability = _ENGINE_RELIABILITY.get(piece.engine, 0.70)
        freshness = self._freshness_score(piece.timestamp)
        corroboration_score = min(1.0, corroboration / 3.0)  # 3+ engines → max
        return (
            0.40 * piece.score
            + 0.20 * reliability
            + 0.20 * freshness
            + 0.20 * corroboration_score
        )

    def aggregate(self, raw_sources: list[dict]) -> list[EvidencePiece]:
        """Deduplicate by chunk_id, rank, and select top evidence pieces."""
        # Count corroboration (how many engines returned this chunk_id)
        corroboration: dict[str, int] = {}
        for src in raw_sources:
            cid = src.get("id", "")
            corroboration[cid] = corroboration.get(cid, 0) + 1

        # Deduplicate: keep highest-score entry per chunk_id
        seen: dict[str, EvidencePiece] = {}
        for src in raw_sources:
            cid = src.get("id", "")
            content = src.get("content", "")
            if not content:
                continue
            meta = src.get("metadata", {})
            piece = EvidencePiece(
                chunk_id=cid,
                content=content,
                score=src.get("score", 0.5),
                source_id=src.get("id", cid),
                document_id=meta.get("document_id", ""),
                engine=meta.get("source", meta.get("engine", "vector")),
                timestamp=meta.get("timestamp", 0.0),
                metadata=meta,
            )
            if cid not in seen or piece.score > seen[cid].score:
                seen[cid] = piece

        # Rank
        ranked = sorted(
            seen.values(),
            key=lambda p: self._rank_score(p, corroboration.get(p.chunk_id, 1)),
            reverse=True,
        )

        # Greedy selection within context budget (already ranked by relevance +
        # diversity-aware corroboration score above).
        selected: list[EvidencePiece] = []
        token_budget = self.max_context_tokens

        for piece in ranked:
            piece_tokens = self._estimate_tokens(piece.content)
            if piece_tokens > token_budget:
                continue
            selected.append(piece)
            token_budget -= piece_tokens
            if token_budget <= 0:
                break

        return selected


class CitationLinker:
    """Step 4: trace response claims to source documents via MutualIndex (ADR-0021 + ADR-0010)."""

    def __init__(self, mutual_index: Any | None = None) -> None:
        self._mutual = mutual_index

    def build_citations(self, evidence: list[EvidencePiece]) -> list[Citation]:
        """Build a numbered citation list from evidence pieces."""
        citations: list[Citation] = []
        for i, piece in enumerate(evidence, start=1):
            citations.append(Citation(
                number=i,
                chunk_id=piece.chunk_id,
                source_id=piece.source_id,
                document_id=piece.document_id,
                section=piece.metadata.get("section", ""),
                page=piece.metadata.get("page", 0),
            ))
        return citations

    def append_footnotes(self, answer: str, citations: list[Citation]) -> str:
        """Append a footnote-style sources section to the answer."""
        if not citations:
            return answer
        lines = ["\n\n**Sources:**"]
        for c in citations:
            doc_ref = c.document_id or c.source_id or c.chunk_id
            section = f", §{c.section}" if c.section else ""
            page = f", p.{c.page}" if c.page else ""
            lines.append(f"[{c.number}] {doc_ref}{section}{page}")
        return answer + "\n".join(lines)


class ResponseSynthesizer:
    """Step 2: generate response with adaptive prompting and tiered model routing (ADR-0021)."""

    async def synthesize(
        self,
        query: str,
        evidence: list[EvidencePiece],
        query_complexity: float = 0.5,
        engine_strategy: str = "vector",
    ) -> tuple[str, str]:
        """Return (answer, model_used).

        Model routing: complexity < 0.3 → fast model, ≥ 0.3 → capable model.
        Prompt style: kag strategy → proof chain, complex → multi-hop, else simple.
        """
        from rrag_ingestion.services import llm_service

        # Build context block with citation markers
        context_parts = [
            f"[{i + 1}] {piece.content}" for i, piece in enumerate(evidence)
        ]
        context = "\n\n".join(context_parts)

        # Select prompt template by strategy/complexity
        if "kag" in engine_strategy.lower():
            prompt = _KAG_PROOF_PROMPT.format(context=context, query=query)
        elif query_complexity >= 0.5:
            prompt = _COMPLEX_QUERY_PROMPT.format(context=context, query=query)
        else:
            prompt = _SIMPLE_QUERY_PROMPT.format(context=context, query=query)

        # Tier routing: simple queries (< 0.3) → fast model
        tier = "fast" if query_complexity < 0.3 else "capable"

        resp = await llm_service.completion(
            messages=[{"role": "user", "content": prompt}],
            tier=tier,
            temperature=0.3,
            max_tokens=2048,
        )
        answer = (resp.choices[0].message.content or "").strip()
        model_used = llm_service.select_model(tier)
        return answer, model_used


class GenerationPipeline:
    """Full 4-component generation and synthesis pipeline (ADR-0021).

    Usage:
        pipeline = GenerationPipeline(redis=app.state.redis)
        result = await pipeline.run(
            query="...",
            sources=[{id, content, score, metadata}, ...],
            query_complexity=0.6,   # from ADR-0008 router score
            engine_strategy="fusion",
            domain="healthcare",    # for guard threshold
            tenant_id="ws-123",     # for L2 cache key
        )
    """

    def __init__(
        self,
        redis: Any | None = None,
        mutual_index: Any | None = None,
        enable_cache: bool = True,
        enable_guard: bool = True,
        max_context_tokens: int = 8000,
    ) -> None:
        self._aggregator = ContextAggregator(max_context_tokens=max_context_tokens)
        self._synthesizer = ResponseSynthesizer()
        self._guard = HallucinationGuard()
        self._citation_linker = CitationLinker(mutual_index=mutual_index)
        self._enable_cache = enable_cache and redis is not None
        self._enable_guard = enable_guard

        if self._enable_cache:
            from rrag_ingestion.generation.cache import QueryCache
            self._cache = QueryCache(redis=redis)
        else:
            self._cache = None

    @staticmethod
    def _derive_entity_tags(evidence: list[EvidencePiece]) -> list[str]:
        """Collect entity/document identifiers from evidence for cache invalidation.

        Graph-sourced evidence (engine == 'knowledge_graph'/'graph'/'kag') uses the
        entity name as its id; those names match what IncrementalUpdater passes to
        invalidate_by_entities. Document ids are also tagged so document-level
        updates evict related cache entries.
        """
        tags: set[str] = set()
        for e in evidence:
            engine = (e.engine or "").lower()
            if engine in ("knowledge_graph", "graph", "kag", "lightrag_local", "lightrag_global"):
                if e.chunk_id:
                    tags.add(e.chunk_id)
            entities = e.metadata.get("entities") or e.metadata.get("entity_names")
            if isinstance(entities, list):
                tags.update(str(x) for x in entities if x)
            if e.document_id:
                tags.add(e.document_id)
        return [t for t in tags if t]

    async def run(
        self,
        query: str,
        sources: list[dict],
        query_complexity: float = 0.5,
        engine_strategy: str = "vector",
        domain: str = "default",
        tenant_id: str = "",
        entity_tags: list[str] | None = None,
    ) -> SynthesisResult:
        start = time.monotonic()

        # ── Cache lookup (L2/L3) ─────────────────────────────────────────────
        if self._cache:
            cached = await self._cache.get(query, tenant_id)
            if cached:
                return SynthesisResult(
                    answer=cached.answer,
                    citations=[],
                    quality_score=1.0,
                    quality_breakdown={"cache_hit": True, "cache_level": cached.cache_level},
                    guard_result=None,
                    evidence_count=0,
                    model_used="cached",
                    duration_ms=round((time.monotonic() - start) * 1000, 2),
                    strategy=cached.strategy,
                )

        # ── Step 1: Aggregate evidence ────────────────────────────────────────
        evidence = self._aggregator.aggregate(sources)
        if not evidence:
            return SynthesisResult(
                answer="I could not find relevant evidence to answer this question.",
                citations=[],
                quality_score=0.0,
                quality_breakdown={},
                guard_result=None,
                evidence_count=0,
                model_used="none",
                duration_ms=round((time.monotonic() - start) * 1000, 2),
            )

        # ── Step 2: Synthesize response ───────────────────────────────────────
        answer, model_used = await self._synthesizer.synthesize(
            query=query,
            evidence=evidence,
            query_complexity=query_complexity,
            engine_strategy=engine_strategy,
        )

        # ── Step 3: Hallucination guard ───────────────────────────────────────
        guard_result: GuardResult | None = None
        if self._enable_guard:
            source_dicts = [
                {"id": e.chunk_id, "content": e.content, "score": e.score, "metadata": e.metadata}
                for e in evidence
            ]
            guard_result = await self._guard.verify(
                response=answer,
                sources=source_dicts,
                domain=domain,
            )
            answer = guard_result.response
            quality_score = guard_result.quality_score
            quality_breakdown = guard_result.score_breakdown
        else:
            quality_score = 0.8
            quality_breakdown = {}

        # ── Step 4: Citation linking ──────────────────────────────────────────
        citations = self._citation_linker.build_citations(evidence)
        answer_with_citations = self._citation_linker.append_footnotes(answer, citations)

        duration_ms = round((time.monotonic() - start) * 1000, 2)

        # ── Cache store ───────────────────────────────────────────────────────
        if self._cache and guard_result and guard_result.passed:
            # Derive entity tags from the evidence so ADR-0014 selective
            # invalidation (ADR-0011 Step 7) can match this entry when the
            # underlying knowledge changes. Graph-sourced evidence carries the
            # entity name as its id; document_ids let doc-level updates match too.
            derived_tags = self._derive_entity_tags(evidence)
            await self._cache.set(
                query=query,
                tenant_id=tenant_id,
                answer=answer_with_citations,
                sources=[{"id": e.chunk_id, "content": e.content} for e in evidence],
                strategy=engine_strategy,
                entity_tags=(entity_tags or []) + derived_tags,
            )

        return SynthesisResult(
            answer=answer_with_citations,
            citations=citations,
            quality_score=quality_score,
            quality_breakdown=quality_breakdown,
            guard_result=guard_result,
            evidence_count=len(evidence),
            model_used=model_used,
            duration_ms=duration_ms,
            strategy=engine_strategy,
        )
