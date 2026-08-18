"""ADR-0015: Hallucination Guard with Claim Verification.

Five-step pipeline:
  1. Claim Extraction  — parse response into discrete factual claims via LLM
  2. Evidence Matching — match each claim against retrieved evidence by similarity
  3. Classification    — label: Supported | PartiallySupported | Unsupported
  4. Iterative Revision — re-generate unsupported claims; max 2 iterations
  5. Quality Score     — weighted composite score across 5 dimensions

Quality score dimensions:
  evidence_coverage     30%  — % of claims supported by evidence
  citation_completeness 20%  — % of claims with source citations
  source_diversity      15%  — distinct source document count (normalized)
  reasoning_coherence   20%  — LLM-judged logical flow (0–1)
  confidence_score      15%  — average evidence confidence

Domain thresholds: default 0.70, healthcare/legal/finance 0.85.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

_EXTRACT_CLAIMS_PROMPT = """\
Extract all discrete factual claims from the following response.
Output ONE claim per line. Each claim must be a standalone, verifiable statement.
Do NOT output numbering, bullet points, or explanations.

Response:
{response}

Claims:"""

_CLASSIFY_CLAIM_PROMPT = """\
You are a fact-checker. Given a claim and retrieved evidence passages, classify the claim.

Claim: {claim}

Evidence:
{evidence}

Respond with exactly one word: Supported, PartiallySupported, or Unsupported.
Classification:"""

_COHERENCE_PROMPT = """\
Rate the logical coherence of this response on a scale of 0.0 to 1.0.
Consider: logical flow, consistent reasoning, no contradictions.
Respond with a single float between 0.0 and 1.0 only.

Response:
{response}

Score:"""

_REVISION_PROMPT = """\
Revise the following response to ONLY include claims that are directly supported
by the provided evidence. Remove or soften any unsupported claims.

Original response:
{response}

Evidence:
{evidence}

Unsupported claims to remove or soften:
{unsupported}

