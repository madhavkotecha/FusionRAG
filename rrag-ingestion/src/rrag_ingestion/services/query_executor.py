"""Execute a QueryPipeline with full tracing: retrieve -> optional rerank -> generate."""
from __future__ import annotations

import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from rrag_ingestion.models.query_pipeline import QueryPipeline, RerankerConfig
from rrag_ingestion.services import llm_service

logger = logging.getLogger(__name__)

DEFAULT_INDEX_PATH = "/data/documents/faiss_index"


@dataclass
class TraceStep:
    step: str
    status: str = "pending"
    start_ms: float = 0.0
    end_ms: float = 0.0
    duration_ms: float = 0.0
    input_summary: dict = field(default_factory=dict)
    output_summary: dict = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "step": self.step,
            "status": self.status,
            "duration_ms": round(self.duration_ms, 2),
            "input_summary": self.input_summary,
            "output_summary": self.output_summary,
            "error": self.error,
        }


@dataclass
class QueryTrace:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    pipeline_id: str = ""
    pipeline_name: str = ""
    query: str = ""
    datastore_id: str = ""
    datastore_name: str = ""
    steps: list[TraceStep] = field(default_factory=list)
    total_duration_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "pipeline_id": self.pipeline_id,
            "pipeline_name": self.pipeline_name,
            "query": self.query,
            "datastore_id": self.datastore_id,
            "datastore_name": self.datastore_name,
            "steps": [s.to_dict() for s in self.steps],
            "total_duration_ms": round(self.total_duration_ms, 2),
        }


@dataclass
class RetrievedSource:
    id: str
    content: str
    score: float = 0.0
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "content": self.content,
            "score": self.score,
            "metadata": self.metadata,
        }


@dataclass
class QueryResult:
    sources: list[RetrievedSource]
    strategy: str
    trace: QueryTrace


# ── Retrieval helpers ──────────────────────────────────────────────────────


def _load_chunk_store(index_path: str) -> list[dict]:
    chunks_path = index_path + ".chunks.json"
    if not os.path.exists(chunks_path):
        return []
    try:
        import json
        with open(chunks_path) as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load chunk store: {e}")
        return []


def _retrieve_from_faiss(
    query_embedding: list[float], top_k: int, index_path: str
) -> list[RetrievedSource]:
    import faiss
    import numpy as np

    if not os.path.exists(index_path):
        logger.warning(f"FAISS index not found at {index_path}")
        return []

    index = faiss.read_index(index_path)
    chunk_store = _load_chunk_store(index_path)

    query_vec = np.array([query_embedding], dtype=np.float32)
    scores, indices = index.search(query_vec, top_k)

    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx == -1:
            continue
        chunk_data = next((cs for cs in chunk_store if cs["idx"] == int(idx)), None)
        if chunk_data:
            results.append(RetrievedSource(
                id=chunk_data.get("id", str(idx)),
                content=chunk_data.get("content", ""),
                score=float(score),
                metadata=chunk_data.get("metadata", {}),
            ))
        else:
            results.append(RetrievedSource(id=str(idx), content="", score=float(score)))
    return results


def _retrieve_from_qdrant(
    query_embedding: list[float], top_k: int, config: dict
) -> list[RetrievedSource]:
    """Retrieve from Qdrant using vector similarity search."""
    try:
        from qdrant_client import QdrantClient

        url = config.get("url") or os.environ.get("RRAG_QDRANT_URL", "http://localhost:6333")
        api_key = config.get("api_key") or os.environ.get("RRAG_QDRANT_API_KEY") or None
        collection_name = config.get("collection_name", "rrag_vectors")

        client = QdrantClient(url=url, api_key=api_key)
        search_result = client.query_points(
            collection_name=collection_name,
            query=query_embedding,
            limit=top_k,
        )

        results = []
        for point in search_result.points:
            payload = point.payload or {}
            results.append(RetrievedSource(
                id=payload.get("chunk_id", str(point.id)),
                content=payload.get("content", ""),
                score=point.score,
                metadata={
                    "source": "qdrant",
                    "document_id": payload.get("document_id", ""),
                    **(payload.get("metadata", {})),
                },
            ))
        return results

    except ImportError:
        logger.debug("qdrant-client not available")
        return []
    except Exception as e:
        logger.warning(f"Qdrant retrieval failed: {e}")
        return []


