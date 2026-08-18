"""LightRAG Ingestion composite component.

Five-step pipeline that processes documents through:
1. Chunk Documents -- split into token-sized chunks
2. Extract Entities & Relations -- LLM extraction with gleaning
3. Merge & Deduplicate -- entity/relation deduplication
4. Store to Graph -- persist entities and relations in Neo4j
5. Store Vectors & KV -- persist embeddings in Qdrant and raw data in Redis
"""

from __future__ import annotations

from typing import Any

from pipeline_service.framework import component, step, CompositeComponent


@component(
    category="graph_builder",
    name="LightRAG Ingestion",
    description=(
        "End-to-end document ingestion: chunk, extract entities/relations via "
        "LLM, merge duplicates, and persist to Neo4j + Qdrant + Redis."
    ),
    input_ports=[
        {"name": "documents", "type": "list[dict]"},
    ],
    output_ports=[
        {"name": "ingestion_report", "type": "dict"},
    ],
)
class LightRAGIngestion(CompositeComponent):

    CONFIG_SCHEMA = {
        "type": "object",
        "properties": {
            "scope": {
                "type": "string",
                "description": "Workspace scope key, e.g. ws_abc_ds_1",
            },
            "chunk_size": {
                "type": "integer",
                "default": 1200,
                "description": "Max tokens per chunk",
            },
            "chunk_overlap": {
                "type": "integer",
                "default": 100,
                "description": "Overlap tokens between chunks",
            },
            "entity_types": {
                "type": "array",
                "items": {"type": "string"},
                "default": [
                    "Person", "Organization", "Location", "Event",
                    "Concept", "Method", "Technology",
                ],
            },
            "extraction_model": {
                "type": "string",
                "default": "gpt-4o-mini",
            },
            "max_gleaning": {
                "type": "integer",
                "default": 1,
            },
            "merge_threshold": {
                "type": "number",
                "default": 0.85,
            },
            "embedding_model": {
                "type": "string",
                "default": "text-embedding-3-small",
            },
        },
        "required": ["scope"],
    }

    # ------------------------------------------------------------------
    # Step 1
    # ------------------------------------------------------------------

    @step(order=1, name="Chunk Documents", description="Split documents into token-sized chunks")
    async def chunk_documents(
        self, data: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        from ..chunking import chunking_by_token_size

        documents = data.get("documents", [])
        chunk_size = config.get("chunk_size", 1200)
        overlap = config.get("chunk_overlap", 100)

        all_chunks: list[dict] = []
        for doc in documents:
            doc_id = doc.get("doc_id", doc.get("id", "unknown"))
            content = doc.get("content", "")
            chunks = chunking_by_token_size(
                content=content,
                doc_id=doc_id,
                chunk_size=chunk_size,
                overlap=overlap,
            )
            all_chunks.extend(chunks)

        return {"chunks": all_chunks, "chunk_count": len(all_chunks)}

    # ------------------------------------------------------------------
    # Step 2
    # ------------------------------------------------------------------

    @step(
        order=2,
        name="Extract Entities And Relations",
        description="LLM-based entity and relation extraction with gleaning",
        retry=2,
        retry_condition="_extraction_incomplete",
    )
    async def extract_entities_and_relations(
        self, data: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        from ..extraction import llm_extract_entities_and_relations

        chunks = data.get("chunks", [])
        entity_types = config.get("entity_types")
        model = config.get("extraction_model", "gpt-4o-mini")
        max_gleaning = config.get("max_gleaning", 1)

        all_entities: list[dict] = []
        all_relations: list[dict] = []

        for chunk in chunks:
            result = await llm_extract_entities_and_relations(
                content=chunk.get("content", ""),
                entity_types=entity_types,
                model=model,
                max_gleaning=max_gleaning,
            )
            all_entities.extend(result.get("entities", []))
            all_relations.extend(result.get("relations", []))

        # Flag as incomplete if nothing was extracted from non-empty chunks
        incomplete = len(all_entities) == 0 and len(chunks) > 0

        return {
            "raw_entities": all_entities,
            "raw_relations": all_relations,
            "_extraction_incomplete": incomplete,
        }

    # ------------------------------------------------------------------
    # Step 3
    # ------------------------------------------------------------------

    @step(order=3, name="Merge And Deduplicate", description="Merge duplicate entities and relations")
    async def merge_and_deduplicate(
        self, data: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        from ..merging import merge_entities_by_similarity, merge_relations

        threshold = config.get("merge_threshold", 0.85)
        embedding_model = config.get("embedding_model", "text-embedding-3-small")

        entities = await merge_entities_by_similarity(
            data.get("raw_entities", []),
            threshold=threshold,
            embedding_model=embedding_model,
        )
        relations = merge_relations(data.get("raw_relations", []))

        return {
            "entities": entities,
            "relations": relations,
            "entity_count": len(entities),
            "relation_count": len(relations),
        }

    # ------------------------------------------------------------------
    # Step 4
    # ------------------------------------------------------------------

    @step(order=4, name="Store To Graph", description="Persist entities and relations in Neo4j")
    async def store_to_graph(
        self, data: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        from ..storage.neo4j_ops import neo4j_upsert_entities, neo4j_upsert_relations

        scope = config["scope"]
        entities = data.get("entities", [])
        relations = data.get("relations", [])

        ent_count = await neo4j_upsert_entities(scope, entities)
        rel_count = await neo4j_upsert_relations(scope, relations)

        return {
            "graph_entities_stored": ent_count,
            "graph_relations_stored": rel_count,
        }

    # ------------------------------------------------------------------
    # Step 5
    # ------------------------------------------------------------------

    @step(order=5, name="Store Vectors And KV", description="Persist embeddings in Qdrant and raw data in Redis")
    async def store_vectors_and_kv(
        self, data: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        from ..storage.qdrant_ops import (
            qdrant_upsert_entities,
            qdrant_upsert_relations,
            qdrant_upsert_chunks,
        )
        from ..storage.redis_ops import redis_store_chunks, redis_store_entity_mappings

        scope = config["scope"]
        embedding_model = config.get("embedding_model", "text-embedding-3-small")

        entities = data.get("entities", [])
        relations = data.get("relations", [])
        chunks = data.get("chunks", [])

        vec_ent = await qdrant_upsert_entities(scope, entities, embedding_model)
        vec_rel = await qdrant_upsert_relations(scope, relations, embedding_model)
        vec_chk = await qdrant_upsert_chunks(scope, chunks, embedding_model)

        kv_chunks = await redis_store_chunks(scope, chunks)
        kv_maps = await redis_store_entity_mappings(scope, entities, chunks)

        return {
            "vector_entities_stored": vec_ent,
            "vector_relations_stored": vec_rel,
            "vector_chunks_stored": vec_chk,
            "kv_chunks_stored": kv_chunks,
            "kv_entity_mappings_stored": kv_maps,
            "ingestion_report": {
                "chunks": data.get("chunk_count", 0),
                "entities": data.get("entity_count", 0),
                "relations": data.get("relation_count", 0),
                "scope": scope,
            },
        }
