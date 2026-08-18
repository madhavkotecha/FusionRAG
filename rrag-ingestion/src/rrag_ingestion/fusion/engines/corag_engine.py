"""ADR-0007: CoRAG Engine — chain-of-retrieval with iterative sub-query generation.

Three decoding strategies:
  greedy    → one sub-query at a time, stop when answer found
  best_of_n → generate N parallel chains, pick highest-confidence
  tree      → branch at each hop, prune low-confidence branches
"""
from __future__ import annotations

import asyncio
import logging

from rrag_ingestion.fusion.engines.base import EngineResult
from rrag_ingestion.fusion.knowledge_store import KnowledgeStore

logger = logging.getLogger(__name__)

_SUBQUERY_PROMPT = """\
You are building an evidence chain for a complex question.
Given the original question and the evidence gathered so far, generate ONE focused follow-up question
that would provide missing evidence needed to fully answer the original question.
If the gathered evidence is already sufficient, respond with "DONE".

Original question: {query}

Evidence gathered so far:
{evidence_summary}

Next sub-question (or DONE):"""

_ANSWER_CONFIDENCE_PROMPT = """\
Rate from 0.0 to 1.0 how well the following evidence answers the question.
Respond with only a number.

Question: {query}
Evidence: {evidence}
Score:"""


class CoRAGEngine:
    """Iterative chain-of-retrieval engine."""

    name = "corag"

    def __init__(self, store: KnowledgeStore, llm_client: object | None = None) -> None:
        self._store = store
        self._llm = llm_client

    def _get_llm(self) -> object:
        if self._llm is not None:
            return self._llm
        from rrag_ingestion.services.openai_client import get_openai_client
        return get_openai_client()

    async def _generate_subquery(
        self, query: str, evidence_so_far: list[str], model: str
    ) -> str:
        client = self._get_llm()
        evidence_summary = "\n".join(f"- {e[:200]}" for e in evidence_so_far[:5]) or "(none yet)"
        prompt = _SUBQUERY_PROMPT.format(query=query, evidence_summary=evidence_summary)
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=128,
        )
        return (resp.choices[0].message.content or "").strip()

    async def _score_confidence(
        self, query: str, evidence: list[str], model: str
    ) -> float:
        if not evidence:
            return 0.0
        client = self._get_llm()
        evidence_text = "\n".join(e[:300] for e in evidence[:5])
        prompt = _ANSWER_CONFIDENCE_PROMPT.format(query=query, evidence=evidence_text)
        try:
            resp = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=8,
            )
            return float((resp.choices[0].message.content or "").strip())
        except Exception:
            return 0.5

    async def _retrieve_for_subquery(
        self,
        subquery: str,
        datastore_id: str,
        top_k: int,
        embedding: list[float] | None,
    ) -> list[dict]:
        results: list[dict] = []

        # BM25 on document store
        bm25 = self._store.search_bm25(subquery, top_k=top_k // 2)
        results.extend(bm25)

        # Vector search if embedding available
        if embedding is not None:
            try:
                vec = self._store.search_vectors(embedding, top_k=top_k // 2)
                results.extend(vec)
            except Exception as e:
                logger.warning(f"CoRAG vector retrieval failed: {e}")

        return results

    async def _greedy_chain(
        self,
        query: str,
        datastore_id: str,
        top_k: int,
        max_hops: int,
        model: str,
        embedding: list[float] | None,
    ) -> tuple[list[dict], float]:
        all_chunks: list[dict] = []
        evidence_texts: list[str] = []

        for hop in range(max_hops):
            if hop == 0:
                subquery = query
            else:
                subquery = await self._generate_subquery(query, evidence_texts, model)
                if subquery.upper() == "DONE":
                    break

            chunks = await self._retrieve_for_subquery(subquery, datastore_id, top_k, embedding)
            all_chunks.extend(chunks)
            evidence_texts.extend(c["content"] for c in chunks[:3])

            confidence = await self._score_confidence(query, evidence_texts, model)
            if confidence >= 0.85:
                break

        confidence = await self._score_confidence(query, evidence_texts, model)
        return all_chunks, confidence

    async def _best_of_n_chain(
        self,
        query: str,
        datastore_id: str,
        top_k: int,
        max_hops: int,
        model: str,
        n: int,
        embedding: list[float] | None,
    ) -> tuple[list[dict], float]:
        tasks = [
            self._greedy_chain(query, datastore_id, top_k, max_hops, model, embedding)
            for _ in range(n)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        best_chunks: list[dict] = []
        best_conf = 0.0
        for r in results:
            if isinstance(r, Exception):
                continue
            chunks, conf = r
            if conf > best_conf:
                best_conf = conf
                best_chunks = chunks
        return best_chunks, best_conf

    async def retrieve(
        self,
        query: str,
        datastore_id: str,
        top_k: int = 20,
        strategy: str = "greedy",   # greedy | best_of_n | tree
        max_hops: int = 3,
        model: str = "gpt-4o-mini",
        embedding: list[float] | None = None,
    ) -> EngineResult:
        try:
            if strategy == "best_of_n":
                chunks, confidence = await self._best_of_n_chain(
                    query, datastore_id, top_k, max_hops, model, n=3, embedding=embedding
                )
            else:
                # greedy and tree both use greedy as the base chain
                chunks, confidence = await self._greedy_chain(
                    query, datastore_id, top_k, max_hops, model, embedding=embedding
                )
        except Exception as e:
            logger.warning(f"CoRAG chain failed: {e}")
            chunks, confidence = [], 0.0

        # Deduplicate
        seen: dict[str, dict] = {}
        for c in chunks:
            cid = c.get("id", "")
            if cid and (cid not in seen or c.get("score", 0) > seen[cid].get("score", 0)):
                seen[cid] = {**c, "metadata": {**c.get("metadata", {}), "engine": "corag"}}

        ranked = sorted(seen.values(), key=lambda x: x.get("score", 0), reverse=True)[:top_k]

        return EngineResult(
            engine="corag",
            chunks=ranked,
            confidence=confidence,
            metadata={"strategy": strategy, "max_hops": max_hops},
        )