def _retrieve_from_opensearch(
    query: str,
    query_embedding: list[float],
    top_k: int,
    config: dict,
    search_mode: str = "hybrid",
) -> list[RetrievedSource]:
    """Retrieve from OpenSearch using kNN, BM25, or hybrid search."""
    try:
        from opensearchpy import OpenSearch

        host = config.get("host", os.environ.get("RRAG_OPENSEARCH_HOST", "localhost"))
        port = int(config.get("port", os.environ.get("RRAG_OPENSEARCH_PORT", 9200)))
        index_name = config.get("index_name", "rrag_vectors")
        use_ssl = config.get("use_ssl", False)

        client = OpenSearch(
            hosts=[{"host": host, "port": port}],
            use_ssl=use_ssl,
            verify_certs=False,
            ssl_show_warn=False,
        )

        rrf_k = 60

        if search_mode == "knn":
            results = _opensearch_knn(client, index_name, query_embedding, top_k)
        elif search_mode == "bm25":
            results = _opensearch_bm25(client, index_name, query, top_k)
        else:  # hybrid
            knn_results = _opensearch_knn(client, index_name, query_embedding, top_k)
            bm25_results = _opensearch_bm25(client, index_name, query, top_k)
            results = _rrf_fuse(knn_results, bm25_results, top_k, rrf_k)

        return results

    except ImportError:
        logger.debug("opensearch-py not available")
        return []
    except Exception as e:
        logger.warning(f"OpenSearch retrieval failed: {e}")
        return []


def _opensearch_knn(client, index_name: str, embedding: list[float], top_k: int) -> list[RetrievedSource]:
    body = {
        "size": top_k,
        "query": {"knn": {"embedding": {"vector": embedding, "k": top_k}}},
    }
    response = client.search(index=index_name, body=body)
    return _parse_opensearch_hits(response)


def _opensearch_bm25(client, index_name: str, query: str, top_k: int) -> list[RetrievedSource]:
    body = {
        "size": top_k,
        "query": {"match": {"content": {"query": query, "operator": "or"}}},
    }
    response = client.search(index=index_name, body=body)
    return _parse_opensearch_hits(response)


def _parse_opensearch_hits(response: dict) -> list[RetrievedSource]:
    results = []
    for hit in response.get("hits", {}).get("hits", []):
        source = hit.get("_source", {})
        results.append(RetrievedSource(
            id=source.get("chunk_id", hit.get("_id", "")),
            content=source.get("content", ""),
            score=float(hit.get("_score", 0.0)),
            metadata={
                "source": "opensearch",
                "document_id": source.get("document_id", ""),
                **(source.get("metadata", {})),
            },
        ))
    return results


def _rrf_fuse(
    knn_results: list[RetrievedSource],
    bm25_results: list[RetrievedSource],
    top_k: int,
    rrf_k: int = 60,
) -> list[RetrievedSource]:
    """Reciprocal Rank Fusion to merge kNN and BM25 result lists."""
    scores: dict[str, float] = {}
    result_map: dict[str, RetrievedSource] = {}

    for rank, r in enumerate(knn_results):
        scores[r.id] = scores.get(r.id, 0.0) + 1.0 / (rrf_k + rank + 1)
        result_map[r.id] = r

    for rank, r in enumerate(bm25_results):
        scores[r.id] = scores.get(r.id, 0.0) + 1.0 / (rrf_k + rank + 1)
        if r.id not in result_map:
            result_map[r.id] = r

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    fused = []
    for doc_id, fused_score in ranked[:top_k]:
        result = result_map[doc_id]
        fused.append(RetrievedSource(
            id=result.id,
            content=result.content,
            score=fused_score,
            metadata={**result.metadata, "source": "hybrid_rrf"},
        ))
    return fused


_STOP_WORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "dare", "ought",
    "in", "on", "at", "to", "for", "of", "with", "by", "from", "as",
    "into", "through", "during", "before", "after", "above", "below",
    "and", "but", "or", "nor", "not", "so", "yet", "both", "either",
    "neither", "each", "every", "all", "any", "few", "more", "most",
    "other", "some", "such", "no", "only", "own", "same", "than",
    "too", "very", "just", "about", "also", "if", "then", "that",
    "this", "these", "those", "what", "which", "who", "whom", "how",
    "when", "where", "why", "it", "its", "i", "me", "my", "we", "our",
    "you", "your", "he", "him", "his", "she", "her", "they", "them",
    "their",
})


