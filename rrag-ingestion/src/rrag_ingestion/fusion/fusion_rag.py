"""ADR-0007: FusionRAG — unified orchestrator for three-engine retrieval.

Dispatches to engines based on routing decision (ADR-0008),
runs selected engines (in parallel for full_parallel strategy),
merges results using Reciprocal Rank Fusion, and escalates
if quality is below threshold.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from rrag_ingestion.fusion.engines.base import EngineResult
from rrag_ingestion.fusion.engines.corag_engine import CoRAGEngine
from rrag_ingestion.fusion.engines.kag_engine import KAGEngine
from rrag_ingestion.fusion.engines.lightrag_engine import LightRAGEngine
from rrag_ingestion.fusion.knowledge_store import KnowledgeStore
from rrag_ingestion.fusion.router import QueryRouter, RoutingDecision

logger = logging.getLogger(__name__)

_MIN_QUALITY_THRESHOLD = 0.3
_RRF_K = 60


@dataclass
class FusionResult:
    chunks: list[dict] = field(default_factory=list)
    engine_results: list[EngineResult] = field(default_factory=list)
    routing: RoutingDecision | None = None
    strategy: str = ""
    escalations: int = 0


class FusionRAG:
    """Three-engine fusion RAG orchestrator (ADR-0007)."""

    def __init__(
        self,
        store: KnowledgeStore,
        router: QueryRouter | None = None,
        llm_client: object | None = None,
        model: str = "gpt-4o-mini",
    ) -> None:
        self._store = store
        self._router = router or QueryRouter(llm_client=llm_client, model=model)
        self._lightrag = LightRAGEngine(store)
        self._corag = CoRAGEngine(store, llm_client=llm_client)
        self._kag = KAGEngine(store, llm_client=llm_client)
        self._model = model

    async def _get_embedding(self, query: str) -> list[float] | None:
        try:
            from rrag_ingestion.services import llm_service
            embeddings = await llm_service.embedding(query)
            return embeddings[0] if embeddings else None
        except Exception as e:
            logger.debug(f"Embedding failed: {e}")
            return None

    async def _run_engine(
        self,
        engine_name: str,
        query: str,
        datastore_id: str,
        top_k: int,
        decision: RoutingDecision,
        embedding: list[float] | None,
    ) -> EngineResult:
        try:
            if engine_name == "lightrag":
                return await self._lightrag.retrieve(
                    query, datastore_id, top_k,
                    mode=decision.lightrag_mode,
                    embedding=embedding,
                )
            elif engine_name == "corag":
                return await self._corag.retrieve(
                    query, datastore_id, top_k,
                    strategy=decision.corag_strategy,
                    model=self._model,
                    embedding=embedding,
                )
            elif engine_name == "kag":
                return await self._kag.retrieve(
                    query, datastore_id, top_k,
                    model=self._model,
                    embedding=embedding,
                )
        except Exception as e:
            logger.warning(f"Engine {engine_name} failed: {e}")
        return EngineResult(engine=engine_name, chunks=[], confidence=0.0)

    @staticmethod
    def _rrf_merge(engine_results: list[EngineResult], top_k: int) -> list[dict]:
        """Reciprocal Rank Fusion across engine result lists."""
        scores: dict[str, float] = {}
        chunk_map: dict[str, dict] = {}

        for result in engine_results:
            for rank, chunk in enumerate(result.chunks):
                cid = chunk.get("id", "")
                if not cid:
                    continue
                scores[cid] = scores.get(cid, 0.0) + 1.0 / (_RRF_K + rank + 1)
                if cid not in chunk_map:
                    chunk_map[cid] = chunk

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        merged = []
        for doc_id, fused_score in ranked[:top_k]:
            chunk = dict(chunk_map[doc_id])
            chunk["score"] = fused_score
            chunk["metadata"] = {**chunk.get("metadata", {}), "fusion_score": fused_score}
            merged.append(chunk)
        return merged

    def _quality_score(self, engine_results: list[EngineResult]) -> float:
        """Aggregate quality from engine confidences and chunk counts."""
        if not engine_results:
            return 0.0
        total_chunks = sum(len(r.chunks) for r in engine_results)
        avg_conf = sum(r.confidence for r in engine_results) / len(engine_results)
        chunk_signal = min(total_chunks / 10, 1.0)
        return 0.5 * avg_conf + 0.5 * chunk_signal

    async def retrieve(
        self,
        query: str,
        datastore_id: str = "",
        top_k: int = 20,
    ) -> FusionResult:
        decision = await self._router.route(query)
        embedding = await self._get_embedding(query)

        escalations = 0
        engine_results: list[EngineResult] = []

        while True:
            # Run selected engines (parallel for full_parallel, sequential otherwise)
            if decision.strategy.startswith("full_parallel") or len(decision.engines) > 1:
                tasks = [
                    self._run_engine(name, query, datastore_id, top_k, decision, embedding)
                    for name in decision.engines
                ]
                engine_results = list(await asyncio.gather(*tasks))
            else:
                engine_results = [
                    await self._run_engine(
                        decision.engines[0], query, datastore_id, top_k, decision, embedding
                    )
                ]

            quality = self._quality_score(engine_results)

            if quality >= _MIN_QUALITY_THRESHOLD:
                break

            next_decision = self._router.escalate(decision)
            if next_decision is None:
                logger.info(f"FusionRAG: max escalations reached for query (quality={quality:.2f})")
                break

            escalations += 1
            decision = next_decision
            logger.info(
                f"FusionRAG: escalating to {decision.strategy} (quality={quality:.2f}, level={escalations})"
            )

        merged = self._rrf_merge(engine_results, top_k)

        return FusionResult(
            chunks=merged,
            engine_results=engine_results,
            routing=decision,
            strategy=decision.strategy,
            escalations=escalations,
        )
