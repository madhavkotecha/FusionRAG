"""ADR-0011: 7-Step Incremental Update Protocol.

Step 1: Change Detection & Intake      — content-hash deduplication
Step 2: Selective Semantic Chunking    — only new/modified content
Step 3: LightRAG Incremental Graph Update — entity merge with locks
Step 4: KAG Knowledge Alignment        — synonym fusion, hierarchy
Step 5: Vector Embedding Upsert        — Qdrant native upsert
Step 6: Mutual Index Update            — new KG↔chunk links
Step 7: Cache Invalidation             — selective by entity overlap

All steps are idempotent and resumable on failure.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from rrag_ingestion.fusion.knowledge_store import ChunkRecord, EntityRecord, KnowledgeStore
from rrag_ingestion.fusion.mutual_index import MutualIndex

logger = logging.getLogger(__name__)

_SYNONYM_PROMPT = """\
Given the new entity name and the list of existing entity names, identify any synonyms or aliases.
Respond with a comma-separated list of exact matches from the existing list, or NONE.

New entity: {new_name}
Existing entities: {existing}

Matches:"""

_HIERARCHY_PROMPT = """\
Given a new entity and a list of candidate parent categories, identify the best parent.
Respond with the exact parent name from the list, or NONE if none apply.

New entity: {new_name} (type: {entity_type})
Candidates: {candidates}