def _query_to_keywords(query: str) -> list[str]:
    """Split query into meaningful keywords, removing stop words."""
    import re
    words = re.findall(r"[a-zA-Z0-9]+", query.lower())
    return [w for w in words if w not in _STOP_WORDS and len(w) > 1]


def _build_keyword_cypher(keywords: list[str], datastore_id: str) -> tuple[str, dict]:
    """Build a Cypher query that matches any keyword in entity name or description."""
    # Build WHERE clause: OR across all keywords
    conditions = []
    params: dict = {"limit": 0}  # limit added by caller
    for i, kw in enumerate(keywords):
        pk = f"kw{i}"
        conditions.append(f"(toLower(n.name) CONTAINS ${pk} OR toLower(n.description) CONTAINS ${pk})")
        params[pk] = kw

    where_keywords = " OR ".join(conditions) if conditions else "true"

    if datastore_id:
        params["ds_id"] = datastore_id
        cypher = (
            f"MATCH (n) WHERE n.datastore_id = $ds_id AND ({where_keywords}) "
            f"OPTIONAL MATCH (n)-[r]-(m) WHERE m.datastore_id = $ds_id "
            "RETURN n.name AS entity, n.description AS desc, "
            "collect(DISTINCT {target: m.name, rel: type(r), desc: r.description}) AS relations "
            "LIMIT $limit"
        )
    else:
        cypher = (
            f"MATCH (n) WHERE {where_keywords} "
            "OPTIONAL MATCH (n)-[r]-(m) "
            "RETURN n.name AS entity, n.description AS desc, "
            "collect(DISTINCT {target: m.name, rel: type(r), desc: r.description}) AS relations "
            "LIMIT $limit"
        )
    return cypher, params


async def _retrieve_from_neo4j(
    query: str, config: dict, top_k: int, datastore_id: str = ""
) -> list[RetrievedSource]:
    """Retrieve from Neo4j knowledge graph, scoped to datastore_id.

    Splits the query into individual keywords and matches any of them against
    entity names and descriptions, filtering out common stop words.
    """
    try:
        from neo4j import AsyncGraphDatabase

        uri = config.get("uri") or os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        username = config.get("username") or os.environ.get("NEO4J_USERNAME", "neo4j")
        password = config.get("password") or os.environ["NEO4J_PASSWORD"]

        keywords = _query_to_keywords(query)
        if not keywords:
            logger.debug("No meaningful keywords extracted from query for graph search")
            return []

        cypher, params = _build_keyword_cypher(keywords, datastore_id)
        params["limit"] = top_k

        driver = AsyncGraphDatabase.driver(uri, auth=(username, password))
        results = []
        async with driver.session() as session:
            records = await session.run(cypher, **params)
            async for record in records:
                context = f"Entity: {record['entity']}\nDescription: {record['desc'] or ''}\n"
                for rel in record["relations"]:
                    if rel["target"]:
                        context += f"  - {rel['rel']}: {rel['target']} ({rel.get('desc', '')})\n"
                results.append(RetrievedSource(
                    id=record["entity"],
                    content=context,
                    score=1.0,
                    metadata={"source": "knowledge_graph"},
                ))
        await driver.close()
        return results
    except ImportError:
        logger.debug("neo4j driver not available")
        return []
    except Exception as e:
        logger.warning(f"Neo4j retrieval failed: {e}")
        return []


# ── Reranking helpers ─────────────────────────────────────────────────────


async def _rerank_cross_encoder(
    sources: list[RetrievedSource],
    query: str,
    model_name: str,
    top_k: int,
    max_length: int = 512,
    batch_size: int = 32,
) -> list[RetrievedSource]:
    """Rerank sources using a cross-encoder model."""
    try:
        from sentence_transformers import CrossEncoder

        model = CrossEncoder(model_name, max_length=max_length)
        pairs = [[query, s.content] for s in sources]

        # Score in batches
        all_scores: list[float] = []
        for i in range(0, len(pairs), batch_size):
            batch = pairs[i : i + batch_size]
            scores = model.predict(batch)
            all_scores.extend(float(s) for s in scores)

        # Assign scores and sort
        for source, score in zip(sources, all_scores):
            source.score = score
            source.metadata["reranker_score"] = score

        sources.sort(key=lambda s: s.score, reverse=True)
        return sources[:top_k]

    except ImportError:
        logger.warning("sentence-transformers not installed, skipping reranking")
        return sources[:top_k]
    except Exception as e:
        logger.warning(f"Cross-encoder reranking failed: {e}")
        return sources[:top_k]