Revised response:"""

_DOMAIN_THRESHOLDS: dict[str, float] = {
    "healthcare": 0.85,
    "legal": 0.85,
    "finance": 0.85,
    "medical": 0.85,
    "default": 0.70,
}


@dataclass
class ClaimVerification:
    claim: str
    status: str              # Supported | PartiallySupported | Unsupported
    evidence_snippets: list[str] = field(default_factory=list)
    source_ids: list[str] = field(default_factory=list)


@dataclass
class GuardResult:
    response: str
    quality_score: float
    claims: list[ClaimVerification] = field(default_factory=list)
    iterations: int = 0
    passed: bool = True
    score_breakdown: dict = field(default_factory=dict)


def _cosine_sim(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


class HallucinationGuard:
    """Claim-level hallucination verification with iterative revision (ADR-0015).

    Connects to the LLM service for claim extraction, classification, and
    coherence scoring. Evidence matching uses embedding cosine similarity so no
    extra index is required — the retrieved sources are used directly.
    """

    def __init__(
        self,
        model_fast: str | None = None,
        model_capable: str | None = None,
        max_iterations: int = 2,
        embedding_model: str = "text-embedding-3-small",
    ) -> None:
        from rrag_ingestion.config import settings
        self._model_fast = model_fast or settings.llm_model_fast
        self._model_capable = model_capable or settings.llm_model_capable
        self._max_iterations = max_iterations
        self._embedding_model = embedding_model

    # ── LLM helpers ───────────────────────────────────────────────────────────

    async def _llm(self, prompt: str, tier: str = "fast", max_tokens: int = 512) -> str:
        from rrag_ingestion.services import llm_service
        resp = await llm_service.completion(
            messages=[{"role": "user", "content": prompt}],
            tier=tier,
            temperature=0.0,
            max_tokens=max_tokens,
        )
        return (resp.choices[0].message.content or "").strip()

    async def _embed(self, texts: list[str]) -> list[list[float]]:
        from rrag_ingestion.services import llm_service
        return await llm_service.embedding(texts, model=self._embedding_model)

    # ── Step 1: Claim Extraction ───────────────────────────────────────────────

    async def _extract_claims(self, response: str) -> list[str]:
        raw = await self._llm(
            _EXTRACT_CLAIMS_PROMPT.format(response=response),
            tier="fast",
            max_tokens=1024,
        )
        claims = [line.strip() for line in raw.splitlines() if line.strip()]
        return claims[:40]  # cap to avoid runaway cost

    # ── Step 2: Evidence Matching ──────────────────────────────────────────────

    async def _match_evidence(
        self,
        claim: str,
        sources: list[dict],
        top_k: int = 3,
    ) -> tuple[list[str], list[str]]:
        """Return (evidence_snippets, source_ids) for a claim via embedding similarity."""
        if not sources:
            return [], []

        contents = [s.get("content", "") for s in sources]
        texts_to_embed = [claim] + contents

        try:
            embeddings = await self._embed(texts_to_embed)
        except Exception as e:
            logger.debug("Embedding for evidence matching failed: %s", e)
            return [], []

        claim_emb = embeddings[0]
        scored = [
            (_cosine_sim(claim_emb, embeddings[i + 1]), contents[i], sources[i].get("id", ""))
            for i in range(len(contents))
        ]
        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:top_k]
        return [t[1] for t in top], [t[2] for t in top]

    # ── Step 3: Classification ─────────────────────────────────────────────────

    async def _classify_claim(self, claim: str, evidence_snippets: list[str]) -> str:
        if not evidence_snippets:
            return "Unsupported"

        evidence_block = "\n---\n".join(evidence_snippets[:3])
        raw = await self._llm(
            _CLASSIFY_CLAIM_PROMPT.format(claim=claim, evidence=evidence_block),
            tier="fast",
            max_tokens=8,
        )
        word = raw.split()[0].rstrip(".,") if raw else "Unsupported"
        if word in ("Supported", "PartiallySupported", "Unsupported"):
            return word
        return "Unsupported"

    # ── Step 4: Iterative Revision ─────────────────────────────────────────────

    async def _revise_response(
        self,
        response: str,
        sources: list[dict],
        unsupported_claims: list[str],
    ) -> str:
        evidence_block = "\n---\n".join(
            s.get("content", "") for s in sources[:8]
        )
        unsupported_block = "\n".join(f"- {c}" for c in unsupported_claims[:10])
        revised = await self._llm(
            _REVISION_PROMPT.format(
                response=response,
                evidence=evidence_block,
                unsupported=unsupported_block,
            ),
            tier="capable",
            max_tokens=2048,
        )
        return revised or response

    # ── Step 5: Quality Score ──────────────────────────────────────────────────

    async def _compute_quality(
        self,
        response: str,
        verifications: list[ClaimVerification],
        sources: list[dict],
    ) -> tuple[float, dict]:
        n = len(verifications) or 1

        supported = sum(1 for v in verifications if v.status == "Supported")
        partial = sum(1 for v in verifications if v.status == "PartiallySupported")
        evidence_coverage = (supported + 0.5 * partial) / n

        cited = sum(1 for v in verifications if v.source_ids)
        citation_completeness = cited / n

        distinct_docs = len(
            {s.get("metadata", {}).get("document_id", s.get("id", "")) for s in sources}
        )
        source_diversity = min(1.0, distinct_docs / 5.0)

        try:
            raw = await self._llm(
                _COHERENCE_PROMPT.format(response=response[:3000]),
                tier="fast",
                max_tokens=8,
            )
            reasoning_coherence = float(raw.split()[0]) if raw else 0.5
            reasoning_coherence = max(0.0, min(1.0, reasoning_coherence))
        except Exception:
            reasoning_coherence = 0.5

        # Average confidence of the evidence that actually supports claims, derived
        # from real retrieval scores (clamped to [0,1]). Falls back to the full
        # evidence set, then to a neutral 0.5 when no scores are present.
        supporting_ids = {
            sid for v in verifications
            if v.status in ("Supported", "PartiallySupported")
            for sid in v.source_ids
        }
        supporting_scores = [
            max(0.0, min(1.0, float(s.get("score", 0.0))))
            for s in sources
            if s.get("id") in supporting_ids and isinstance(s.get("score"), (int, float))
        ]
        if not supporting_scores:
            supporting_scores = [
                max(0.0, min(1.0, float(s.get("score", 0.0))))
                for s in sources
                if isinstance(s.get("score"), (int, float))
            ]
        avg_confidence = (
            sum(supporting_scores) / len(supporting_scores) if supporting_scores else 0.5
        )

        score = (
            0.30 * evidence_coverage
            + 0.20 * citation_completeness
            + 0.15 * source_diversity
            + 0.20 * reasoning_coherence
            + 0.15 * avg_confidence
        )

        breakdown = {
            "evidence_coverage": round(evidence_coverage, 3),
            "citation_completeness": round(citation_completeness, 3),
            "source_diversity": round(source_diversity, 3),
            "reasoning_coherence": round(reasoning_coherence, 3),
            "confidence_score": round(avg_confidence, 3),
            "total": round(score, 3),
        }
        return score, breakdown

    # ── Main entry point ───────────────────────────────────────────────────────

    async def verify(
        self,
        response: str,
        sources: list[dict],
        domain: str = "default",
    ) -> GuardResult:
        """Run the full 5-step hallucination guard pipeline.

        Returns a GuardResult with the (possibly revised) response, quality
        score, per-claim verifications, and pass/fail decision.
        """
        threshold = _DOMAIN_THRESHOLDS.get(domain.lower(), _DOMAIN_THRESHOLDS["default"])
        current_response = response
        iterations = 0

        for iteration in range(self._max_iterations + 1):
            # Step 1: extract claims
            claims = await self._extract_claims(current_response)
            if not claims:
                break

            # Steps 2 + 3: match and classify in parallel
            async def _verify_one(claim: str) -> ClaimVerification:
                snippets, src_ids = await self._match_evidence(claim, sources)
                status = await self._classify_claim(claim, snippets)
                return ClaimVerification(
                    claim=claim,
                    status=status,
                    evidence_snippets=snippets,
                    source_ids=src_ids,
                )

            verifications = list(await asyncio.gather(*[_verify_one(c) for c in claims]))
            unsupported = [v.claim for v in verifications if v.status == "Unsupported"]

            # Step 5: quality score
            quality_score, breakdown = await self._compute_quality(
                current_response, verifications, sources
            )

            if not unsupported or quality_score >= threshold:
                return GuardResult(
                    response=current_response,
                    quality_score=quality_score,
                    claims=verifications,
                    iterations=iterations,
                    passed=quality_score >= threshold,
                    score_breakdown=breakdown,
                )

            # Step 4: revise if we haven't exhausted iterations
            if iteration < self._max_iterations:
                iterations += 1
                current_response = await self._revise_response(
                    current_response, sources, unsupported
                )
            else:
                # Max iterations reached — flag remaining unsupported claims
                for v in verifications:
                    if v.status == "Unsupported":
                        v.claim = f"[LOW CONFIDENCE] {v.claim}"
                return GuardResult(
                    response=current_response,
                    quality_score=quality_score,
                    claims=verifications,
                    iterations=iterations,
                    passed=quality_score >= threshold,
                    score_breakdown=breakdown,
                )

        # Fallback if no claims extracted
        return GuardResult(
            response=current_response,
            quality_score=1.0,
            claims=[],
            iterations=0,
            passed=True,
            score_breakdown={},
        )
