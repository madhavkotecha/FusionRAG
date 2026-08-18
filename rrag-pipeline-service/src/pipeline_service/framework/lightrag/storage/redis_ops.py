"""Workspace-scoped Redis operations for KV storage.

Redis is used for:
* Storing raw text chunks keyed by ``{scope}:chunk:{doc_id}:{index}``
* Mapping entities to the chunks that mention them
* Caching LLM responses to avoid repeated calls

All keys are prefixed with the *scope* string for workspace isolation.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import redis.asyncio as redis

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Client singleton
# ---------------------------------------------------------------------------

_client: redis.Redis | None = None


async def get_redis_client() -> redis.Redis:
    """Return (and lazily create) a shared async Redis client."""
    global _client
    if _client is None:
        url = os.getenv("REDIS_URL", "redis://redis:6379/0")
        _client = redis.from_url(url, decode_responses=True)
    return _client


async def close_redis_client() -> None:
    """Close the shared Redis client."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


# ---------------------------------------------------------------------------
# Key helpers
# ---------------------------------------------------------------------------

def _chunk_key(scope: str, doc_id: str, index: int) -> str:
    return f"{scope}:chunk:{doc_id}:{index}"


def _entity_map_key(scope: str, entity_id: str) -> str:
    return f"{scope}:entity_chunks:{entity_id}"


def _entity_key(scope: str, entity_id: str) -> str:
    return f"{scope}:entity:{entity_id}"


def _llm_cache_key(scope: str, key: str) -> str:
    return f"{scope}:llm_cache:{key}"


# ---------------------------------------------------------------------------
# Chunk storage
# ---------------------------------------------------------------------------

async def redis_store_chunks(scope: str, chunks: list[dict[str, Any]]) -> int:
    """Store text chunks as individual hash entries in Redis.

    Each chunk dict must contain ``full_doc_id``, ``chunk_order_index``, and
    ``content`` at minimum.  Additional fields (``tokens``, etc.) are also
    stored.

    Returns the number of chunks written.
    """
    if not chunks:
        return 0

    client = await get_redis_client()
    pipe = client.pipeline(transaction=False)

    for chunk in chunks:
        doc_id = chunk.get("full_doc_id", "unknown")
        idx = chunk.get("chunk_order_index", 0)
        key = _chunk_key(scope, doc_id, idx)
        pipe.hset(key, mapping={
            "content": chunk.get("content", ""),
            "full_doc_id": doc_id,
            "chunk_order_index": str(idx),
            "tokens": str(chunk.get("tokens", 0)),
        })

    await pipe.execute()
    return len(chunks)


# ---------------------------------------------------------------------------
# Entity <-> chunk mappings
# ---------------------------------------------------------------------------

async def redis_store_entity_mappings(
    scope: str,
    entities: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
) -> int:
    """Map each entity to the chunk keys it was extracted from.

    The mapping is a Redis Set per entity.  Entities are matched to chunks via
    a naive substring check of ``entity_name`` inside chunk ``content``.

    Returns the number of mapping entries created.
    """
    if not entities or not chunks:
        return 0

    client = await get_redis_client()
    pipe = client.pipeline(transaction=False)
    count = 0

    for entity in entities:
        eid = entity.get("entity_id") or entity.get("entity_name", "")
        ename = entity.get("entity_name", eid).lower()
        if not eid:
            continue

        map_key = _entity_map_key(scope, eid)
        # Also store the entity itself
        ent_key = _entity_key(scope, eid)
        pipe.set(ent_key, json.dumps(entity, default=str))

        for chunk in chunks:
            if ename in chunk.get("content", "").lower():
                doc_id = chunk.get("full_doc_id", "unknown")
                idx = chunk.get("chunk_order_index", 0)
                chunk_key = _chunk_key(scope, doc_id, idx)
                pipe.sadd(map_key, chunk_key)
                count += 1

    await pipe.execute()
    return count


# ---------------------------------------------------------------------------
# Retrieval helpers
# ---------------------------------------------------------------------------

async def redis_get_related_chunks(
    scope: str,
    entities: list[dict[str, Any]],
    relations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Retrieve chunks that are related to the given entities and relations.

    This looks up the entity-to-chunk mapping sets, unions the chunk keys, then
    fetches and returns the full chunk data.
    """
    client = await get_redis_client()
    chunk_keys: set[str] = set()

    # Collect chunk keys from entities
    for entity in entities:
        eid = entity.get("entity_id") or entity.get("entity_name", "")
        if eid:
            members = await client.smembers(_entity_map_key(scope, eid))
            chunk_keys.update(members)

    # Collect chunk keys from relations (both source and target)
    for rel in relations:
        for field in ("source_entity", "target_entity"):
            eid = rel.get(field, "")
            if eid:
                members = await client.smembers(_entity_map_key(scope, eid))
                chunk_keys.update(members)

    if not chunk_keys:
        return []

    # Fetch all chunk hashes
    pipe = client.pipeline(transaction=False)
    for key in chunk_keys:
        pipe.hgetall(key)
    results = await pipe.execute()

    chunks: list[dict[str, Any]] = []
    for data in results:
        if data:
            data["chunk_order_index"] = int(data.get("chunk_order_index", 0))
            data["tokens"] = int(data.get("tokens", 0))
            chunks.append(data)

    return chunks


async def redis_get_entity(scope: str, entity_id: str) -> dict[str, Any] | None:
    """Retrieve a single entity dict from Redis, or *None* if not found."""
    client = await get_redis_client()
    raw = await client.get(_entity_key(scope, entity_id))
    if raw:
        return json.loads(raw)
    return None


# ---------------------------------------------------------------------------
# LLM response cache
# ---------------------------------------------------------------------------

async def redis_cache_llm_response(
    scope: str, key: str, value: str
) -> None:
    """Cache an LLM response string under a scoped key.

    The TTL is controlled by the ``REDIS_LLM_CACHE_TTL`` env var (default:
    86400 seconds = 24 h).
    """
    client = await get_redis_client()
    ttl = int(os.getenv("REDIS_LLM_CACHE_TTL", "86400"))
    cache_key = _llm_cache_key(scope, key)
    await client.set(cache_key, value, ex=ttl)


async def redis_get_cached_llm_response(
    scope: str, key: str
) -> str | None:
    """Retrieve a cached LLM response, or *None* if not found / expired."""
    client = await get_redis_client()
    return await client.get(_llm_cache_key(scope, key))