async def _rerank_sources(
    sources: list[RetrievedSource],
    query: str,
    reranker_config: RerankerConfig,
) -> list[RetrievedSource]:
    """Dispatch reranking to the appropriate strategy."""
    strategy = reranker_config.strategy

    if strategy == "cross_encoder":
        sources = await _rerank_cross_encoder(
            sources,
            query,
            model_name=reranker_config.model,
            top_k=reranker_config.top_k,
            max_length=reranker_config.max_length,
            batch_size=reranker_config.batch_size,
        )
    elif strategy == "llm_listwise":
        # LLM listwise reranking — use the LLM to rank documents
        # For now, fall back to score-based sorting with LLM scoring
        logger.info(f"LLM listwise reranking with model={reranker_config.llm_model}")
        sources = sources[: reranker_config.top_k]
    elif strategy in ("cohere", "jina"):
        # API-based rerankers — stub for external API integration
        logger.info(f"{strategy} reranking with model={reranker_config.model}")
        sources = sources[: reranker_config.top_k]
    else:
        sources = sources[: reranker_config.top_k]

    # Apply score threshold
    if reranker_config.score_threshold > 0:
        sources = [s for s in sources if s.score >= reranker_config.score_threshold]

    return sources


# ── Main executor ──────────────────────────────────────────────────────────


