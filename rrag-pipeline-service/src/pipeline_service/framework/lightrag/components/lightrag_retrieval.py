"""LightRAG Retrieval composite component.

Five-step pipeline that handles query processing:
1. Extract Keywords -- LLM keyword extraction from query
2. Search Knowledge Graph -- entity & relation search via Neo4j / Qdrant
3. Search Vectors -- chunk search via Qdrant
4. Assemble Context -- build token-budgeted context (with sufficiency gate)
5. Generate Answer -- LLM answer generation from context
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pipeline_service.framework import component, step, CompositeComponent

logger = logging.getLogger(__name__)


@component(
    category="retriever",
    name="LightRAG Retrieval",
    description=(
        "Query-time retrieval: extract keywords, search the knowledge graph "
        "and vector stores, assemble context with token budget, then generate "
        "a grounded answer."
    ),
    input_ports=[
        {"name": "query", "type": "str"},
    ],
    output_ports=[
        {"name": "answer", "type": "str"},
        {"name": "context", "type": "dict"},
    ],
)
class LightRAGRetrieval(CompositeComponent):

    CONFIG_SCHEMA = {
        "type": "object",
        "properties": {
            "scope": {
                "type": "string",
                "description": "Workspace scope key",
            },
            "mode": {
                "type": "string",
                "enum": ["local", "global", "hybrid", "mix", "naive"],
                "default": "mix",
            },
            "top_k": {
                "type": "integer",
                "default": 10,
            },
            "max_entity_tokens": {
                "type": "integer",
                "default": 4000,
            },
            "max_relation_tokens": {
                "type": "integer",
                "default": 4000,
            },
            "max_total_tokens": {
                "type": "integer",
                "default": 12000,
            },
            "generation_model": {
                "type": "string",
                "default": "gpt-4o-mini",
            },
            "embedding_model": {
                "type": "string",
                "default": "text-embedding-3-small",
            },
            "response_type": {
                "type": "string",
                "default": "Multiple Paragraphs",
            },
            "language": {
                "type": "string",
                "default": "English",
            },
        },
        "required": ["scope"],
    }

    # ------------------------------------------------------------------
    # Step 1: Extract Keywords
    # ------------------------------------------------------------------

    @step(order=1, name="Extract Keywords", description="Extract high/low level keywords from query via LLM")
    async def extract_keywords(
        self, data: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        from ..extraction import _call_llm
        from ..prompts import KEYWORD_EXTRACTION_PROMPT

        query = data.get("query", "")
        language = config.get("language", "English")
        model = config.get("generation_model", "gpt-4o-mini")

        prompt = KEYWORD_EXTRACTION_PROMPT.format(query=query, language=language)
        raw = await _call_llm(prompt, model)

        hl_keywords: list[str] = []
        ll_keywords: list[str] = []

        if raw:
            try:
                parsed = json.loads(raw)
                hl_keywords = parsed.get("high_level_keywords", [])
                ll_keywords = parsed.get("low_level_keywords", [])
            except (json.JSONDecodeError, TypeError):
                logger.warning("Failed to parse keyword extraction output")

        return {
            "hl_keywords": hl_keywords,
            "ll_keywords": ll_keywords,
        }

    # ------------------------------------------------------------------
    # Step 2: Search Knowledge Graph
    # ------------------------------------------------------------------

    @step(order=2, name="Search Knowledge Graph", description="Search entities and relations via Neo4j and Qdrant")
    async def search_knowledge_graph(
        self, data: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        from ..storage.qdrant_ops import qdrant_search_entities, qdrant_search_relations
        from ..storage.neo4j_ops import neo4j_enrich_entities, neo4j_enrich_relations
        from ..storage.redis_ops import redis_get_related_chunks

        scope = config["scope"]
        top_k = config.get("top_k", 10)
        embedding_model = config.get("embedding_model", "text-embedding-3-small")
        mode = config.get("mode", "mix")
        query = data.get("query", "")

        # Build search terms from keywords + original query
        hl_keywords = data.get("hl_keywords", [])
        ll_keywords = data.get("ll_keywords", [])
        search_text = " ".join([query] + hl_keywords + ll_keywords)

        entities: list[dict] = []
        relations: list[dict] = []
        graph_chunks: list[dict] = []

        if mode != "naive":
            # Vector search for entities and relations
            entities = await qdrant_search_entities(
                scope, search_text, top_k, embedding_model
            )
            relations = await qdrant_search_relations(
                scope, search_text, top_k, embedding_model
            )

            # Enrich from Neo4j (add neighbor info, full properties)
            entities = await neo4j_enrich_entities(scope, entities)
            relations = await neo4j_enrich_relations(scope, relations)

            # Get related chunks from KV store
            graph_chunks = await redis_get_related_chunks(scope, entities, relations)

        return {
            "entities": entities,
            "relations": relations,
            "graph_chunks": graph_chunks,
        }

    # ------------------------------------------------------------------
    # Step 3: Search Vectors
    # ------------------------------------------------------------------

    @step(order=3, name="Search Vectors", description="Direct vector search on document chunks")
    async def search_vectors(
        self, data: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        from ..storage.qdrant_ops import qdrant_search_chunks

        scope = config["scope"]
        top_k = config.get("top_k", 10)
        embedding_model = config.get("embedding_model", "text-embedding-3-small")
        query = data.get("query", "")

        vector_chunks = await qdrant_search_chunks(
            scope, query, top_k, embedding_model
        )

        return {"vector_chunks": vector_chunks}

    # ------------------------------------------------------------------
    # Step 4: Assemble Context
    # ------------------------------------------------------------------

    @step(
        order=4,
        name="Assemble Context",
        description="Build token-budgeted context from graph and vector results",
        outputs=["sufficient", "Search Knowledge Graph"],
    )
    async def assemble_context(
        self, data: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        from ..context_builder import build_context

        mode = config.get("mode", "mix")
        entities = data.get("entities", [])
        relations = data.get("relations", [])
        graph_chunks = data.get("graph_chunks", [])
        vector_chunks = data.get("vector_chunks", [])

        context = build_context(
            mode=mode,
            entities=entities,
            relations=relations,
            graph_chunks=graph_chunks,
            vector_chunks=vector_chunks,
            max_entity_tokens=config.get("max_entity_tokens", 4000),
            max_relation_tokens=config.get("max_relation_tokens", 4000),
            max_total_tokens=config.get("max_total_tokens", 12000),
        )

        # Sufficiency check: if we have at least some context go ahead
        has_context = (
            context["entity_count"] > 0
            or context["relation_count"] > 0
            or context["chunk_count"] > 0
        )

        route = "sufficient" if has_context else "Search Knowledge Graph"

        return {
            "context": context,
            "_route": route,
        }

    # ------------------------------------------------------------------
    # Step 5: Generate Answer
    # ------------------------------------------------------------------

    @step(order=5, name="Generate Answer", description="Generate the final answer using LLM and assembled context")
    async def generate_answer(
        self, data: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        from ..extraction import _call_llm
        from ..prompts import RAG_RESPONSE_PROMPT

        query = data.get("query", "")
        context = data.get("context", {})
        model = config.get("generation_model", "gpt-4o-mini")
        response_type = config.get("response_type", "Multiple Paragraphs")

        prompt = RAG_RESPONSE_PROMPT.format(
            response_type=response_type,
            entities_context=context.get("entities_context", "[]"),
            relations_context=context.get("relations_context", "[]"),
            chunks_context=context.get("chunks_context", "[]"),
        )

        answer = await _call_llm(
            query, model, system_prompt=prompt
        )

        return {
            "answer": answer,
            "context": context,
        }
