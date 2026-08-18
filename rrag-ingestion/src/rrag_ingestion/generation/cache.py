"""ADR-0014: Multi-Level Caching Strategy (L1–L4).

Lookup order:
  L1 — Edge cache (Traefik/Nginx, handled at infrastructure layer — not implemented here)
  L2 — Exact query cache (Redis, SHA256(normalized_query + tenant_id), TTL 1h)
  L3 — Semantic cache (Redis + cosine similarity on stored embeddings, threshold 0.95, TTL 30m)
  L4 — LLM prefix cache (vLLM PagedAttention, provider-managed — not implemented here)

This module implements L2 and L3. L1 and L4 are infrastructure-layer concerns.

Cache invalidation (ADR-0011 Step 7):
  Selectively invalidate L2/L3 entries whose entity tags overlap with the
  updated entity set. Entries for unrelated queries remain valid.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

_L2_PREFIX = "rrag:qcache:l2:"
_L3_PREFIX = "rrag:qcache:l3:"
_L3_EMB_PREFIX = "rrag:qcache:l3emb:"
_L3_META_PREFIX = "rrag:qcache:l3meta:"
_L3_INDEX_KEY = "rrag:qcache:l3:index"   # set of L3 entry keys for invalidation scan

_L2_TTL = 3600       # 1 hour
_L3_TTL = 1800       # 30 minutes
_L3_SIMILARITY_THRESHOLD = 0.95


@dataclass
class CacheEntry:
    answer: str
    sources: list[dict] = field(default_factory=list)
    strategy: str = "cached"
    entity_tags: list[str] = field(default_factory=list)  # for selective invalidation
    cached_at: float = field(default_factory=time.time)
    cache_level: str = "l2"


def _normalize_query(query: str) -> str:
    return " ".join(query.lower().split())


def _l2_key(query: str, tenant_id: str) -> str:
    h = hashlib.sha256(f"{_normalize_query(query)}|{tenant_id}".encode()).hexdigest()
    return f"{_L2_PREFIX}{h}"


def _cosine_sim(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


class QueryCache:
    """L2 (exact) + L3 (semantic) query cache backed by Redis (ADR-0014).

    L2 uses SHA256 of normalized query + tenant_id for exact-match lookup.
    L3 uses stored query embeddings with cosine similarity ≥ 0.95.
    Both levels record entity_tags for selective invalidation by ADR-0011 Step 7.
    """

    def __init__(self, redis: Any, embedding_model: str = "text-embedding-3-small") -> None:
        self._redis = redis
        self.embedding_model = embedding_model

    # ── Embedding ─────────────────────────────────────────────────────────────

    async def _embed(self, text: str) -> list[float]:
        from rrag_ingestion.services import llm_service
        results = await llm_service.embedding([text], model=self.embedding_model)
        return results[0]

    # ── L2 Exact Cache ────────────────────────────────────────────────────────

    def _l2_get(self, query: str, tenant_id: str) -> CacheEntry | None:
        key = _l2_key(query, tenant_id)
        try:
            raw = self._redis.get(key)
            if raw:
                data = json.loads(raw)
                return CacheEntry(**data)
        except Exception as e:
            logger.debug("L2 cache get error: %s", e)
        return None

    def _l2_set(self, query: str, tenant_id: str, entry: CacheEntry) -> None:
        key = _l2_key(query, tenant_id)
        try:
            self._redis.setex(key, _L2_TTL, json.dumps(entry.__dict__))
        except Exception as e:
            logger.debug("L2 cache set error: %s", e)

    # ── L3 Semantic Cache ─────────────────────────────────────────────────────

    async def _l3_get(self, query_embedding: list[float]) -> CacheEntry | None:
        """Find a semantically similar cached response (similarity ≥ 0.95)."""
        try:
            # Retrieve all L3 entry keys from the index set
            raw_keys = self._redis.smembers(_L3_INDEX_KEY)
            if not raw_keys:
                return None

            best_sim = 0.0
            best_entry: CacheEntry | None = None

            for raw_key in raw_keys:
                key = raw_key.decode() if isinstance(raw_key, bytes) else raw_key
                emb_raw = self._redis.get(f"{_L3_EMB_PREFIX}{key}")
                if not emb_raw:
                    continue
                stored_emb: list[float] = json.loads(emb_raw)
                sim = _cosine_sim(query_embedding, stored_emb)
                if sim >= _L3_SIMILARITY_THRESHOLD and sim > best_sim:
                    meta_raw = self._redis.get(f"{_L3_META_PREFIX}{key}")
                    if meta_raw:
                        data = json.loads(meta_raw)
                        data["cache_level"] = "l3"
                        entry = CacheEntry(**data)
                        best_sim = sim
                        best_entry = entry

            return best_entry
        except Exception as e:
            logger.debug("L3 cache lookup error: %s", e)
            return None

    async def _l3_set(
        self, query: str, query_embedding: list[float], entry: CacheEntry
    ) -> None:
        try:
            key = hashlib.sha256(query.encode()).hexdigest()
            pipe = self._redis.pipeline()
            pipe.setex(f"{_L3_EMB_PREFIX}{key}", _L3_TTL, json.dumps(query_embedding))
            pipe.setex(f"{_L3_META_PREFIX}{key}", _L3_TTL, json.dumps(entry.__dict__))
            pipe.sadd(_L3_INDEX_KEY, key)
            pipe.execute()
        except Exception as e:
            logger.debug("L3 cache set error: %s", e)

    # ── Public API ────────────────────────────────────────────────────────────

    async def get(self, query: str, tenant_id: str) -> CacheEntry | None:
        """Check L2 then L3. Returns None on full cache miss."""
        # L2: exact match
        entry = self._l2_get(query, tenant_id)
        if entry:
            logger.debug("Cache L2 hit for query: %.60s", query)
            return entry

        # L3: semantic match (needs an embedding)
        try:
            embedding = await self._embed(query)
            entry = await self._l3_get(embedding)
            if entry:
                logger.debug("Cache L3 hit (semantic) for query: %.60s", query)
                return entry
        except Exception as e:
            logger.debug("L3 lookup skipped: %s", e)

        return None

    async def set(
        self,
        query: str,
        tenant_id: str,
        answer: str,
        sources: list[dict],
        strategy: str,
        entity_tags: list[str] | None = None,
    ) -> None:
        """Store a result in both L2 and L3."""
        entry = CacheEntry(
            answer=answer,
            sources=sources,
            strategy=strategy,
            entity_tags=entity_tags or [],
        )
        # L2 always
        self._l2_set(query, tenant_id, entry)

        # L3: embed and store
        try:
            embedding = await self._embed(query)
            await self._l3_set(query, embedding, entry)
        except Exception as e:
            logger.debug("L3 cache store skipped: %s", e)

    # ── Selective Invalidation (ADR-0011 Step 7) ──────────────────────────────

    def invalidate_by_entities(self, entity_names: list[str]) -> int:
        """Invalidate L2 and L3 cache entries whose entity_tags overlap with updated entities.

        Only entries related to the changed entities are evicted; unrelated
        entries remain valid (selective invalidation as specified in ADR-0014).
        Returns the count of invalidated entries.
        """
        if not entity_names:
            return 0

        entity_set = {e.lower() for e in entity_names}
        invalidated = 0

        try:
            # Scan L2 keys
            l2_keys = list(self._redis.scan_iter(f"{_L2_PREFIX}*"))
            for key in l2_keys:
                raw = self._redis.get(key)
                if not raw:
                    continue
                data = json.loads(raw)
                tags = {t.lower() for t in data.get("entity_tags", [])}
                if tags & entity_set:
                    self._redis.delete(key)
                    invalidated += 1

            # Scan L3 meta keys
            l3_meta_keys = list(self._redis.scan_iter(f"{_L3_META_PREFIX}*"))
            for key in l3_meta_keys:
                raw = self._redis.get(key)
                if not raw:
                    continue
                data = json.loads(raw)
                tags = {t.lower() for t in data.get("entity_tags", [])}
                if tags & entity_set:
                    short_key = key.replace(
                        (_L3_META_PREFIX).encode() if isinstance(key, bytes) else _L3_META_PREFIX, ""
                    )
                    if isinstance(short_key, bytes):
                        short_key = short_key.decode()
                    pipe = self._redis.pipeline()
                    pipe.delete(key)
                    pipe.delete(f"{_L3_EMB_PREFIX}{short_key}")
                    pipe.srem(_L3_INDEX_KEY, short_key)
                    pipe.execute()
                    invalidated += 1

        except Exception as e:
            logger.warning("Cache invalidation error: %s", e)

        logger.info("Invalidated %d cache entries for entities: %s", invalidated, entity_names[:5])
        return invalidated