async def execute_query_pipeline(
    pipeline: QueryPipeline,
    query: str,
    datastore: dict,
) -> QueryResult:
    """Execute a query pipeline with full tracing.

    Steps: embed -> retrieve -> (optional rerank) -> return sources + trace.
    Generation is handled by the chat layer using the LLM's tool-calling response.
    """
    trace = QueryTrace(
        pipeline_id=pipeline.id,
        pipeline_name=pipeline.name,
        query=query,
        datastore_id=pipeline.datastore_id,
        datastore_name=datastore.get("name", ""),
    )
    overall_start = time.monotonic()

    # ── Step 1: Embed ──
    embed_step = TraceStep(step="embed", input_summary={"query_length": len(query)})
    embed_step.start_ms = time.monotonic()
    embed_step.status = "running"
    trace.steps.append(embed_step)

    query_embedding: list[float] | None = None
    try:
        embeddings = await llm_service.embedding(query)
        query_embedding = embeddings[0] if embeddings else None
        embed_step.status = "completed"
        embed_step.output_summary = {
            "dimensions": len(query_embedding) if query_embedding else 0,
        }
    except Exception as e:
        embed_step.status = "failed"
        embed_step.error = str(e)
        logger.warning(f"Embedding failed: {e}")
    embed_step.end_ms = time.monotonic()
    embed_step.duration_ms = (embed_step.end_ms - embed_step.start_ms) * 1000

    # ── Step 2: Retrieve ──
    retrieve_step = TraceStep(
        step="retrieve",
        input_summary={
            "strategy": pipeline.retrieval_strategy,
            "top_k": pipeline.retriever.top_k,
            "datastore_id": pipeline.datastore_id,
        },
    )
    retrieve_step.start_ms = time.monotonic()
    retrieve_step.status = "running"
    trace.steps.append(retrieve_step)

    sources: list[RetrievedSource] = []
    strategies_used: list[str] = []
    try:
        targets = datastore.get("targets", [])
        vector_target = next((t for t in targets if t["type"] == "vector"), None)
        graph_target = next((t for t in targets if t["type"] == "graph"), None)

        strategy = pipeline.retrieval_strategy

        if strategy == "fusion":
            # ── FusionRAG path (ADR-0007/0008/0009) ──
            from rrag_ingestion.fusion.fusion_rag import FusionRAG
            from rrag_ingestion.fusion.knowledge_store import KnowledgeStore

            store = KnowledgeStore(datastore_id=pipeline.datastore_id)
            try:
                fusion = FusionRAG(store=store)
                fusion_result = await fusion.retrieve(
                    query=query,
                    datastore_id=pipeline.datastore_id,
                    top_k=pipeline.retriever.top_k,
                )
            finally:
                await store.close()

            for chunk in fusion_result.chunks:
                sources.append(RetrievedSource(
                    id=chunk.get("id", ""),
                    content=chunk.get("content", ""),
                    score=chunk.get("score", 0.0),
                    metadata={
                        **chunk.get("metadata", {}),
                        "fusion_strategy": fusion_result.strategy,
                        "escalations": fusion_result.escalations,
                    },
                ))
            strategies_used.append(f"fusion:{fusion_result.strategy}")
            retrieve_step.status = "completed"
            retrieve_step.output_summary = {
                "source_count": len(sources),
                "strategies_used": strategies_used,
                "fusion_strategy": fusion_result.strategy,
                "engines_used": [r.engine for r in fusion_result.engine_results],
                "escalations": fusion_result.escalations,
            }

        else:
            # ── Original retrieval path ──
            use_vector = strategy in ("auto", "vector", "hybrid", "dense") and vector_target is not None
            use_graph = strategy in ("auto", "graph", "hybrid") and graph_target is not None

            if use_vector and vector_target and query_embedding:
                vector_backend = vector_target.get("backend", "faiss")
                vector_config = vector_target.get("config", {})

                if vector_backend == "qdrant":
                    vector_results = _retrieve_from_qdrant(
                        query_embedding, pipeline.retriever.top_k, vector_config,
                    )
                elif vector_backend == "opensearch":
                    vector_results = _retrieve_from_opensearch(
                        query, query_embedding, pipeline.retriever.top_k,
                        vector_config, "hybrid",
                    )
                else:
                    index_path = vector_config.get("index_path", DEFAULT_INDEX_PATH)
                    vector_results = _retrieve_from_faiss(
                        query_embedding, pipeline.retriever.top_k, index_path
                    )
                sources.extend(vector_results)
                if vector_results:
                    strategies_used.append("vector")

            if use_graph and graph_target:
                graph_config = graph_target.get("config", {})
                graph_results = await _retrieve_from_neo4j(
                    query, graph_config, pipeline.retriever.top_k,
                    datastore_id=pipeline.datastore_id,
                )
                sources.extend(graph_results)
                if graph_results:
                    strategies_used.append("graph")

            # Deduplicate
            seen: set[str] = set()
            unique: list[RetrievedSource] = []
            for s in sources:
                if s.id not in seen and s.content:
                    seen.add(s.id)
                    unique.append(s)
            sources = unique[: pipeline.retriever.top_k]

            # Apply score threshold
            if pipeline.retriever.score_threshold > 0:
                sources = [s for s in sources if s.score >= pipeline.retriever.score_threshold]

            retrieve_step.status = "completed"
            retrieve_step.output_summary = {
                "source_count": len(sources),
                "strategies_used": strategies_used,
            }
    except Exception as e:
        retrieve_step.status = "failed"
        retrieve_step.error = str(e)
        logger.warning(f"Retrieval failed: {e}")
    retrieve_step.end_ms = time.monotonic()
    retrieve_step.duration_ms = (retrieve_step.end_ms - retrieve_step.start_ms) * 1000

    # ── Step 3: Rerank (optional) ──
    if pipeline.reranker.enabled and sources:
        rerank_step = TraceStep(
            step="rerank",
            input_summary={
                "strategy": pipeline.reranker.strategy,
                "model": pipeline.reranker.model,
                "input_count": len(sources),
                "top_k": pipeline.reranker.top_k,
            },
        )
        rerank_step.start_ms = time.monotonic()
        rerank_step.status = "running"
        trace.steps.append(rerank_step)

        try:
            sources = await _rerank_sources(sources, query, pipeline.reranker)
            rerank_step.status = "completed"
            rerank_step.output_summary = {
                "output_count": len(sources),
                "top_score": round(sources[0].score, 4) if sources else 0,
            }
        except Exception as e:
            rerank_step.status = "failed"
            rerank_step.error = str(e)
            logger.warning(f"Reranking failed: {e}")
        rerank_step.end_ms = time.monotonic()
        rerank_step.duration_ms = (rerank_step.end_ms - rerank_step.start_ms) * 1000

    strategy_label = "+".join(strategies_used) if strategies_used else "direct"
    if pipeline.reranker.enabled:
        strategy_label += "+rerank"
    trace.total_duration_ms = (time.monotonic() - overall_start) * 1000

    return QueryResult(sources=sources, strategy=strategy_label, trace=trace)
