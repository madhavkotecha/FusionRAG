"""Workspace-scoped Qdrant operations for vector storage.

Each collection is named ``{scope}_{suffix}`` (e.g. ``ws_abc_entities``) so
that different workspaces are isolated.  The pattern follows the upstream
LightRAG ``QdrantVectorDBStorage`` but is expressed as stateless async helpers.
"""

from __future__ import annotations

import hashlib
import logging
import os
import uuid
from typing import Any

from qdrant_client import AsyncQdrantClient, models
from qdrant_client.models import Distance, VectorParams, PointStruct

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Client singleton
# ---------------------------------------------------------------------------

_client: AsyncQdrantClient | None = None


async def get_qdrant_client() -> AsyncQdrantClient:
    """Return (and lazily create) a shared async Qdrant client."""
    global _client
    if _client is None:
        url = os.getenv("QDRANT_URL", "http://qdrant:6333")
        api_key = os.getenv("QDRANT_API_KEY")
        _client = AsyncQdrantClient(url=url, api_key=api_key)
    return _client


async def close_qdrant_client() -> None:
    """Close the shared Qdrant client."""
    global _client
    if _client is not None:
        await _client.close()
        _client = None


# ---------------------------------------------------------------------------
# Embedding placeholder
# ---------------------------------------------------------------------------

async def _get_embedding(text: str, model: str = "text-embedding-3-small") -> list[float]:
    """Compute an embedding vector for *text*.

    If an OpenAI-compatible API key is configured (``OPENAI_API_KEY``), we call
    the real embeddings endpoint via ``httpx``.  Otherwise we return a
    deterministic placeholder vector derived from a hash so that the rest of
    the pipeline can still run in dev/test without an API key.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

    if api_key:
        import httpx

        async with httpx.AsyncClient(timeout=30.0) as http:
            resp = await http.post(
                f"{base_url}/embeddings",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"input": text, "model": model},
            )
            resp.raise_for_status()
            data = resp.json()
            return data["data"][0]["embedding"]

    # Deterministic placeholder (1536-d) for dev/test
    digest = hashlib.sha256(text.encode()).hexdigest()
    rng_seed = int(digest[:8], 16)
    import random

    rng = random.Random(rng_seed)
    return [rng.gauss(0, 0.1) for _ in range(1536)]


async def _get_embeddings_batch(
    texts: list[str], model: str = "text-embedding-3-small"
) -> list[list[float]]:
    """Batch-embed a list of texts.

    Uses the OpenAI batch endpoint when an API key is present, otherwise falls
    back to calling ``_get_embedding`` individually.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

    if api_key and texts:
        import httpx

        async with httpx.AsyncClient(timeout=60.0) as http:
            resp = await http.post(
                f"{base_url}/embeddings",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"input": texts, "model": model},
            )
            resp.raise_for_status()
            data = resp.json()
            # Sort by index to preserve input order
            sorted_data = sorted(data["data"], key=lambda d: d["index"])
            return [d["embedding"] for d in sorted_data]

    return [await _get_embedding(t, model) for t in texts]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _collection_name(scope: str, suffix: str) -> str:
    return f"{scope}_{suffix}"


def _point_id(content: str, prefix: str = "") -> str:
    """Generate a deterministic UUID from content, compatible with Qdrant."""
    hashed = hashlib.sha256((prefix + content).encode()).digest()
    return str(uuid.UUID(bytes=hashed[:16], version=4))


# ---------------------------------------------------------------------------
# Collection management
# ---------------------------------------------------------------------------

async def qdrant_ensure_collection(
    scope: str,
    collection_suffix: str,
    dimension: int = 1536,
) -> str:
    """Create a Qdrant collection if it does not already exist.

    Returns the full collection name.
    """
    client = await get_qdrant_client()
    name = _collection_name(scope, collection_suffix)

    if not await client.collection_exists(name):
        await client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(
                size=dimension,
                distance=Distance.COSINE,
            ),
        )
        logger.info("Created Qdrant collection %s (dim=%d)", name, dimension)

    return name


# ---------------------------------------------------------------------------
# Upsert operations
# ---------------------------------------------------------------------------

async def qdrant_upsert_entities(
    scope: str,
    entities: list[dict[str, Any]],
    embedding_model: str = "text-embedding-3-small",
) -> int:
    """Embed and upsert entities into the scoped ``entities`` collection.

    Each entity dict should have ``entity_id``, ``entity_name``, ``entity_type``,
    and ``description``.
    """
    if not entities:
        return 0

    client = await get_qdrant_client()
    coll = await qdrant_ensure_collection(scope, "entities")

    texts = [e.get("description", e.get("entity_name", "")) for e in entities]
    embeddings = await _get_embeddings_batch(texts, embedding_model)

    points = []
    for entity, emb in zip(entities, embeddings):
        eid = entity.get("entity_id") or entity.get("entity_name", "")
        points.append(
            PointStruct(
                id=_point_id(eid, prefix="ent-"),
                vector=emb,
                payload={
                    "entity_id": eid,
                    "entity_name": entity.get("entity_name", ""),
                    "entity_type": entity.get("entity_type", ""),
                    "description": entity.get("description", ""),
                    "scope": scope,
                },
            )
        )

    await client.upsert(collection_name=coll, points=points)
    return len(points)