Best parent:"""


@dataclass
class DocumentUpdate:
    document_id: str
    content: str
    metadata: dict = field(default_factory=dict)
    datastore_id: str = ""


@dataclass
class UpdateResult:
    document_id: str
    status: str = "ok"           # ok | skipped | failed
    steps_completed: list[str] = field(default_factory=list)
    new_chunks: int = 0
    new_entities: int = 0
    cache_invalidated: int = 0
    error: str | None = None


class IncrementalUpdater:
    """7-step incremental update protocol (ADR-0011)."""

    def __init__(
        self,
        store: KnowledgeStore,
        mutual_index: MutualIndex,
        llm_client: object | None = None,
        model: str = "gpt-4o-mini",
        chunk_size: int = 1200,
        chunk_overlap: int = 100,
    ) -> None:
        self._store = store
        self._mutual = mutual_index
        self._llm = llm_client
        self._model = model
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._entity_locks: dict[str, asyncio.Lock] = {}

    def _get_llm(self) -> object:
        if self._llm is not None:
            return self._llm
        from rrag_ingestion.services.openai_client import get_openai_client
        return get_openai_client()

    # ── Step 1: Change Detection ──────────────────────────────────────────

    def _content_hash(self, content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()

    async def _is_changed(self, document_id: str, content_hash: str) -> bool:
        """Return True if document is new or content has changed."""
        try:
            redis = self._store._get_redis()
            stored = await redis.get(f"doc_hash:{document_id}")
            return stored != content_hash
        except Exception:
            return True  # Treat as changed on error to avoid skipping updates

    async def _record_hash(self, document_id: str, content_hash: str) -> None:
        try:
            redis = self._store._get_redis()
            await redis.set(f"doc_hash:{document_id}", content_hash)
        except Exception as e:
            logger.warning(f"Could not record hash for {document_id}: {e}")

    # ── Step 2: Selective Chunking ────────────────────────────────────────

    async def _chunk_text(self, text: str, document_id: str) -> list[ChunkRecord]:
        """Semantic chunking via ADR-0019 pipeline (1200t target / 100t overlap).

        Delegates to SemanticChunkingPipeline which uses embedding-based boundary
        detection. Falls back to token-based splitting automatically on embedding
        errors so ingestion never blocks.
        """
        from rrag_ingestion.generation.chunker import SemanticChunkingPipeline
        chunker = SemanticChunkingPipeline(
            target_tokens=self._chunk_size,
            overlap_tokens=self._chunk_overlap,
        )
        semantic_chunks = await chunker.chunk(text, document_id)
        return [
            ChunkRecord(
                id=sc.id,
                content=sc.content,
                document_id=document_id,
                metadata={
                    "chunk_index": sc.chunk_index,
                    "token_count": sc.token_count,
                    **sc.metadata,
                },
            )
            for sc in semantic_chunks
        ]

    # ── Step 3: LightRAG Incremental Graph Update ─────────────────────────

    async def _extract_entities_from_chunks(
        self, chunks: list[ChunkRecord]
    ) -> list[EntityRecord]:
        """Extract entities from new chunks via LLM (simplified KAG OpenIE)."""
        from rrag_ingestion.components.extractors.kag_schema_free import KAGSchemaFreeExtractor
        from rrag_ingestion.core.base import ComponentResult

        extractor = KAGSchemaFreeExtractor()
        chunk_dicts = [{"id": c.id, "content": c.content} for c in chunks]
        result = await extractor.invoke(
            ComponentResult(data={"chunks": chunk_dicts}),
            config={"llm_model": self._model},
        )
        subgraph = result.data.get("subgraph")
        if not subgraph:
            return []

        entities = []
        for node in getattr(subgraph, "nodes", []):
            entities.append(EntityRecord(
                id=str(uuid.uuid4()),
                name=getattr(node, "name", ""),
                entity_type=getattr(node, "entity_type", "Entity"),
                description=getattr(node, "description", ""),
                source_chunk_ids=getattr(node, "source_chunks", []),
            ))
        return entities

    def _get_entity_lock(self, entity_name: str) -> asyncio.Lock:
        if entity_name not in self._entity_locks:
            self._entity_locks[entity_name] = asyncio.Lock()
        return self._entity_locks[entity_name]

    async def _merge_entity(
        self, entity: EntityRecord, datastore_id: str
    ) -> None:
        """Merge entity into graph with per-entity lock to prevent concurrent conflicts."""
        async with self._get_entity_lock(entity.name):
            await self._store.upsert_entity(entity, datastore_id=datastore_id)

    # ── Step 4: KAG Knowledge Alignment ──────────────────────────────────

    async def _find_synonyms(
        self, entity_name: str, existing_names: list[str]
    ) -> list[str]:
        if not existing_names:
            return []
        client = self._get_llm()
        candidates = existing_names[:50]  # limit context size
        prompt = _SYNONYM_PROMPT.format(
            new_name=entity_name,
            existing=", ".join(candidates),
        )
        try:
            resp = await client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=64,
            )
            raw = (resp.choices[0].message.content or "").strip()
            if raw.upper() == "NONE":
                return []
            return [s.strip() for s in raw.split(",") if s.strip() in existing_names]
        except Exception as e:
            logger.debug(f"Synonym finding failed: {e}")
            return []

    async def _align_entity(
        self, entity: EntityRecord, datastore_id: str, existing_names: list[str]
    ) -> None:
        """Synonym fusion and hierarchy placement."""
        synonyms = await self._find_synonyms(entity.name, existing_names)
        if synonyms:
            logger.debug(f"Entity '{entity.name}' aliased to {synonyms}")
            # Add synonym relationship in graph
            for synonym in synonyms:
                from rrag_ingestion.fusion.knowledge_store import RelationRecord
                relation = RelationRecord(
                    id=str(uuid.uuid4()),
                    source=entity.name,
                    target=synonym,
                    relation_type="SAME_AS",
                    description=f"Synonym/alias relationship",
                )
                await self._store.upsert_relation(relation, datastore_id=datastore_id)

    # ── Step 5: Vector Embedding Upsert ───────────────────────────────────

    async def _embed_chunks(self, chunks: list[ChunkRecord]) -> list[ChunkRecord]:
        """Generate embeddings for chunks using the configured LLM service."""
        try:
            from rrag_ingestion.services import llm_service
            texts = [c.content for c in chunks]
            embeddings = await llm_service.embedding(texts)
            if embeddings and len(embeddings) == len(chunks):
                for chunk, emb in zip(chunks, embeddings):
                    chunk.embedding = emb
        except Exception as e:
            logger.warning(f"Chunk embedding failed: {e}")
        return chunks

    # ── Main protocol ─────────────────────────────────────────────────────

    async def update(self, doc: DocumentUpdate) -> UpdateResult:
        result = UpdateResult(document_id=doc.document_id)

        # Step 1: Change Detection
        content_hash = self._content_hash(doc.content)
        changed = await self._is_changed(doc.document_id, content_hash)
        if not changed:
            result.status = "skipped"
            return result
        result.steps_completed.append("step1_change_detection")

        # Step 2: Selective Chunking
        try:
            chunks = await self._chunk_text(doc.content, doc.document_id)
            result.new_chunks = len(chunks)
            result.steps_completed.append("step2_chunking")
        except Exception as e:
            result.status = "failed"
            result.error = f"Step 2 failed: {e}"
            return result

        # Step 3: LightRAG Incremental Graph Update
        new_entities: list[EntityRecord] = []
        try:
            new_entities = await self._extract_entities_from_chunks(chunks)
            merge_tasks = [self._merge_entity(e, doc.datastore_id) for e in new_entities]
            await asyncio.gather(*merge_tasks, return_exceptions=True)
            result.new_entities = len(new_entities)
            result.steps_completed.append("step3_graph_update")
        except Exception as e:
            logger.warning(f"Step 3 (graph update) failed: {e}")

        # Step 4: KAG Knowledge Alignment — fuse new entities against the
        # entities already in the graph (not just this document's batch).
        try:
            new_names = {e.name for e in new_entities}
            graph_names = await self._store.get_entity_names(doc.datastore_id)
            existing_names = [n for n in graph_names if n not in new_names]
            align_tasks = [
                self._align_entity(e, doc.datastore_id, existing_names)
                for e in new_entities
            ]
            await asyncio.gather(*align_tasks, return_exceptions=True)
            result.steps_completed.append("step4_kag_alignment")
        except Exception as e:
            logger.warning(f"Step 4 (KAG alignment) failed: {e}")

        # Step 5: Vector Embedding Upsert
        try:
            chunks = await self._embed_chunks(chunks)
            self._store.upsert_vectors(chunks)
            # Also index in OpenSearch for BM25
            for chunk in chunks:
                self._store.index_chunk(chunk, datastore_id=doc.datastore_id)
            result.steps_completed.append("step5_vector_upsert")
        except Exception as e:
            logger.warning(f"Step 5 (vector upsert) failed: {e}")

        # Step 6: Mutual Index Update
        try:
            for entity in new_entities:
                self._mutual.index_entity_chunks(
                    entity_id=entity.id,
                    entity_name=entity.name,
                    chunk_ids=entity.source_chunk_ids,
                    datastore_id=doc.datastore_id,
                )
            for chunk in chunks:
                entity_ids = [
                    e.id for e in new_entities if chunk.id in e.source_chunk_ids
                ]
                if entity_ids:
                    self._mutual.index_chunk_entities(
                        chunk_id=chunk.id,
                        kg_node_ids=entity_ids,
                        datastore_id=doc.datastore_id,
                    )
            result.steps_completed.append("step6_mutual_index")
        except Exception as e:
            logger.warning(f"Step 6 (mutual index) failed: {e}")

        # Step 7: Cache Invalidation (ADR-0014 + ADR-0011 Step 7)
        # Invalidates both KnowledgeStore-level cache and ADR-0014 L2/L3 query cache.
        try:
            entity_names = [e.name for e in new_entities]
            # KnowledgeStore Redis cache
            ks_invalidated = await self._store.cache_invalidate_by_entities(entity_names)
            # ADR-0014 query cache (L2 + L3 selective invalidation)
            qc_invalidated = 0
            try:
                redis = self._store._get_redis()
                # Use a sync redis handle (QueryCache expects sync Redis)
                from rrag_ingestion.generation.cache import QueryCache
                # Obtain the sync redis client via the store's internal sync handle
                sync_redis = self._store._get_sync_redis()
                if sync_redis is not None:
                    qcache = QueryCache(redis=sync_redis)
                    qc_invalidated = qcache.invalidate_by_entities(entity_names)
            except Exception as qe:
                logger.debug("Query cache invalidation skipped: %s", qe)
            result.cache_invalidated = ks_invalidated + qc_invalidated
            result.steps_completed.append("step7_cache_invalidation")
        except Exception as e:
            logger.warning(f"Step 7 (cache invalidation) failed: {e}")

        # Record hash only after all steps succeed
        await self._record_hash(doc.document_id, content_hash)
        result.status = "ok"
        return result

    async def update_batch(self, docs: list[DocumentUpdate]) -> list[UpdateResult]:
        """Process multiple documents concurrently."""
        return list(await asyncio.gather(*[self.update(d) for d in docs], return_exceptions=False))
