"""Seed data for pipeline templates and DB-backed service functions.

SEED_TEMPLATES provides the initial data for the pipeline_templates table
(used by the Alembic migration and test fixtures). The service functions query the DB.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.template import PipelineTemplate


SEED_TEMPLATES: list[dict] = [
    {
        "template_id": "vanilla_rag",
        "name": "Vanilla RAG",
        "description": "Simple document ingestion and retrieval: parse, chunk, embed, index",
        "category": "ingestion",
        "definition": {
            "nodes": [
                {"id": "n1", "type": "parser", "position": {"x": 100, "y": 200}, "data": {"label": "File Loader", "componentType": "file_loader", "category": "parser", "config": {"file_path": "./data/documents"}}},
                {"id": "n2", "type": "chunker", "position": {"x": 350, "y": 200}, "data": {"label": "Recursive Chunker", "componentType": "recursive_chunker", "category": "chunker", "config": {"chunk_size": 512, "chunk_overlap": 50}}},
                {"id": "n3", "type": "embedder", "position": {"x": 600, "y": 200}, "data": {"label": "OpenAI Embedder", "componentType": "openai_embedder", "category": "embedder", "config": {"model": "text-embedding-3-small"}}},
                {"id": "n4", "type": "indexer", "position": {"x": 850, "y": 200}, "data": {"label": "FAISS Indexer", "componentType": "faiss_indexer", "category": "indexer", "config": {"index_path": "./data/faiss_index"}}},
            ],
            "edges": [
                {"id": "e-n1-n2-0", "source": "n1", "target": "n2"},
                {"id": "e-n2-n3-0", "source": "n2", "target": "n3"},
                {"id": "e-n3-n4-0", "source": "n3", "target": "n4"},
            ],
        },
    },
    {
        "template_id": "rag_with_reranker",
        "name": "RAG + Reranker",
        "description": "Query pipeline with retrieval, reranking, and generation",
        "category": "query",
        "definition": {
            "nodes": [
                {"id": "n1", "type": "retriever", "position": {"x": 100, "y": 200}, "data": {"label": "Dense Retriever", "componentType": "dense_retriever", "category": "retriever", "config": {"top_k": 20}}},
                {"id": "n2", "type": "reranker", "position": {"x": 350, "y": 200}, "data": {"label": "Cross-Encoder Reranker", "componentType": "cross_encoder_reranker", "category": "reranker", "config": {"top_k": 5}}},
                {"id": "n3", "type": "generator", "position": {"x": 600, "y": 200}, "data": {"label": "LLM Generator", "componentType": "llm_generator", "category": "generator", "config": {"model": "gpt-4o-mini", "temperature": 0.7}}},
            ],
            "edges": [
                {"id": "e-n1-n2-0", "source": "n1", "target": "n2"},
                {"id": "e-n2-n3-0", "source": "n2", "target": "n3"},
            ],
        },
    },
    {
        "template_id": "knowledge_graph",
        "name": "Knowledge Graph Ingestion",
        "description": "LightRAG-style: parse, chunk, extract entities, build graph in Neo4j + embed into FAISS vector index",
        "category": "ingestion",
        "definition": {
            "nodes": [
                {"id": "n1", "type": "parser", "position": {"x": 100, "y": 200}, "data": {"label": "Multi-Format Parser", "componentType": "multi_parser", "category": "parser", "config": {"formats": ["pdf", "docx", "md", "txt"]}}},
                {"id": "n2", "type": "chunker", "position": {"x": 350, "y": 200}, "data": {"label": "Token Chunker", "componentType": "token_chunker", "category": "chunker", "config": {"chunk_token_size": 1200, "chunk_overlap_token_size": 100}}},
                {"id": "n3", "type": "extractor", "position": {"x": 600, "y": 100}, "data": {"label": "Entity Extractor", "componentType": "entity_extractor", "category": "extractor", "config": {"llm_model": "gpt-4o-mini", "entity_types": ["Person", "Organization", "Location", "Concept"]}}},
                {"id": "n4", "type": "embedder", "position": {"x": 600, "y": 320}, "data": {"label": "OpenAI Embedder", "componentType": "openai_embedder", "category": "embedder", "config": {"model": "text-embedding-3-small"}}},
                {"id": "n5", "type": "graph_builder", "position": {"x": 850, "y": 100}, "data": {"label": "LightRAG Graph Builder", "componentType": "lightrag_graph_builder", "category": "graph_builder", "config": {"merge_strategy": "merge_descriptions"}}},
                {"id": "n6", "type": "storage", "position": {"x": 1100, "y": 100}, "data": {"label": "Graph Store (Neo4j)", "componentType": "graph_store", "category": "storage", "config": {"uri": "bolt://localhost:7687"}}},
                {"id": "n7", "type": "indexer", "position": {"x": 850, "y": 320}, "data": {"label": "FAISS Indexer", "componentType": "faiss_indexer", "category": "indexer", "config": {"index_path": "/data/documents/faiss_index"}}},
            ],
            "edges": [
                {"id": "e-n1-n2-0", "source": "n1", "target": "n2"},
                {"id": "e-n2-n3-0", "source": "n2", "target": "n3"},
                {"id": "e-n2-n4-0", "source": "n2", "target": "n4"},
                {"id": "e-n3-n5-0", "source": "n3", "target": "n5"},
                {"id": "e-n5-n6-0", "source": "n5", "target": "n6"},
                {"id": "e-n4-n7-0", "source": "n4", "target": "n7"},
            ],
        },
    },
    {
        "template_id": "agentic_rag",
        "name": "Agentic RAG",
        "description": "Full agentic pipeline: route, decompose, retrieve, rerank, generate with reflection",
        "category": "query",
        "definition": {
            "nodes": [
                {"id": "n1", "type": "agent", "position": {"x": 100, "y": 200}, "data": {"label": "Query Router", "componentType": "query_router", "category": "agent", "config": {"llm_model": "gpt-4o-mini"}}},
                {"id": "n2", "type": "extractor", "position": {"x": 350, "y": 200}, "data": {"label": "Subquery Decomposer", "componentType": "subquery_decomposer", "category": "extractor", "config": {"max_hops": 3}}},
                {"id": "n3", "type": "retriever", "position": {"x": 600, "y": 200}, "data": {"label": "Dense Retriever", "componentType": "dense_retriever", "category": "retriever", "config": {"top_k": 20}}},
                {"id": "n4", "type": "reranker", "position": {"x": 850, "y": 200}, "data": {"label": "Cross-Encoder Reranker", "componentType": "cross_encoder_reranker", "category": "reranker", "config": {"top_k": 10}}},
                {"id": "n5", "type": "generator", "position": {"x": 1100, "y": 200}, "data": {"label": "LLM Generator", "componentType": "llm_generator", "category": "generator", "config": {"model": "gpt-4o-mini", "temperature": 0.7}}},
                {"id": "n6", "type": "agent", "position": {"x": 1350, "y": 200}, "data": {"label": "Reflection Agent", "componentType": "reflection_agent", "category": "agent", "config": {"min_score_threshold": 6.0}}},
                {"id": "n7", "type": "agent", "position": {"x": 1350, "y": 380}, "data": {"label": "Conversation Memory", "componentType": "memory_agent", "category": "agent", "config": {"max_history": 20}}},
            ],
            "edges": [
                {"id": "e-n1-n2-0", "source": "n1", "target": "n2"},
                {"id": "e-n2-n3-0", "source": "n2", "target": "n3"},
                {"id": "e-n3-n4-0", "source": "n3", "target": "n4"},
                {"id": "e-n4-n5-0", "source": "n4", "target": "n5"},
                {"id": "e-n5-n6-0", "source": "n5", "target": "n6"},
                {"id": "e-n5-n7-0", "source": "n5", "target": "n7"},
            ],
        },
    },
    {
        "template_id": "kag_three_layer",
        "name": "KAG Three-Layer Ingestion",
        "description": "KAG-style: semantic chunking, schema-free + schema-constrained extraction, subgraph in Neo4j + FAISS vector index",
        "category": "ingestion",
        "definition": {
            "nodes": [
                {"id": "n1", "type": "parser", "position": {"x": 100, "y": 200}, "data": {"label": "File Loader", "componentType": "file_loader", "category": "parser", "config": {}}},
                {"id": "n2", "type": "chunker", "position": {"x": 350, "y": 200}, "data": {"label": "Semantic Chunker", "componentType": "semantic_chunker", "category": "chunker", "config": {"max_chunk_size": 500}}},
                {"id": "n3", "type": "extractor", "position": {"x": 600, "y": 100}, "data": {"label": "Schema-Free Extractor", "componentType": "schema_free_extractor", "category": "extractor", "config": {"llm_model": "gpt-4o-mini"}}},
                {"id": "n4", "type": "extractor", "position": {"x": 600, "y": 300}, "data": {"label": "Schema-Constrained Extractor", "componentType": "schema_constrained_extractor", "category": "extractor", "config": {"llm_model": "gpt-4o-mini"}}},
                {"id": "n5", "type": "graph_builder", "position": {"x": 850, "y": 200}, "data": {"label": "KAG Subgraph Builder", "componentType": "kag_subgraph_builder", "category": "graph_builder", "config": {"add_chunk_links": True}}},
                {"id": "n6", "type": "storage", "position": {"x": 1100, "y": 100}, "data": {"label": "Graph Store (Neo4j)", "componentType": "graph_store", "category": "storage", "config": {"uri": "bolt://localhost:7687"}}},
                {"id": "n7", "type": "embedder", "position": {"x": 1100, "y": 300}, "data": {"label": "OpenAI Embedder", "componentType": "openai_embedder", "category": "embedder", "config": {"model": "text-embedding-3-small"}}},
                {"id": "n8", "type": "indexer", "position": {"x": 1350, "y": 300}, "data": {"label": "FAISS Indexer", "componentType": "faiss_indexer", "category": "indexer", "config": {"index_path": "/data/documents/faiss_index"}}},
            ],
            "edges": [
                {"id": "e-n1-n2-0", "source": "n1", "target": "n2"},
                {"id": "e-n2-n3-0", "source": "n2", "target": "n3"},
                {"id": "e-n2-n4-0", "source": "n2", "target": "n4"},
                {"id": "e-n3-n5-0", "source": "n3", "target": "n5"},
                {"id": "e-n4-n5-0", "source": "n4", "target": "n5"},
                {"id": "e-n5-n6-0", "source": "n5", "target": "n6"},
                {"id": "e-n5-n7-0", "source": "n5", "target": "n7"},
                {"id": "e-n7-n8-0", "source": "n7", "target": "n8"},
            ],
        },
    },
    {
        "template_id": "deep_research",
        "name": "Deep Research Pipeline",
        "description": "CoRAG-style iterative multi-hop retrieval with planning for complex research queries",
        "category": "query",
        "definition": {
            "nodes": [
                {"id": "n1", "type": "planner", "position": {"x": 100, "y": 200}, "data": {"label": "CoRAG Planner", "componentType": "corag_planner", "category": "planner", "config": {"strategy": "tree_search", "max_hops": 5}}},
                {"id": "n2", "type": "extractor", "position": {"x": 350, "y": 200}, "data": {"label": "Subquery Decomposer", "componentType": "subquery_decomposer", "category": "extractor", "config": {"max_hops": 5}}},
                {"id": "n3", "type": "retriever", "position": {"x": 600, "y": 100}, "data": {"label": "Dense Retriever", "componentType": "dense_retriever", "category": "retriever", "config": {"top_k": 30}}},
                {"id": "n4", "type": "retriever", "position": {"x": 600, "y": 300}, "data": {"label": "Web Retriever", "componentType": "web_retriever", "category": "retriever", "config": {"max_results": 5}}},
                {"id": "n5", "type": "reranker", "position": {"x": 850, "y": 200}, "data": {"label": "Cross-Encoder Reranker", "componentType": "cross_encoder_reranker", "category": "reranker", "config": {"top_k": 15}}},
                {"id": "n6", "type": "generator", "position": {"x": 1100, "y": 200}, "data": {"label": "LLM Generator", "componentType": "llm_generator", "category": "generator", "config": {"model": "gpt-4o", "max_tokens": 4096}}},
            ],
            "edges": [
                {"id": "e-n1-n2-0", "source": "n1", "target": "n2"},
                {"id": "e-n2-n3-0", "source": "n2", "target": "n3"},
                {"id": "e-n2-n4-0", "source": "n2", "target": "n4"},
                {"id": "e-n3-n5-0", "source": "n3", "target": "n5"},
                {"id": "e-n4-n5-0", "source": "n4", "target": "n5"},
                {"id": "e-n5-n6-0", "source": "n5", "target": "n6"},
            ],
        },
    },
    # End-to-end templates
    {
        "template_id": "e2e_vanilla_rag",
        "name": "End-to-End RAG",
        "description": "Complete ingestion-to-answer pipeline: parse, chunk, embed, index, then retrieve, rerank, and generate",
        "category": "full",
        "definition": {
            "nodes": [
                {"id": "i1", "type": "parser", "position": {"x": 100, "y": 100}, "data": {"label": "File Loader", "componentType": "file_loader", "category": "parser", "config": {"file_path": "./data/documents"}}},
                {"id": "i2", "type": "chunker", "position": {"x": 350, "y": 100}, "data": {"label": "Recursive Chunker", "componentType": "recursive_chunker", "category": "chunker", "config": {"chunk_size": 512, "chunk_overlap": 50}}},
                {"id": "i3", "type": "embedder", "position": {"x": 600, "y": 100}, "data": {"label": "OpenAI Embedder", "componentType": "openai_embedder", "category": "embedder", "config": {"model": "text-embedding-3-small"}}},
                {"id": "i4", "type": "indexer", "position": {"x": 850, "y": 100}, "data": {"label": "FAISS Indexer", "componentType": "faiss_indexer", "category": "indexer", "config": {"index_path": "./data/faiss_index"}}},
                {"id": "q1", "type": "retriever", "position": {"x": 850, "y": 350}, "data": {"label": "Dense Retriever", "componentType": "dense_retriever", "category": "retriever", "config": {"top_k": 20}}},
                {"id": "q2", "type": "reranker", "position": {"x": 1100, "y": 350}, "data": {"label": "Cross-Encoder Reranker", "componentType": "cross_encoder_reranker", "category": "reranker", "config": {"top_k": 5}}},
                {"id": "q3", "type": "generator", "position": {"x": 1350, "y": 350}, "data": {"label": "LLM Generator", "componentType": "llm_generator", "category": "generator", "config": {"model": "gpt-4o-mini", "temperature": 0.7}}},
            ],
            "edges": [
                {"id": "e-i1-i2-0", "source": "i1", "target": "i2"},
                {"id": "e-i2-i3-0", "source": "i2", "target": "i3"},
                {"id": "e-i3-i4-0", "source": "i3", "target": "i4"},
                {"id": "e-i4-q1-0", "source": "i4", "target": "q1"},
                {"id": "e-q1-q2-0", "source": "q1", "target": "q2"},
                {"id": "e-q2-q3-0", "source": "q2", "target": "q3"},
            ],
        },
    },
    {
        "template_id": "e2e_hybrid_search",
        "name": "Hybrid Search RAG",
        "description": "End-to-end with dual vector + keyword indexing, reciprocal rank fusion, reranking, and generation",
        "category": "full",
        "definition": {
            "nodes": [
                {"id": "i1", "type": "parser", "position": {"x": 100, "y": 200}, "data": {"label": "Multi-Format Parser", "componentType": "multi_parser", "category": "parser", "config": {"formats": ["pdf", "docx", "md", "txt"]}}},
                {"id": "i2", "type": "chunker", "position": {"x": 350, "y": 200}, "data": {"label": "Recursive Chunker", "componentType": "recursive_chunker", "category": "chunker", "config": {"chunk_size": 512, "chunk_overlap": 50}}},
                {"id": "i3", "type": "embedder", "position": {"x": 600, "y": 100}, "data": {"label": "OpenAI Embedder", "componentType": "openai_embedder", "category": "embedder", "config": {"model": "text-embedding-3-small"}}},
                {"id": "i4", "type": "indexer", "position": {"x": 850, "y": 100}, "data": {"label": "FAISS Indexer", "componentType": "faiss_indexer", "category": "indexer", "config": {"index_path": "./data/faiss_index"}}},
                {"id": "i5", "type": "indexer", "position": {"x": 850, "y": 300}, "data": {"label": "BM25 Indexer", "componentType": "bm25_indexer", "category": "indexer", "config": {"k1": 1.2, "b": 0.75}}},
                {"id": "q1", "type": "retriever", "position": {"x": 1100, "y": 100}, "data": {"label": "Dense Retriever", "componentType": "dense_retriever", "category": "retriever", "config": {"top_k": 30}}},
                {"id": "q2", "type": "retriever", "position": {"x": 1100, "y": 300}, "data": {"label": "BM25 Retriever", "componentType": "bm25_retriever", "category": "retriever", "config": {"top_k": 30}}},
                {"id": "q3", "type": "reranker", "position": {"x": 1350, "y": 200}, "data": {"label": "RRF Fusion", "componentType": "rrf_fusion", "category": "reranker", "config": {"k": 60, "top_k": 20}}},
                {"id": "q4", "type": "reranker", "position": {"x": 1600, "y": 200}, "data": {"label": "Cross-Encoder Reranker", "componentType": "cross_encoder_reranker", "category": "reranker", "config": {"top_k": 5}}},
                {"id": "q5", "type": "generator", "position": {"x": 1850, "y": 200}, "data": {"label": "LLM Generator", "componentType": "llm_generator", "category": "generator", "config": {"model": "gpt-4o-mini", "temperature": 0.7}}},
            ],
            "edges": [
                {"id": "e-i1-i2-0", "source": "i1", "target": "i2"},
                {"id": "e-i2-i3-0", "source": "i2", "target": "i3"},
                {"id": "e-i2-i5-0", "source": "i2", "target": "i5"},
                {"id": "e-i3-i4-0", "source": "i3", "target": "i4"},
                {"id": "e-i4-q1-0", "source": "i4", "target": "q1"},
                {"id": "e-i5-q2-0", "source": "i5", "target": "q2"},
                {"id": "e-q1-q3-0", "source": "q1", "target": "q3"},
                {"id": "e-q2-q3-0", "source": "q2", "target": "q3"},
                {"id": "e-q3-q4-0", "source": "q3", "target": "q4"},
                {"id": "e-q4-q5-0", "source": "q4", "target": "q5"},
            ],
        },
    },
    {
        "template_id": "e2e_graphrag",
        "name": "GraphRAG End-to-End",
        "description": "Full knowledge-graph pipeline: ingest into Neo4j + vector store, then query with graph traversal + dense retrieval",
        "category": "full",
        "definition": {
            "nodes": [
                {"id": "i1", "type": "parser", "position": {"x": 100, "y": 200}, "data": {"label": "Multi-Format Parser", "componentType": "multi_parser", "category": "parser", "config": {"formats": ["pdf", "docx", "md", "txt"]}}},
                {"id": "i2", "type": "chunker", "position": {"x": 350, "y": 200}, "data": {"label": "Token Chunker", "componentType": "token_chunker", "category": "chunker", "config": {"chunk_token_size": 1200, "chunk_overlap_token_size": 100}}},
                {"id": "i3", "type": "extractor", "position": {"x": 600, "y": 100}, "data": {"label": "Entity Extractor", "componentType": "entity_extractor", "category": "extractor", "config": {"llm_model": "gpt-4o-mini", "entity_types": ["Person", "Organization", "Location", "Concept", "Event"]}}},
                {"id": "i4", "type": "embedder", "position": {"x": 600, "y": 320}, "data": {"label": "OpenAI Embedder", "componentType": "openai_embedder", "category": "embedder", "config": {"model": "text-embedding-3-small"}}},
                {"id": "i5", "type": "graph_builder", "position": {"x": 850, "y": 100}, "data": {"label": "LightRAG Graph Builder", "componentType": "lightrag_graph_builder", "category": "graph_builder", "config": {"merge_strategy": "merge_descriptions"}}},
                {"id": "i6", "type": "storage", "position": {"x": 1100, "y": 100}, "data": {"label": "Graph Store (Neo4j)", "componentType": "graph_store", "category": "storage", "config": {"uri": "bolt://localhost:7687"}}},
                {"id": "i7", "type": "indexer", "position": {"x": 850, "y": 320}, "data": {"label": "FAISS Indexer", "componentType": "faiss_indexer", "category": "indexer", "config": {"index_path": "./data/faiss_index"}}},
                {"id": "q1", "type": "retriever", "position": {"x": 1350, "y": 100}, "data": {"label": "Graph Retriever", "componentType": "graph_retriever", "category": "retriever", "config": {"max_hops": 2, "top_k": 15}}},
                {"id": "q2", "type": "retriever", "position": {"x": 1350, "y": 320}, "data": {"label": "Dense Retriever", "componentType": "dense_retriever", "category": "retriever", "config": {"top_k": 20}}},
                {"id": "q3", "type": "reranker", "position": {"x": 1600, "y": 200}, "data": {"label": "Cross-Encoder Reranker", "componentType": "cross_encoder_reranker", "category": "reranker", "config": {"top_k": 10}}},
                {"id": "q4", "type": "generator", "position": {"x": 1850, "y": 200}, "data": {"label": "LLM Generator", "componentType": "llm_generator", "category": "generator", "config": {"model": "gpt-4o-mini", "temperature": 0.3}}},
            ],
            "edges": [
                {"id": "e-i1-i2-0", "source": "i1", "target": "i2"},
                {"id": "e-i2-i3-0", "source": "i2", "target": "i3"},
                {"id": "e-i2-i4-0", "source": "i2", "target": "i4"},
                {"id": "e-i3-i5-0", "source": "i3", "target": "i5"},
                {"id": "e-i5-i6-0", "source": "i5", "target": "i6"},
                {"id": "e-i4-i7-0", "source": "i4", "target": "i7"},
                {"id": "e-i6-q1-0", "source": "i6", "target": "q1"},
                {"id": "e-i7-q2-0", "source": "i7", "target": "q2"},
                {"id": "e-q1-q3-0", "source": "q1", "target": "q3"},
                {"id": "e-q2-q3-0", "source": "q2", "target": "q3"},
                {"id": "e-q3-q4-0", "source": "q3", "target": "q4"},
            ],
        },
    },
    {
        "template_id": "e2e_agentic_rag",
        "name": "Agentic RAG End-to-End",
        "description": "Full ingest-to-answer agentic pipeline with routing, multi-hop decomposition, retrieval, reflection, and memory",
        "category": "full",
        "definition": {
            "nodes": [
                {"id": "i1", "type": "parser", "position": {"x": 100, "y": 80}, "data": {"label": "Multi-Format Parser", "componentType": "multi_parser", "category": "parser", "config": {"formats": ["pdf", "docx", "md", "txt"]}}},
                {"id": "i2", "type": "chunker", "position": {"x": 350, "y": 80}, "data": {"label": "Semantic Chunker", "componentType": "semantic_chunker", "category": "chunker", "config": {"max_chunk_size": 500}}},
                {"id": "i3", "type": "embedder", "position": {"x": 600, "y": 80}, "data": {"label": "OpenAI Embedder", "componentType": "openai_embedder", "category": "embedder", "config": {"model": "text-embedding-3-small"}}},
                {"id": "i4", "type": "indexer", "position": {"x": 850, "y": 80}, "data": {"label": "FAISS Indexer", "componentType": "faiss_indexer", "category": "indexer", "config": {"index_path": "./data/faiss_index"}}},
                {"id": "q1", "type": "agent", "position": {"x": 100, "y": 320}, "data": {"label": "Query Router", "componentType": "query_router", "category": "agent", "config": {"llm_model": "gpt-4o-mini"}}},
                {"id": "q2", "type": "extractor", "position": {"x": 350, "y": 320}, "data": {"label": "Subquery Decomposer", "componentType": "subquery_decomposer", "category": "extractor", "config": {"max_hops": 3}}},
                {"id": "q3", "type": "retriever", "position": {"x": 600, "y": 320}, "data": {"label": "Dense Retriever", "componentType": "dense_retriever", "category": "retriever", "config": {"top_k": 20}}},
                {"id": "q4", "type": "reranker", "position": {"x": 850, "y": 320}, "data": {"label": "Cross-Encoder Reranker", "componentType": "cross_encoder_reranker", "category": "reranker", "config": {"top_k": 10}}},
                {"id": "q5", "type": "generator", "position": {"x": 1100, "y": 320}, "data": {"label": "LLM Generator", "componentType": "llm_generator", "category": "generator", "config": {"model": "gpt-4o-mini", "temperature": 0.7}}},
                {"id": "q6", "type": "agent", "position": {"x": 1350, "y": 260}, "data": {"label": "Reflection Agent", "componentType": "reflection_agent", "category": "agent", "config": {"min_score_threshold": 6.0}}},
                {"id": "q7", "type": "agent", "position": {"x": 1350, "y": 400}, "data": {"label": "Conversation Memory", "componentType": "memory_agent", "category": "agent", "config": {"max_history": 20}}},
            ],
            "edges": [
                {"id": "e-i1-i2-0", "source": "i1", "target": "i2"},
                {"id": "e-i2-i3-0", "source": "i2", "target": "i3"},
                {"id": "e-i3-i4-0", "source": "i3", "target": "i4"},
                {"id": "e-i4-q3-0", "source": "i4", "target": "q3"},
                {"id": "e-q1-q2-0", "source": "q1", "target": "q2"},
                {"id": "e-q2-q3-0", "source": "q2", "target": "q3"},
                {"id": "e-q3-q4-0", "source": "q3", "target": "q4"},
                {"id": "e-q4-q5-0", "source": "q4", "target": "q5"},
                {"id": "e-q5-q6-0", "source": "q5", "target": "q6"},
                {"id": "e-q5-q7-0", "source": "q5", "target": "q7"},
            ],
        },
    },
    {
        "template_id": "parent_child_chunking",
        "name": "Parent-Child Chunking",
        "description": "Hierarchical chunking: large parent chunks for context, small child chunks for precise retrieval",
        "category": "ingestion",
        "definition": {
            "nodes": [
                {"id": "n1", "type": "parser", "position": {"x": 100, "y": 200}, "data": {"label": "File Loader", "componentType": "file_loader", "category": "parser", "config": {"file_path": "./data/documents"}}},
                {"id": "n2", "type": "chunker", "position": {"x": 350, "y": 100}, "data": {"label": "Parent Chunker", "componentType": "recursive_chunker", "category": "chunker", "config": {"chunk_size": 2048, "chunk_overlap": 200}}},
                {"id": "n3", "type": "chunker", "position": {"x": 600, "y": 100}, "data": {"label": "Child Chunker", "componentType": "recursive_chunker", "category": "chunker", "config": {"chunk_size": 256, "chunk_overlap": 30}}},
                {"id": "n4", "type": "embedder", "position": {"x": 850, "y": 100}, "data": {"label": "OpenAI Embedder", "componentType": "openai_embedder", "category": "embedder", "config": {"model": "text-embedding-3-small"}}},
                {"id": "n5", "type": "indexer", "position": {"x": 1100, "y": 100}, "data": {"label": "Child Index", "componentType": "faiss_indexer", "category": "indexer", "config": {"index_path": "./data/child_index"}}},
                {"id": "n6", "type": "storage", "position": {"x": 600, "y": 300}, "data": {"label": "Parent Doc Store", "componentType": "doc_store", "category": "storage", "config": {"store_path": "./data/parent_store"}}},
            ],
            "edges": [
                {"id": "e-n1-n2-0", "source": "n1", "target": "n2"},
                {"id": "e-n2-n3-0", "source": "n2", "target": "n3"},
                {"id": "e-n2-n6-0", "source": "n2", "target": "n6"},
                {"id": "e-n3-n4-0", "source": "n3", "target": "n4"},
                {"id": "e-n4-n5-0", "source": "n4", "target": "n5"},
            ],
        },
    },
    {
        "template_id": "multimodal_ingestion",
        "name": "Multi-Modal Ingestion",
        "description": "Ingest text, tables, and images separately with specialized parsers, then embed and merge into a unified index",
        "category": "ingestion",
        "definition": {
            "nodes": [
                {"id": "n1", "type": "parser", "position": {"x": 100, "y": 80}, "data": {"label": "Text Parser", "componentType": "text_parser", "category": "parser", "config": {"formats": ["pdf", "docx", "md"]}}},
                {"id": "n2", "type": "parser", "position": {"x": 100, "y": 250}, "data": {"label": "Table Parser", "componentType": "table_parser", "category": "parser", "config": {"formats": ["csv", "xlsx"]}}},
                {"id": "n3", "type": "parser", "position": {"x": 100, "y": 420}, "data": {"label": "Image Parser", "componentType": "image_parser", "category": "parser", "config": {"ocr": True, "caption_model": "gpt-4o-mini"}}},
                {"id": "n4", "type": "chunker", "position": {"x": 350, "y": 80}, "data": {"label": "Text Chunker", "componentType": "recursive_chunker", "category": "chunker", "config": {"chunk_size": 512, "chunk_overlap": 50}}},
                {"id": "n5", "type": "chunker", "position": {"x": 350, "y": 250}, "data": {"label": "Table Chunker", "componentType": "row_chunker", "category": "chunker", "config": {"rows_per_chunk": 20}}},
                {"id": "n6", "type": "embedder", "position": {"x": 600, "y": 80}, "data": {"label": "Text Embedder", "componentType": "openai_embedder", "category": "embedder", "config": {"model": "text-embedding-3-small"}}},
                {"id": "n7", "type": "embedder", "position": {"x": 600, "y": 250}, "data": {"label": "Table Embedder", "componentType": "openai_embedder", "category": "embedder", "config": {"model": "text-embedding-3-small"}}},
                {"id": "n8", "type": "embedder", "position": {"x": 600, "y": 420}, "data": {"label": "Image Embedder", "componentType": "clip_embedder", "category": "embedder", "config": {"model": "clip-vit-large-patch14"}}},
                {"id": "n9", "type": "indexer", "position": {"x": 850, "y": 250}, "data": {"label": "Unified Index", "componentType": "faiss_indexer", "category": "indexer", "config": {"index_path": "./data/multimodal_index"}}},
            ],
            "edges": [
                {"id": "e-n1-n4-0", "source": "n1", "target": "n4"},
                {"id": "e-n2-n5-0", "source": "n2", "target": "n5"},
                {"id": "e-n3-n8-0", "source": "n3", "target": "n8"},
                {"id": "e-n4-n6-0", "source": "n4", "target": "n6"},
                {"id": "e-n5-n7-0", "source": "n5", "target": "n7"},
                {"id": "e-n6-n9-0", "source": "n6", "target": "n9"},
                {"id": "e-n7-n9-0", "source": "n7", "target": "n9"},
                {"id": "e-n8-n9-0", "source": "n8", "target": "n9"},
            ],
        },
    },
    {
        "template_id": "corrective_rag",
        "name": "Corrective RAG (CRAG)",
        "description": "Evaluates retrieval relevance -- if documents are relevant, generate; otherwise fall back to web search",
        "category": "query",
        "definition": {
            "nodes": [
                {"id": "n1", "type": "retriever", "position": {"x": 100, "y": 200}, "data": {"label": "Dense Retriever", "componentType": "dense_retriever", "category": "retriever", "config": {"top_k": 15}}},
                {"id": "n2", "type": "agent", "position": {"x": 350, "y": 200}, "data": {"label": "Relevance Evaluator", "componentType": "relevance_evaluator", "category": "agent", "config": {"llm_model": "gpt-4o-mini", "threshold": 0.6}}},
                {"id": "n3", "type": "retriever", "position": {"x": 600, "y": 320}, "data": {"label": "Web Search Fallback", "componentType": "web_retriever", "category": "retriever", "config": {"max_results": 5}}},
                {"id": "n4", "type": "reranker", "position": {"x": 850, "y": 200}, "data": {"label": "Cross-Encoder Reranker", "componentType": "cross_encoder_reranker", "category": "reranker", "config": {"top_k": 5}}},
                {"id": "n5", "type": "generator", "position": {"x": 1100, "y": 200}, "data": {"label": "LLM Generator", "componentType": "llm_generator", "category": "generator", "config": {"model": "gpt-4o-mini", "temperature": 0.5}}},
            ],
            "edges": [
                {"id": "e-n1-n2-0", "source": "n1", "target": "n2"},
                {"id": "e-n2-n4-0", "source": "n2", "target": "n4"},
                {"id": "e-n2-n3-0", "source": "n2", "target": "n3"},
                {"id": "e-n3-n4-0", "source": "n3", "target": "n4"},
                {"id": "e-n4-n5-0", "source": "n4", "target": "n5"},
            ],
        },
    },
    {
        "template_id": "self_rag",
        "name": "Self-RAG",
        "description": "Retrieve, generate, then self-critique the answer -- loops back for re-retrieval if quality is insufficient",
        "category": "query",
        "definition": {
            "nodes": [
                {"id": "n1", "type": "retriever", "position": {"x": 100, "y": 200}, "data": {"label": "Dense Retriever", "componentType": "dense_retriever", "category": "retriever", "config": {"top_k": 15}}},
                {"id": "n2", "type": "reranker", "position": {"x": 350, "y": 200}, "data": {"label": "Cross-Encoder Reranker", "componentType": "cross_encoder_reranker", "category": "reranker", "config": {"top_k": 5}}},
                {"id": "n3", "type": "generator", "position": {"x": 600, "y": 200}, "data": {"label": "LLM Generator", "componentType": "llm_generator", "category": "generator", "config": {"model": "gpt-4o-mini", "temperature": 0.7}}},
                {"id": "n4", "type": "agent", "position": {"x": 850, "y": 200}, "data": {"label": "Self-Critique Agent", "componentType": "self_critique_agent", "category": "agent", "config": {"llm_model": "gpt-4o-mini", "critique_dimensions": ["faithfulness", "relevance", "completeness"], "min_score": 7.0}}},
                {"id": "n5", "type": "agent", "position": {"x": 850, "y": 380}, "data": {"label": "Citation Annotator", "componentType": "citation_annotator", "category": "agent", "config": {"style": "inline"}}},
            ],
            "edges": [
                {"id": "e-n1-n2-0", "source": "n1", "target": "n2"},
                {"id": "e-n2-n3-0", "source": "n2", "target": "n3"},
                {"id": "e-n3-n4-0", "source": "n3", "target": "n4"},
                {"id": "e-n4-n1-0", "source": "n4", "target": "n1"},
                {"id": "e-n3-n5-0", "source": "n3", "target": "n5"},
            ],
        },
    },
    # ── NEW templates using research-backed components ──────────────────
    {
        "template_id": "deep_rag_reasoning",
        "name": "Deep RAG Reasoning",
        "description": "DeepRAG/AirRAG-style: interleaves retrieval within chain-of-thought reasoning steps for complex multi-hop questions",
        "category": "query",
        "definition": {
            "nodes": [
                {"id": "n1", "type": "agent", "position": {"x": 100, "y": 200}, "data": {"label": "Self-Cognition Gate", "componentType": "self_cognition_gate", "category": "agent", "config": {"confidence_threshold": 0.7}}},
                {"id": "n2", "type": "retriever", "position": {"x": 350, "y": 200}, "data": {"label": "Hybrid Retriever", "componentType": "hybrid_retriever", "category": "retriever", "config": {"top_k": 20, "alpha": 0.6}}},
                {"id": "n3", "type": "reranker", "position": {"x": 600, "y": 200}, "data": {"label": "Cross-Encoder Reranker", "componentType": "cross_encoder_reranker", "category": "reranker", "config": {"top_k": 10}}},
                {"id": "n4", "type": "agent", "position": {"x": 850, "y": 200}, "data": {"label": "Deep RAG Agent", "componentType": "deep_rag_agent", "category": "agent", "config": {"max_reasoning_steps": 8, "retrieval_trigger": "llm_decision"}}},
                {"id": "n5", "type": "agent", "position": {"x": 1100, "y": 200}, "data": {"label": "RAG Evaluator", "componentType": "rag_evaluator", "category": "agent", "config": {"metrics": ["faithfulness", "answer_relevance", "context_precision"]}}},
            ],
            "edges": [
                {"id": "e-n1-n2-0", "source": "n1", "target": "n2"},
                {"id": "e-n2-n3-0", "source": "n2", "target": "n3"},
                {"id": "e-n3-n4-0", "source": "n3", "target": "n4"},
                {"id": "e-n4-n5-0", "source": "n4", "target": "n5"},
            ],
        },
    },
    {
        "template_id": "speculative_rag",
        "name": "Speculative RAG",
        "description": "Draft multiple answers with small model, verify with large model. 2-3x faster with better accuracy",
        "category": "query",
        "definition": {
            "nodes": [
                {"id": "n1", "type": "retriever", "position": {"x": 100, "y": 200}, "data": {"label": "Dense Retriever", "componentType": "dense_retriever", "category": "retriever", "config": {"top_k": 20}}},
                {"id": "n2", "type": "reranker", "position": {"x": 350, "y": 200}, "data": {"label": "Context Compressor", "componentType": "context_compressor", "category": "reranker", "config": {"compression_method": "extractive", "target_ratio": 0.4}}},
                {"id": "n3", "type": "generator", "position": {"x": 600, "y": 200}, "data": {"label": "Speculative Generator", "componentType": "speculative_generator", "category": "generator", "config": {"draft_model": "gpt-4o-mini", "verify_model": "gpt-4o", "num_drafts": 3}}},
                {"id": "n4", "type": "agent", "position": {"x": 850, "y": 200}, "data": {"label": "RAG Evaluator", "componentType": "rag_evaluator", "category": "agent", "config": {"metrics": ["faithfulness", "answer_relevance"]}}},
            ],
            "edges": [
                {"id": "e-n1-n2-0", "source": "n1", "target": "n2"},
                {"id": "e-n2-n3-0", "source": "n2", "target": "n3"},
                {"id": "e-n3-n4-0", "source": "n3", "target": "n4"},
            ],
        },
    },
    {
        "template_id": "adaptive_retrieval",
        "name": "Adaptive Retrieval Pipeline",
        "description": "Stop-RAG: dynamically decides when enough context has been retrieved, reducing 40% of unnecessary retrievals",
        "category": "query",
        "definition": {
            "nodes": [
                {"id": "n1", "type": "agent", "position": {"x": 100, "y": 200}, "data": {"label": "Query Router", "componentType": "query_router", "category": "agent", "config": {"llm_model": "gpt-4o-mini", "routing_mode": "adaptive"}}},
                {"id": "n2", "type": "retriever", "position": {"x": 350, "y": 100}, "data": {"label": "Dense Retriever", "componentType": "dense_retriever", "category": "retriever", "config": {"top_k": 15}}},
                {"id": "n3", "type": "retriever", "position": {"x": 350, "y": 300}, "data": {"label": "Graph Retriever", "componentType": "graph_retriever", "category": "retriever", "config": {"top_k": 10, "graph_search_depth": 2}}},
                {"id": "n4", "type": "agent", "position": {"x": 600, "y": 200}, "data": {"label": "Adaptive Controller", "componentType": "adaptive_retrieval_controller", "category": "agent", "config": {"sufficiency_threshold": 0.75, "max_retrieval_rounds": 5}}},
                {"id": "n5", "type": "reranker", "position": {"x": 850, "y": 200}, "data": {"label": "Cross-Encoder Reranker", "componentType": "cross_encoder_reranker", "category": "reranker", "config": {"top_k": 8}}},
                {"id": "n6", "type": "generator", "position": {"x": 1100, "y": 200}, "data": {"label": "LLM Generator", "componentType": "llm_generator", "category": "generator", "config": {"model": "gpt-4o-mini", "temperature": 0.3}}},
            ],
            "edges": [
                {"id": "e-n1-n2-0", "source": "n1", "target": "n2"},
                {"id": "e-n1-n3-0", "source": "n1", "target": "n3"},
                {"id": "e-n2-n4-0", "source": "n2", "target": "n4"},
                {"id": "e-n3-n4-0", "source": "n3", "target": "n4"},
                {"id": "e-n4-n5-0", "source": "n4", "target": "n5"},
                {"id": "e-n5-n6-0", "source": "n5", "target": "n6"},
            ],
        },
    },
    {
        "template_id": "streaming_rag",
        "name": "Streaming RAG",
        "description": "RAPID-style progressive retrieval with streaming generation. 50% latency reduction for real-time applications",
        "category": "query",
        "definition": {
            "nodes": [
                {"id": "n1", "type": "retriever", "position": {"x": 100, "y": 200}, "data": {"label": "Streaming Retriever", "componentType": "streaming_retriever", "category": "retriever", "config": {"top_k": 20, "stream_batch_size": 5, "early_generation_threshold": 3}}},
                {"id": "n2", "type": "reranker", "position": {"x": 350, "y": 200}, "data": {"label": "Context Compressor", "componentType": "context_compressor", "category": "reranker", "config": {"compression_method": "extractive", "target_ratio": 0.5}}},
                {"id": "n3", "type": "generator", "position": {"x": 600, "y": 200}, "data": {"label": "LLM Generator", "componentType": "llm_generator", "category": "generator", "config": {"model": "gpt-4o-mini", "temperature": 0.3, "stream": True}}},
            ],
            "edges": [
                {"id": "e-n1-n2-0", "source": "n1", "target": "n2"},
                {"id": "e-n2-n3-0", "source": "n2", "target": "n3"},
            ],
        },
    },
    {
        "template_id": "table_qa",
        "name": "Table Question Answering",
        "description": "TableRAG: specialized pipeline for structured tabular data retrieval and question answering",
        "category": "query",
        "definition": {
            "nodes": [
                {"id": "n1", "type": "retriever", "position": {"x": 100, "y": 200}, "data": {"label": "Table Retriever", "componentType": "table_retriever", "category": "retriever", "config": {"top_k": 5, "schema_matching": "embedding", "cell_retrieval_enabled": True}}},
                {"id": "n2", "type": "reranker", "position": {"x": 350, "y": 200}, "data": {"label": "Cross-Encoder Reranker", "componentType": "cross_encoder_reranker", "category": "reranker", "config": {"top_k": 3}}},
                {"id": "n3", "type": "generator", "position": {"x": 600, "y": 200}, "data": {"label": "LLM Generator", "componentType": "llm_generator", "category": "generator", "config": {"model": "gpt-4o-mini", "temperature": 0.1, "enable_cot": True}}},
            ],
            "edges": [
                {"id": "e-n1-n2-0", "source": "n1", "target": "n2"},
                {"id": "e-n2-n3-0", "source": "n2", "target": "n3"},
            ],
        },
    },
    {
        "template_id": "vision_rag",
        "name": "Vision RAG",
        "description": "VisRAG/ColPali: embed document pages as images and answer questions using vision-language models",
        "category": "full",
        "definition": {
            "nodes": [
                {"id": "i1", "type": "parser", "position": {"x": 100, "y": 100}, "data": {"label": "File Loader", "componentType": "file_loader", "category": "parser", "config": {"file_path": "./data/documents"}}},
                {"id": "i2", "type": "embedder", "position": {"x": 350, "y": 100}, "data": {"label": "Multimodal Embedder", "componentType": "multimodal_embedder", "category": "embedder", "config": {"model_name": "vidore/colpali-v1.3", "embedding_mode": "late_interaction"}}},
                {"id": "i3", "type": "indexer", "position": {"x": 600, "y": 100}, "data": {"label": "FAISS Indexer", "componentType": "faiss_indexer", "category": "indexer", "config": {"index_path": "./data/vision_index"}}},
                {"id": "q1", "type": "retriever", "position": {"x": 600, "y": 350}, "data": {"label": "Dense Retriever", "componentType": "dense_retriever", "category": "retriever", "config": {"top_k": 10}}},
                {"id": "q2", "type": "generator", "position": {"x": 850, "y": 350}, "data": {"label": "Vision Generator", "componentType": "vision_generator", "category": "generator", "config": {"model": "gpt-4o", "max_images": 5}}},
            ],
            "edges": [
                {"id": "e-i1-i2-0", "source": "i1", "target": "i2"},
                {"id": "e-i2-i3-0", "source": "i2", "target": "i3"},
                {"id": "e-i3-q1-0", "source": "i3", "target": "q1"},
                {"id": "e-q1-q2-0", "source": "q1", "target": "q2"},
            ],
        },
    },
    {
        "template_id": "mcts_deep_research",
        "name": "MCTS Deep Research",
        "description": "Monte Carlo Tree Search planning with iterative multi-hop retrieval for complex research questions",
        "category": "query",
        "definition": {
            "nodes": [
                {"id": "n1", "type": "planner", "position": {"x": 100, "y": 200}, "data": {"label": "MCTS Planner", "componentType": "mcts_planner", "category": "planner", "config": {"mcts_simulations": 100, "max_depth": 5}}},
                {"id": "n2", "type": "extractor", "position": {"x": 350, "y": 200}, "data": {"label": "Subquery Decomposer", "componentType": "subquery_decomposer", "category": "extractor", "config": {"max_hops": 5}}},
                {"id": "n3", "type": "retriever", "position": {"x": 600, "y": 100}, "data": {"label": "Hybrid Retriever", "componentType": "hybrid_retriever", "category": "retriever", "config": {"top_k": 30, "alpha": 0.6}}},
                {"id": "n4", "type": "retriever", "position": {"x": 600, "y": 300}, "data": {"label": "Web Retriever", "componentType": "web_retriever", "category": "retriever", "config": {"max_results": 10}}},
                {"id": "n5", "type": "reranker", "position": {"x": 850, "y": 200}, "data": {"label": "LLM Listwise Reranker", "componentType": "llm_listwise_reranker", "category": "reranker", "config": {"top_k": 15, "window_size": 20}}},
                {"id": "n6", "type": "reranker", "position": {"x": 1100, "y": 200}, "data": {"label": "Context Compressor", "componentType": "context_compressor", "category": "reranker", "config": {"target_ratio": 0.4}}},
                {"id": "n7", "type": "generator", "position": {"x": 1350, "y": 200}, "data": {"label": "LLM Generator", "componentType": "llm_generator", "category": "generator", "config": {"model": "gpt-4o", "max_tokens": 4096, "enable_cot": True}}},
            ],
            "edges": [
                {"id": "e-n1-n2-0", "source": "n1", "target": "n2"},
                {"id": "e-n2-n3-0", "source": "n2", "target": "n3"},
                {"id": "e-n2-n4-0", "source": "n2", "target": "n4"},
                {"id": "e-n3-n5-0", "source": "n3", "target": "n5"},
                {"id": "e-n4-n5-0", "source": "n4", "target": "n5"},
                {"id": "e-n5-n6-0", "source": "n5", "target": "n6"},
                {"id": "e-n6-n7-0", "source": "n6", "target": "n7"},
            ],
        },
    },
    {
        "template_id": "contextual_ingestion",
        "name": "Contextual Ingestion",
        "description": "Anthropic-style contextual retrieval: prepend LLM-generated context to each chunk. -49% retrieval failures",
        "category": "ingestion",
        "definition": {
            "nodes": [
                {"id": "n1", "type": "parser", "position": {"x": 100, "y": 200}, "data": {"label": "Multi-Format Parser", "componentType": "multi_parser", "category": "parser", "config": {"formats": ["pdf", "docx", "md", "txt"]}}},
                {"id": "n2", "type": "chunker", "position": {"x": 350, "y": 200}, "data": {"label": "Contextual Chunker", "componentType": "contextual_chunker", "category": "chunker", "config": {"chunk_size": 512, "context_model": "gpt-4o-mini"}}},
                {"id": "n3", "type": "embedder", "position": {"x": 600, "y": 200}, "data": {"label": "OpenAI Embedder", "componentType": "openai_embedder", "category": "embedder", "config": {"model": "text-embedding-3-small"}}},
                {"id": "n4", "type": "indexer", "position": {"x": 850, "y": 200}, "data": {"label": "FAISS Indexer", "componentType": "faiss_indexer", "category": "indexer", "config": {"index_path": "./data/contextual_index"}}},
            ],
            "edges": [
                {"id": "e-n1-n2-0", "source": "n1", "target": "n2"},
                {"id": "e-n2-n3-0", "source": "n2", "target": "n3"},
                {"id": "e-n3-n4-0", "source": "n3", "target": "n4"},
            ],
        },
    },
    {
        "template_id": "proposition_ingestion",
        "name": "Proposition-Based Ingestion",
        "description": "Dense X: decompose text into atomic propositions for higher recall (+10 Recall@20). Best for precise retrieval",
        "category": "ingestion",
        "definition": {
            "nodes": [
                {"id": "n1", "type": "parser", "position": {"x": 100, "y": 200}, "data": {"label": "File Loader", "componentType": "file_loader", "category": "parser", "config": {"file_path": "./data/documents"}}},
                {"id": "n2", "type": "chunker", "position": {"x": 350, "y": 200}, "data": {"label": "Proposition Chunker", "componentType": "proposition_chunker", "category": "chunker", "config": {"proposition_model": "gpt-4o-mini", "decontextualize": True}}},
                {"id": "n3", "type": "embedder", "position": {"x": 600, "y": 200}, "data": {"label": "OpenAI Embedder", "componentType": "openai_embedder", "category": "embedder", "config": {"model": "text-embedding-3-small"}}},
                {"id": "n4", "type": "indexer", "position": {"x": 850, "y": 200}, "data": {"label": "FAISS Indexer", "componentType": "faiss_indexer", "category": "indexer", "config": {"index_path": "./data/proposition_index"}}},
            ],
            "edges": [
                {"id": "e-n1-n2-0", "source": "n1", "target": "n2"},
                {"id": "e-n2-n3-0", "source": "n2", "target": "n3"},
                {"id": "e-n3-n4-0", "source": "n3", "target": "n4"},
            ],
        },
    },
    # ── Composite component templates ─────────────────────────────────
    {
        "template_id": "lightrag_ingestion_composite",
        "name": "LightRAG Ingestion Pipeline",
        "description": "Complete ingestion using the LightRAG Ingestion composite component: load files, then chunk, extract entities, merge, and persist to Neo4j + Qdrant + Redis in one step",
        "category": "ingestion",
        "definition": {
            "nodes": [
                {"id": "n1", "type": "parser", "position": {"x": 100, "y": 200}, "data": {"label": "File Loader", "componentType": "file_loader", "category": "parser", "config": {"file_path": "./data/documents"}}},
                {
                    "id": "n2", "type": "graph_builder", "position": {"x": 450, "y": 200},
                    "data": {
                        "label": "LightRAG Ingestion",
                        "componentType": "lightrag_ingestion",
                        "category": "graph_builder",
                        "is_composite": True,
                        "config": {
                            "scope": "ws_default_ds_1",
                            "chunk_size": 1200,
                            "chunk_overlap": 100,
                            "extraction_model": "gpt-4o-mini",
                            "embedding_model": "text-embedding-3-small",
                        },
                        "steps": [
                            {"order": 1, "name": "Chunk Documents", "description": "Split documents into token-sized chunks"},
                            {"order": 2, "name": "Extract Entities And Relations", "description": "LLM-based entity and relation extraction with gleaning"},
                            {"order": 3, "name": "Merge And Deduplicate", "description": "Merge duplicate entities and relations"},
                            {"order": 4, "name": "Store To Graph", "description": "Persist entities and relations in Neo4j"},
                            {"order": 5, "name": "Store Vectors And KV", "description": "Persist embeddings in Qdrant and raw data in Redis"},
                        ],
                    },
                },
            ],
            "edges": [
                {"id": "e-n1-n2-0", "source": "n1", "target": "n2"},
            ],
        },
    },
    {
        "template_id": "lightrag_query_composite",
        "name": "LightRAG Query Pipeline",
        "description": "Single-node query pipeline using the LightRAG Retrieval composite: extracts keywords, searches graph + vectors, assembles context, and generates a grounded answer",
        "category": "query",
        "definition": {
            "nodes": [
                {
                    "id": "n1", "type": "retriever", "position": {"x": 300, "y": 200},
                    "data": {
                        "label": "LightRAG Retrieval",
                        "componentType": "lightrag_retrieval",
                        "category": "retriever",
                        "is_composite": True,
                        "config": {
                            "scope": "ws_default_ds_1",
                            "mode": "mix",
                            "top_k": 10,
                            "generation_model": "gpt-4o-mini",
                            "embedding_model": "text-embedding-3-small",
                        },
                        "steps": [
                            {"order": 1, "name": "Extract Keywords", "description": "Extract high/low level keywords from query via LLM"},
                            {"order": 2, "name": "Search Knowledge Graph", "description": "Search entities and relations via Neo4j and Qdrant"},
                            {"order": 3, "name": "Search Vectors", "description": "Direct vector search on document chunks"},
                            {"order": 4, "name": "Assemble Context", "description": "Build token-budgeted context from graph and vector results"},
                            {"order": 5, "name": "Generate Answer", "description": "Generate the final answer using LLM and assembled context"},
                        ],
                    },
                },
            ],
            "edges": [],
        },
    },
    {
        "template_id": "agentic_rag_query_composite",
        "name": "Agentic RAG Query Pipeline",
        "description": "Single-node agentic query pipeline: analyzes query, plans retrieval strategy, executes tools, evaluates evidence sufficiency, and iterates until a comprehensive answer is generated",
        "category": "query",
        "definition": {
            "nodes": [
                {
                    "id": "n1", "type": "agent", "position": {"x": 300, "y": 200},
                    "data": {
                        "label": "Agentic RAG Retrieval",
                        "componentType": "agentic_rag_retrieval",
                        "category": "agent",
                        "is_composite": True,
                        "config": {
                            "scope": "ws_default_ds_1",
                            "max_iterations": 3,
                            "generation_model": "gpt-4o-mini",
                            "planning_model": "gpt-4o-mini",
                            "embedding_model": "text-embedding-3-small",
                        },
                        "steps": [
                            {"order": 1, "name": "Analyze Query", "description": "Understand query intent and extract keywords"},
                            {"order": 2, "name": "Plan Retrieval Strategy", "description": "LLM-based selection of retrieval tools"},
                            {"order": 3, "name": "Execute Tools", "description": "Dispatch planned tool calls to storage layer"},
                            {"order": 4, "name": "Assemble Evidence", "description": "Collect and deduplicate all evidence gathered so far"},
                            {"order": 5, "name": "Evaluate And Decide", "description": "Check evidence sufficiency; loop back or proceed to generation"},
                            {"order": 6, "name": "Generate Answer", "description": "Generate the final answer using assembled evidence"},
                        ],
                    },
                },
            ],
            "edges": [],
        },
    },
]


async def get_all_templates(db: AsyncSession, *, redis=None) -> list[PipelineTemplate]:
    """Return all available pipeline templates."""
    if redis:
        from ..cache import cache_get, cache_set, TTL_STATIC
        cached = cache_get(redis, "tmpl", "_global", "list")
        if cached is not None:
            return cached
    result = await db.execute(
        select(PipelineTemplate).order_by(PipelineTemplate.category, PipelineTemplate.name)
    )
    rows = list(result.scalars().all())
    if redis:
        from ..cache import cache_set, TTL_STATIC
        data = [{"template_id": t.template_id, "name": t.name, "description": t.description,
                 "category": t.category, "definition": _parse_definition(t.definition)} for t in rows]
        cache_set(redis, "tmpl", "_global", data, suffix="list", ttl=TTL_STATIC)
    return rows


def _parse_definition(defn) -> dict:
    """Ensure definition is a dict, handling double-encoded JSON strings."""
    if isinstance(defn, str):
        import json
        try:
            defn = json.loads(defn)
        except (json.JSONDecodeError, TypeError):
            defn = {}
    return defn if isinstance(defn, dict) else {}


async def get_template(db: AsyncSession, template_id: str, *, redis=None) -> PipelineTemplate | None:
    """Return a single pipeline template by template_id, or None if not found."""
    if redis:
        from ..cache import cache_get, cache_set, TTL_STATIC
        cached = cache_get(redis, "tmpl", "_global", template_id)
        if cached is not None:
            return cached
    result = await db.execute(
        select(PipelineTemplate).where(PipelineTemplate.template_id == template_id)
    )
    row = result.scalar_one_or_none()
    if row and redis:
        from ..cache import cache_set, TTL_STATIC
        data = {"template_id": row.template_id, "name": row.name, "description": row.description,
                "category": row.category, "definition": _parse_definition(row.definition)}
        cache_set(redis, "tmpl", "_global", data, suffix=template_id, ttl=TTL_STATIC)
    return row


async def get_templates_by_category(db: AsyncSession, category: str) -> list[PipelineTemplate]:
    """Return all templates for a given category."""
    result = await db.execute(
        select(PipelineTemplate).where(PipelineTemplate.category == category)
    )
    return list(result.scalars().all())