async def qdrant_upsert_relations(
    scope: str,
    relations: list[dict[str, Any]],
    embedding_model: str = "text-embedding-3-small",
) -> int:
    """Embed and upsert relations into the scoped ``relations`` collection."""
    if not relations:
        return 0

    client = await get_qdrant_client()
    coll = await qdrant_ensure_collection(scope, "relations")

    texts = [
        f"{r.get('source_entity', '')} -> {r.get('target_entity', '')}: "
        f"{r.get('keywords', '')} {r.get('description', '')}"
        for r in relations
    ]
    embeddings = await _get_embeddings_batch(texts, embedding_model)

    points = []
    for rel, emb in zip(relations, embeddings):
        rid = f"{rel.get('source_entity', '')}::{rel.get('target_entity', '')}"
        points.append(
            PointStruct(
                id=_point_id(rid, prefix="rel-"),
                vector=emb,
                payload={
                    "source_entity": rel.get("source_entity", ""),
                    "target_entity": rel.get("target_entity", ""),
                    "keywords": rel.get("keywords", ""),
                    "description": rel.get("description", ""),
                    "weight": rel.get("weight", 1.0),
                    "scope": scope,
                },
            )
        )

    await client.upsert(collection_name=coll, points=points)
    return len(points)


async def qdrant_upsert_chunks(
    scope: str,
    chunks: list[dict[str, Any]],
    embedding_model: str = "text-embedding-3-small",
) -> int:
    """Embed and upsert text chunks into the scoped ``chunks`` collection."""
    if not chunks:
        return 0

    client = await get_qdrant_client()
    coll = await qdrant_ensure_collection(scope, "chunks")

    texts = [c.get("content", "") for c in chunks]
    embeddings = await _get_embeddings_batch(texts, embedding_model)

    points = []
    for chunk, emb in zip(chunks, embeddings):
        cid = f"{chunk.get('full_doc_id', '')}::{chunk.get('chunk_order_index', 0)}"
        points.append(
            PointStruct(
                id=_point_id(cid, prefix="chk-"),
                vector=emb,
                payload={
                    "content": chunk.get("content", ""),
                    "full_doc_id": chunk.get("full_doc_id", ""),
                    "chunk_order_index": chunk.get("chunk_order_index", 0),
                    "tokens": chunk.get("tokens", 0),
                    "scope": scope,
                },
            )
        )

    await client.upsert(collection_name=coll, points=points)
    return len(points)


# ---------------------------------------------------------------------------
# Search operations
# ---------------------------------------------------------------------------

async def _search(
    scope: str,
    collection_suffix: str,
    query: str,
    top_k: int = 10,
    embedding_model: str = "text-embedding-3-small",
) -> list[dict[str, Any]]:
    """Generic vector search helper."""
    client = await get_qdrant_client()
    coll = _collection_name(scope, collection_suffix)

    if not await client.collection_exists(coll):
        return []

    query_vec = await _get_embedding(query, embedding_model)

    results = await client.search(
        collection_name=coll,
        query_vector=query_vec,
        query_filter=models.Filter(
            must=[
                models.FieldCondition(
                    key="scope",
                    match=models.MatchValue(value=scope),
                )
            ]
        ),
        limit=top_k,
    )

    return [
        {**hit.payload, "score": hit.score}
        for hit in results
        if hit.payload
    ]


async def qdrant_search_entities(
    scope: str,
    query: str,
    top_k: int = 10,
    embedding_model: str = "text-embedding-3-small",
) -> list[dict[str, Any]]:
    """Search for entities in the scoped ``entities`` collection."""
    return await _search(scope, "entities", query, top_k, embedding_model)


async def qdrant_search_relations(
    scope: str,
    query: str,
    top_k: int = 10,
    embedding_model: str = "text-embedding-3-small",
) -> list[dict[str, Any]]:
    """Search for relations in the scoped ``relations`` collection."""
    return await _search(scope, "relations", query, top_k, embedding_model)


async def qdrant_search_chunks(
    scope: str,
    query: str,
    top_k: int = 10,
    embedding_model: str = "text-embedding-3-small",
) -> list[dict[str, Any]]:
    """Search for text chunks in the scoped ``chunks`` collection."""
    return await _search(scope, "chunks", query, top_k, embedding_model)
