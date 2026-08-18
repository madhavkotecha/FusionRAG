"""ADR-0009: Unified Knowledge Infrastructure.

Single shared layer serving all three engines:
  - Neo4j  → knowledge graph (entities, relations, communities)
  - Qdrant → vector store (chunk + entity embeddings)
  - OpenSearch → document store (BM25 + kNN) and mutual index
  - Redis  → L2/L3/L4 cache
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ChunkRecord:
    id: str
    content: str
    document_id: str
    embedding: list[float] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class EntityRecord:
    id: str
    name: str
    entity_type: str
    description: str = ""
    source_chunk_ids: list[str] = field(default_factory=list)
    properties: dict = field(default_factory=dict)


@dataclass
class RelationRecord:
    id: str
    source: str
    target: str
    relation_type: str
    description: str = ""
    source_chunk_ids: list[str] = field(default_factory=list)


class KnowledgeStore:
    """Unified access layer for all four storage backends (ADR-0009)."""

    def __init__(
        self,
        datastore_id: str = "",
        neo4j_uri: str | None = None,
        neo4j_user: str | None = None,
        neo4j_password: str | None = None,
        qdrant_url: str | None = None,
        qdrant_api_key: str | None = None,
        opensearch_host: str | None = None,
        opensearch_port: int | None = None,
        opensearch_user: str | None = None,
        opensearch_password: str | None = None,
        redis_url: str | None = None,
        vector_collection: str | None = None,
        doc_index: str | None = None,
    ) -> None:
        self._neo4j_uri = neo4j_uri or os.environ.get("NEO4J_URI", "bolt://neo4j:7687")
        self._neo4j_user = neo4j_user or os.environ.get("NEO4J_USERNAME", "neo4j")
        self._neo4j_password = neo4j_password or os.environ["NEO4J_PASSWORD"]

        self._qdrant_url = qdrant_url or os.environ.get("RRAG_QDRANT_URL", "http://qdrant:6333")
        self._qdrant_api_key = qdrant_api_key or os.environ.get("RRAG_QDRANT_API_KEY") or None

        self._os_host = opensearch_host or os.environ.get("RRAG_OPENSEARCH_HOST", "opensearch")
        self._os_port = opensearch_port or int(os.environ.get("RRAG_OPENSEARCH_PORT", "9200"))
        self._os_user = opensearch_user or os.environ.get("OPENSEARCH_USERNAME", "admin")
        self._os_password = opensearch_password or os.environ.get("OPENSEARCH_PASSWORD", "")

        self._redis_url = redis_url or os.environ.get("REDIS_URL", "redis://redis:6379/0")

        # Per-datastore isolation matches the ingestion convention: data is
        # written to `rrag_ds_{datastore_id}` collections/indices (see
        # qdrant_indexer.py / opensearch_indexer.py). Fall back to the shared
        # `rrag_vectors` namespace when no datastore is scoped.
        self.datastore_id = datastore_id
        default_namespace = f"rrag_ds_{datastore_id}" if datastore_id else "rrag_vectors"
        self.vector_collection = vector_collection or default_namespace
        self.doc_index = doc_index or default_namespace

        self._neo4j_driver: Any = None
        self._qdrant_client: Any = None
        self._os_client: Any = None
        self._redis_client: Any = None

    # ── Connection management ─────────────────────────────────────────────

    def _get_neo4j(self) -> Any:
        if self._neo4j_driver is None:
            from neo4j import AsyncGraphDatabase
            self._neo4j_driver = AsyncGraphDatabase.driver(
                self._neo4j_uri, auth=(self._neo4j_user, self._neo4j_password)
            )
        return self._neo4j_driver

    def _get_qdrant(self) -> Any:
        if self._qdrant_client is None:
            from qdrant_client import QdrantClient
            self._qdrant_client = QdrantClient(
                url=self._qdrant_url, api_key=self._qdrant_api_key
            )
        return self._qdrant_client

    def _get_opensearch(self) -> Any:
        if self._os_client is None:
            from opensearchpy import OpenSearch
            kwargs: dict = {
                "hosts": [{"host": self._os_host, "port": self._os_port}],
                "use_ssl": False,
                "verify_certs": False,
                "ssl_show_warn": False,
            }
            if self._os_password:
                kwargs["http_auth"] = (self._os_user, self._os_password)
            self._os_client = OpenSearch(**kwargs)
        return self._os_client

    def _get_redis(self) -> Any:
        if self._redis_client is None:
            import redis.asyncio as aioredis
            self._redis_client = aioredis.from_url(self._redis_url, decode_responses=True)
        return self._redis_client

    def _get_sync_redis(self) -> Any:
        """Return a synchronous Redis client for callers that require it (e.g. QueryCache)."""
        try:
            from redis import Redis
            return Redis.from_url(self._redis_url, decode_responses=True)
        except Exception:
            return None

    async def close(self) -> None:
        if self._neo4j_driver:
            await self._neo4j_driver.close()
            self._neo4j_driver = None
        if self._qdrant_client:
            self._qdrant_client.close()
            self._qdrant_client = None
        if self._redis_client:
            await self._redis_client.aclose()
            self._redis_client = None

    # ── Graph store (Neo4j) ───────────────────────────────────────────────

    async def upsert_entity(self, entity: EntityRecord, datastore_id: str = "") -> None:
        driver = self._get_neo4j()
        import re
        etype = re.sub(r"[^A-Za-z0-9_]", "_", entity.entity_type).strip("_") or "Entity"
        async with driver.session() as session:
            if datastore_id:
                await session.run(
                    f"MERGE (n:`{etype}` {{name: $name, datastore_id: $ds_id}}) "
                    "SET n.description = $desc, n.entity_id = $eid, n += $props",
                    name=entity.name, ds_id=datastore_id, desc=entity.description,
                    eid=entity.id, props=entity.properties,
                )
            else:
                await session.run(
                    f"MERGE (n:`{etype}` {{name: $name}}) "
                    "SET n.description = $desc, n.entity_id = $eid, n += $props",
                    name=entity.name, desc=entity.description,
                    eid=entity.id, props=entity.properties,
                )

    async def upsert_relation(self, relation: RelationRecord, datastore_id: str = "") -> None:
        driver = self._get_neo4j()
        import re
        rel_type = re.sub(r"[^A-Za-z0-9_]", "_", relation.relation_type).upper().strip("_") or "RELATED_TO"
        async with driver.session() as session:
            if datastore_id:
                await session.run(
                    f"MATCH (a {{name: $src, datastore_id: $ds_id}}), (b {{name: $tgt, datastore_id: $ds_id}}) "
                    f"MERGE (a)-[r:`{rel_type}`]->(b) "
                    "SET r.description = $desc, r.datastore_id = $ds_id",
                    src=relation.source, tgt=relation.target, desc=relation.description, ds_id=datastore_id,
                )
            else:
                await session.run(
                    f"MATCH (a {{name: $src}}), (b {{name: $tgt}}) "
                    f"MERGE (a)-[r:`{rel_type}`]->(b) SET r.description = $desc",
                    src=relation.source, tgt=relation.target, desc=relation.description,
                )

    async def search_entities_local(
        self, keywords: list[str], datastore_id: str = "", limit: int = 20
    ) -> list[dict]:
        """Local entity search: match keywords against entity names/descriptions."""
        if not keywords:
            return []
        driver = self._get_neo4j()
        conditions = []
        params: dict = {"limit": limit}
        for i, kw in enumerate(keywords):
            pk = f"kw{i}"
            conditions.append(
                f"(toLower(n.name) CONTAINS ${pk} OR toLower(n.description) CONTAINS ${pk})"
            )
            params[pk] = kw.lower()

        where = " OR ".join(conditions)
        if datastore_id:
            params["ds_id"] = datastore_id
            cypher = (
                f"MATCH (n) WHERE n.datastore_id = $ds_id AND ({where}) "
                "OPTIONAL MATCH (n)-[r]-(m) WHERE m.datastore_id = $ds_id "
                "RETURN n.name AS name, n.description AS description, "
                "collect(DISTINCT {target: m.name, rel: type(r)}) AS relations "
                "LIMIT $limit"
            )
        else:
            cypher = (
                f"MATCH (n) WHERE {where} "
                "OPTIONAL MATCH (n)-[r]-(m) "
                "RETURN n.name AS name, n.description AS description, "
                "collect(DISTINCT {target: m.name, rel: type(r)}) AS relations "
                "LIMIT $limit"
            )

        results = []
        async with driver.session() as session:
            records = await session.run(cypher, **params)
            async for rec in records:
                results.append({
                    "name": rec["name"],
                    "description": rec["description"] or "",
                    "relations": [r for r in rec["relations"] if r["target"]],
                    "source": "kg_local",
                })
        return results

    async def search_entities_global(
        self, datastore_id: str = "", limit: int = 20
    ) -> list[dict]:
        """Global community retrieval: hub entities by degree centrality."""
        driver = self._get_neo4j()
        if datastore_id:
            cypher = (
                "MATCH (n {datastore_id: $ds_id})-[r]-(m {datastore_id: $ds_id}) "
                "WITH n, count(r) AS degree ORDER BY degree DESC LIMIT $limit "
                "MATCH (n)-[r2]-(m2 {datastore_id: $ds_id}) "
                "RETURN n.name AS name, n.description AS description, "
                "collect(DISTINCT {target: m2.name, rel: type(r2)}) AS relations"
            )
            params: dict = {"ds_id": datastore_id, "limit": limit}
        else:
            cypher = (
                "MATCH (n)-[r]-(m) WITH n, count(r) AS degree "
                "ORDER BY degree DESC LIMIT $limit "
                "MATCH (n)-[r2]-(m2) "
                "RETURN n.name AS name, n.description AS description, "
                "collect(DISTINCT {target: m2.name, rel: type(r2)}) AS relations"
            )
            params = {"limit": limit}

        results = []
        async with driver.session() as session:
            records = await session.run(cypher, **params)
            async for rec in records:
                results.append({
                    "name": rec["name"],
                    "description": rec["description"] or "",
                    "relations": [r for r in rec["relations"] if r["target"]],
                    "source": "kg_global",
                })
        return results

    async def get_entity_names(self, datastore_id: str = "", limit: int = 1000) -> list[str]:
        """Return existing entity names in the graph (for ADR-0011 synonym fusion)."""
        driver = self._get_neo4j()
        if datastore_id:
            cypher = "MATCH (n {datastore_id: $ds_id}) RETURN n.name AS name LIMIT $limit"
            params: dict = {"ds_id": datastore_id, "limit": limit}
        else:
            cypher = "MATCH (n) RETURN n.name AS name LIMIT $limit"
            params = {"limit": limit}

        names: list[str] = []
        async with driver.session() as session:
            records = await session.run(cypher, **params)
            async for rec in records:
                if rec["name"]:
                    names.append(rec["name"])
        return names

    # ── Vector store (Qdrant) ─────────────────────────────────────────────

    def search_vectors(
        self, embedding: list[float], top_k: int = 20, filter_payload: dict | None = None
    ) -> list[dict]:
        """Synchronous Qdrant ANN search."""
        client = self._get_qdrant()
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        qdrant_filter = None
        if filter_payload:
            conditions = [
                FieldCondition(key=k, match=MatchValue(value=v))
                for k, v in filter_payload.items()
            ]
            qdrant_filter = Filter(must=conditions)

        hits = client.query_points(
            collection_name=self.vector_collection,
            query=embedding,
            limit=top_k,
            query_filter=qdrant_filter,
        )
        results = []
        for hit in hits.points:
            payload = hit.payload or {}
            results.append({
                "id": payload.get("chunk_id", str(hit.id)),
                "content": payload.get("content", ""),
                "score": hit.score,
                "document_id": payload.get("document_id", ""),
                "metadata": payload.get("metadata", {}),
                "source": "qdrant",
            })
        return results

    def upsert_vectors(self, chunks: list[ChunkRecord]) -> None:
        """Upsert chunk embeddings into Qdrant."""
        if not chunks:
            return
        import uuid

        client = self._get_qdrant()
        from qdrant_client.models import PointStruct

        points = [
            PointStruct(
                # Stable, deterministic point ID so re-running the updater
                # upserts (not duplicates) the same chunk. Mirrors
                # qdrant_indexer.py; `hash()` is process-salted and unsafe here.
                id=str(uuid.uuid5(uuid.NAMESPACE_DNS, c.id)),
                vector=c.embedding,
                payload={
                    "chunk_id": c.id,
                    "content": c.content,
                    "document_id": c.document_id,
                    "metadata": c.metadata,
                },
            )
            for c in chunks
            if c.embedding
        ]
        if points:
            client.upsert(collection_name=self.vector_collection, points=points)

    # ── Document store (OpenSearch) ────────────────────────────────────────

    def search_bm25(self, query: str, top_k: int = 20) -> list[dict]:
        """BM25 full-text search.

        Datastore isolation is by index name (`self.doc_index` is already
        scoped to `rrag_ds_{datastore_id}`), matching opensearch_indexer.py.
        Indexed documents carry no `datastore_id` field, so no term filter.
        """
        client = self._get_opensearch()
        body = {"size": top_k, "query": {"match": {"content": {"query": query, "operator": "or"}}}}
        try:
            resp = client.search(index=self.doc_index, body=body)
            return self._parse_os_hits(resp)
        except Exception as e:
            logger.warning(f"BM25 search failed: {e}")
            return []

    def search_knn(self, embedding: list[float], top_k: int = 20) -> list[dict]:
        """kNN vector search via OpenSearch (isolation by index name)."""
        client = self._get_opensearch()
        body = {"size": top_k, "query": {"knn": {"embedding": {"vector": embedding, "k": top_k}}}}
        try:
            resp = client.search(index=self.doc_index, body=body)
            return self._parse_os_hits(resp)
        except Exception as e:
            logger.warning(f"kNN search failed: {e}")
            return []

    def _parse_os_hits(self, response: dict) -> list[dict]:
        results = []
        for hit in response.get("hits", {}).get("hits", []):
            src = hit.get("_source", {})
            results.append({
                "id": src.get("chunk_id", hit.get("_id", "")),
                "content": src.get("content", ""),
                "score": float(hit.get("_score") or 0.0),
                "document_id": src.get("document_id", ""),
                "metadata": src.get("metadata", {}),
                "source": "opensearch",
            })
        return results

    def index_chunk(self, chunk: ChunkRecord, datastore_id: str = "") -> None:
        """Index a chunk in OpenSearch."""
        client = self._get_opensearch()
        doc = {
            "chunk_id": chunk.id,
            "content": chunk.content,
            "document_id": chunk.document_id,
            "datastore_id": datastore_id,
            "metadata": chunk.metadata,
        }
        if chunk.embedding:
            doc["embedding"] = chunk.embedding
        try:
            client.index(index=self.doc_index, id=chunk.id, body=doc)
        except Exception as e:
            logger.warning(f"OpenSearch index failed for chunk {chunk.id}: {e}")

    # ── Cache (Redis) ─────────────────────────────────────────────────────

    @staticmethod
    def _cache_key(prefix: str, query: str) -> str:
        h = hashlib.sha256(query.encode()).hexdigest()[:16]
        return f"{prefix}:{h}"

    async def cache_get(self, query: str, prefix: str = "l2") -> Any | None:
        """L2 exact-match cache lookup."""
        try:
            redis = self._get_redis()
            raw = await redis.get(self._cache_key(prefix, query))
            return json.loads(raw) if raw else None
        except Exception:
            return None

    async def cache_set(
        self, query: str, value: Any, ttl: int = 3600, prefix: str = "l2"
    ) -> None:
        """L2 exact-match cache write."""
        try:
            redis = self._get_redis()
            await redis.setex(self._cache_key(prefix, query), ttl, json.dumps(value))
        except Exception as e:
            logger.debug(f"Cache write failed: {e}")

    async def cache_invalidate_by_entities(self, entity_names: list[str]) -> int:
        """Selective cache invalidation for queries mentioning updated entities (ADR-0011 step 7)."""
        try:
            redis = self._get_redis()
            pattern = "l2:*"
            cursor = 0
            invalidated = 0
            while True:
                cursor, keys = await redis.scan(cursor, match=pattern, count=100)
                for key in keys:
                    raw = await redis.get(key)
                    if raw:
                        cached = json.loads(raw)
                        query_text = cached.get("query", "")
                        if any(e.lower() in query_text.lower() for e in entity_names):
                            await redis.delete(key)
                            invalidated += 1
                if cursor == 0:
                    break
            return invalidated
        except Exception as e:
            logger.warning(f"Cache invalidation failed: {e}")
            return 0
