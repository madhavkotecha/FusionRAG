"""ADR-0007: LightRAG Engine — graph-enhanced dual-level retrieval.

Local mode:  entity-centric graph traversal (O(1) hop entity lookup)
Global mode: community/hub-based thematic retrieval (high-degree nodes)
Both modes backed by the shared KnowledgeStore (ADR-0009).
"""
from __future__ import annotations

import logging
import re

from rrag_ingestion.fusion.engines.base import EngineResult
from rrag_ingestion.fusion.knowledge_store import KnowledgeStore

logger = logging.getLogger(__name__)

_STOP_WORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "in", "on", "at", "to", "for", "of", "with",
    "by", "from", "as", "and", "but", "or", "not", "it", "its", "this",
    "that", "what", "which", "who", "how", "when", "where", "why",
    "i", "me", "we", "you", "he", "she", "they", "them",
})


def _extract_keywords(query: str) -> list[str]:
    words = re.findall(r"[a-zA-Z0-9]+", query.lower())
    return [w for w in words if w not in _STOP_WORDS and len(w) > 2]


def _entity_to_text(entity: dict) -> str:
    text = f"Entity: {entity['name']}"
    if entity.get("description"):
        text += f"\nDescription: {entity['description']}"
    for rel in entity.get("relations", [])[:8]:
        text += f"\n  - {rel['rel']}: {rel['target']}"
    return text


class LightRAGEngine:
    """Dual-level KG retrieval (local entity + global community)."""

    name = "lightrag"

    def __init__(self, store: KnowledgeStore) -> None:
        self._store = store

    async def retrieve(
        self,
        query: str,
        datastore_id: str,
        top_k: int = 20,
        mode: str = "hybrid",  # local | global | hybrid
        embedding: list[float] | None = None,
    ) -> EngineResult:
        chunks: list[dict] = []

        if mode in ("local", "hybrid"):
            keywords = _extract_keywords(query)
            entities = await self._store.search_entities_local(
                keywords, datastore_id=datastore_id, limit=top_k
            )
            for ent in entities:
                chunks.append({
                    "id": ent["name"],
                    "content": _entity_to_text(ent),
                    "score": 1.0,
                    "source": "lightrag_local",
                    "metadata": {"engine": "lightrag", "mode": "local"},
                })

        if mode in ("global", "hybrid"):
            hubs = await self._store.search_entities_global(
                datastore_id=datastore_id, limit=top_k // 2
            )
            for hub in hubs:
                chunks.append({
                    "id": hub["name"],
                    "content": _entity_to_text(hub),
                    "score": 0.8,
                    "source": "lightrag_global",
                    "metadata": {"engine": "lightrag", "mode": "global"},
                })

        # Augment with vector similarity if embedding provided
        if embedding is not None:
            try:
                vector_hits = self._store.search_vectors(embedding, top_k=top_k)
                for hit in vector_hits:
                    chunks.append({**hit, "metadata": {**hit.get("metadata", {}), "engine": "lightrag"}})
            except Exception as e:
                logger.warning(f"LightRAG vector augmentation failed: {e}")

        # Deduplicate by id, preserve highest score
        seen: dict[str, dict] = {}
        for c in chunks:
            cid = c["id"]
            if cid not in seen or c["score"] > seen[cid]["score"]:
                seen[cid] = c

        ranked = sorted(seen.values(), key=lambda x: x["score"], reverse=True)[:top_k]

        return EngineResult(
            engine="lightrag",
            chunks=ranked,
            confidence=min(1.0, len(ranked) / max(top_k, 1)),
            metadata={"mode": mode, "result_count": len(ranked)},
        )
