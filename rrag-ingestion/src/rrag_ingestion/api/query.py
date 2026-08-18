"""Query API for RAG retrieval and generation."""
from __future__ import annotations

import json
import logging
import os
import time
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from rrag_ingestion.dependencies import AuthContext, get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()

# Fallback for when no datastore is specified
DEFAULT_INDEX_PATH = "./data/faiss_index"


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=10000)
    datastore_id: str | None = Field(None, description="DataStore to query against")
    strategy: str = Field("auto", description="Retrieval strategy: auto | vector | graph | hybrid")
    model: str | None = Field(None, description="Explicit LLM model; overrides tier when set")
    tier: str | None = Field(
        None,
        description="Model tier for ADR-0018 routing when no explicit model: fast | capable",
    )
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(2048, ge=1, le=16384)
    system_prompt: str = Field(
        "You are a helpful research assistant. Answer questions accurately based on the provided context. "
        "If you don't have enough context, say so clearly. Cite document numbers when referencing sources.",
    )
    top_k: int = Field(10, ge=1, le=100, description="Number of documents to retrieve")
    conversation_id: str | None = Field(None, description="Continue an existing conversation")
    stream: bool = Field(False, description="Stream the response via SSE")
    synthesis: bool = Field(
        True,
        description="Enable ADR-0021 generation pipeline (evidence ranking, hallucination guard, citations)",
    )
    domain: str = Field(
        "default",
        description="Domain for hallucination guard threshold: default | healthcare | legal | finance",
    )
    query_complexity: float = Field(
        0.5, ge=0.0, le=1.0,
        description="Query complexity hint (0–1) for model tier routing; overridden by ADR-0008 router when fusion strategy is used",
    )


class QuerySource(BaseModel):
    id: str
    content: str
    score: float = 0.0
    metadata: dict = {}


class QueryResponse(BaseModel):
    id: str
    conversation_id: str
    query: str
    answer: str
    sources: list[QuerySource] = []
    model: str
    tokens_used: int = 0
    duration_ms: float = 0.0
    strategy: str = "direct"
    quality_score: float | None = None
    quality_breakdown: dict = {}
    synthesis_enabled: bool = False


# Redis-backed conversation store with TTL
_CONV_PREFIX = "rrag:query_conv:"
_CONV_TTL = 3600 * 24  # 24 hours


def _conv_key(workspace_id: str, conv_id: str) -> str:
    return f"{_CONV_PREFIX}{workspace_id}:{conv_id}"


def _get_conversation(request: Request, workspace_id: str, conv_id: str) -> list[dict]:
    raw = request.app.state.redis.get(_conv_key(workspace_id, conv_id))
    if raw is None:
        return []
    return json.loads(raw)


def _save_conversation(request: Request, workspace_id: str, conv_id: str, history: list[dict]) -> None:
    request.app.state.redis.set(
        _conv_key(workspace_id, conv_id), json.dumps(history), ex=_CONV_TTL
    )


# -- Embedding ------------------------------------------------------------------


async def _get_query_embedding(query: str) -> list[float]:
    """Embed a query using the configured LLM provider."""
    from rrag_ingestion.services import llm_service
    from rrag_ingestion.config import settings
    embeddings = await llm_service.embedding(query, model=settings.default_embedding_model)
    return embeddings[0]


# -- FAISS Retrieval ------------------------------------------------------------


def _load_chunk_store(index_path: str) -> list[dict]:
    """Load the persisted chunk store saved alongside FAISS index."""
    chunks_path = index_path + ".chunks.json"
    if not os.path.exists(chunks_path):
        return []
    try:
        with open(chunks_path) as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load chunk store: {e}")
        return []


def _retrieve_from_faiss(query_embedding: list[float], top_k: int, index_path: str) -> list[QuerySource]:
    """Retrieve documents from FAISS index using pre-computed query embedding."""
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
        chunk_data = None
        for cs in chunk_store:
            if cs["idx"] == int(idx):
                chunk_data = cs
                break

        if chunk_data:
            results.append(QuerySource(
                id=chunk_data.get("id", str(idx)),
                content=chunk_data.get("content", ""),
                score=float(score),
                metadata=chunk_data.get("metadata", {}),
            ))
        else:
            results.append(QuerySource(id=str(idx), content="", score=float(score)))

    return results


# -- Qdrant Retrieval -----------------------------------------------------------


def _retrieve_from_qdrant_query(
    query_embedding: list[float], top_k: int, config: dict
) -> list[QuerySource]:
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
            results.append(QuerySource(
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


# -- OpenSearch Retrieval -------------------------------------------------------


def _retrieve_from_opensearch_query(
    query_text: str,
    query_embedding: list[float],
    top_k: int,
    config: dict,
) -> list[QuerySource]:
    """Retrieve from OpenSearch using hybrid kNN + BM25 with RRF fusion."""
    try:
        from opensearchpy import OpenSearch

        host = config.get("host") or os.environ.get("RRAG_OPENSEARCH_HOST", "localhost")
        port = int(config.get("port") or os.environ.get("RRAG_OPENSEARCH_PORT", 9200))
        index_name = config.get("index_name", "rrag_vectors")
        use_ssl = config.get("use_ssl", False)

        client = OpenSearch(
            hosts=[{"host": host, "port": port}],
            use_ssl=use_ssl,
            verify_certs=False,
            ssl_show_warn=False,
        )

        # kNN search
        knn_body = {
            "size": top_k,
            "query": {"knn": {"embedding": {"vector": query_embedding, "k": top_k}}},
        }
        knn_resp = client.search(index=index_name, body=knn_body)
        knn_results = _parse_opensearch_hits(knn_resp)

        # BM25 search
        bm25_body = {
            "size": top_k,
            "query": {"match": {"content": {"query": query_text, "operator": "or"}}},
        }
        bm25_resp = client.search(index=index_name, body=bm25_body)
        bm25_results = _parse_opensearch_hits(bm25_resp)

        # RRF fusion
        rrf_k = 60
        scores: dict[str, float] = {}
        result_map: dict[str, QuerySource] = {}

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
            fused.append(QuerySource(
                id=result.id,
                content=result.content,
                score=fused_score,
                metadata={**result.metadata, "source": "hybrid_rrf"},
            ))
        return fused

    except ImportError:
        logger.debug("opensearch-py not available")
        return []
    except Exception as e:
        logger.warning(f"OpenSearch retrieval failed: {e}")
        return []


def _parse_opensearch_hits(response: dict) -> list[QuerySource]:
    """Parse OpenSearch response hits into QuerySource objects."""
    results = []
    for hit in response.get("hits", {}).get("hits", []):
        source = hit.get("_source", {})
        results.append(QuerySource(
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


# -- Neo4j KG Retrieval ---------------------------------------------------------


async def _retrieve_from_neo4j(query: str, config: dict, top_k: int, datastore_id: str = "") -> list[QuerySource]:
    """Retrieve from Neo4j knowledge graph using keyword matching, scoped to datastore.

    Splits the query into individual keywords (filtering stop words) and matches
    any keyword against entity names and descriptions.
    """
    from rrag_ingestion.services.query_executor import _query_to_keywords, _build_keyword_cypher

    try:
        from neo4j import AsyncGraphDatabase

        uri = config.get("uri") or os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        username = config.get("username") or os.environ.get("NEO4J_USERNAME", "neo4j")
        password = config.get("password") or os.environ["NEO4J_PASSWORD"]

        keywords = _query_to_keywords(query)
        if not keywords:
            logger.debug("No meaningful keywords for graph search")
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

                results.append(QuerySource(
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


# -- DataStore-aware retrieval router -------------------------------------------


async def _get_datastore(request: Request, workspace_id: str, datastore_id: str) -> dict | None:
    """Look up a DataStore from PostgreSQL."""
    from rrag_ingestion.db import stores as db
    async with request.app.state.db_session_factory() as session:
        return await db.get_datastore(session, workspace_id, datastore_id, redis=request.app.state.redis)


async def _retrieve_from_datastore(
    request: Request,
    workspace_id: str,
    datastore_id: str,
    query_text: str,
    query_embedding: list[float] | None,
    strategy: str,
    top_k: int,
) -> tuple[list[QuerySource], str]:
    """Route retrieval to the correct backends based on DataStore targets.

    Returns (sources, strategy_used).
    """
    ds = await _get_datastore(request, workspace_id, datastore_id)
    if not ds:
        logger.warning(f"DataStore {datastore_id} not found, falling back to direct")
        return [], "direct"

    targets = ds.get("targets", [])
    vector_target = next((t for t in targets if t["type"] == "vector"), None)
    graph_target = next((t for t in targets if t["type"] == "graph"), None)

    # Decide which retrieval paths to use
    use_vector = False
    use_graph = False

    if strategy == "auto":
        use_vector = vector_target is not None
        use_graph = graph_target is not None
    elif strategy == "vector":
        use_vector = vector_target is not None
    elif strategy == "graph":
        use_graph = graph_target is not None
    elif strategy == "hybrid":
        use_vector = vector_target is not None
        use_graph = graph_target is not None

    all_results: list[QuerySource] = []
    strategies_used = []

    # Vector retrieval (Qdrant, OpenSearch, or FAISS)
    if use_vector and vector_target:
        vector_backend = vector_target.get("backend", "faiss")
        vector_config = vector_target.get("config", {})

        if vector_backend == "qdrant" and query_embedding:
            qdrant_results = _retrieve_from_qdrant_query(query_embedding, top_k, vector_config)
            all_results.extend(qdrant_results)
            if qdrant_results:
                strategies_used.append("vector")
        elif vector_backend == "opensearch" and query_embedding:
            opensearch_results = _retrieve_from_opensearch_query(
                query_text, query_embedding, top_k, vector_config,
            )
            all_results.extend(opensearch_results)
            if opensearch_results:
                strategies_used.append("vector")
        elif query_embedding:
            index_path = vector_config.get("index_path", DEFAULT_INDEX_PATH)
            vector_results = _retrieve_from_faiss(query_embedding, top_k, index_path)
            all_results.extend(vector_results)
            if vector_results:
                strategies_used.append("vector")

    # Graph retrieval (Neo4j) — scoped to datastore
    if use_graph and graph_target:
        graph_config = graph_target.get("config", {})
        graph_results = await _retrieve_from_neo4j(query_text, graph_config, top_k, datastore_id=datastore_id)
        all_results.extend(graph_results)
        if graph_results:
            strategies_used.append("graph")

    # Deduplicate by id
    seen = set()
    unique = []
    for r in all_results:
        if r.id not in seen and r.content:
            seen.add(r.id)
            unique.append(r)

    strategy_label = "+".join(strategies_used) if strategies_used else "direct"
    return unique[:top_k], strategy_label


# -- LLM Generation -------------------------------------------------------------


async def _generate_answer(
    messages: list[dict],
    model: str | None,
    tier: str | None,
    temperature: float,
    max_tokens: int,
) -> tuple[str, int]:
    """Call LLM and return (answer, tokens_used).

    ``model`` (explicit) wins; otherwise ``tier`` drives ADR-0018 model routing.
    Used for the direct (non-synthesis) path and as fallback.
    """
    try:
        from rrag_ingestion.services import llm_service
        response = await llm_service.completion(
            messages=messages,
            model=model,
            tier=tier,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        answer = response.choices[0].message.content or ""
        tokens_used = response.usage.total_tokens if response.usage else 0
        return answer, tokens_used
    except Exception as e:
        return f"Generation failed: {e}", 0


async def _run_synthesis(
    request: Request,
    query: str,
    sources: list[QuerySource],
    req: Any,
    tenant_id: str,
) -> tuple[str, float, dict]:
    """Run ADR-0021 GenerationPipeline. Returns (answer, quality_score, breakdown)."""
    try:
        from rrag_ingestion.generation.synthesis import GenerationPipeline
        redis = getattr(request.app.state, "redis", None)
        pipeline = GenerationPipeline(redis=redis, enable_cache=redis is not None)
        source_dicts = [
            {"id": s.id, "content": s.content, "score": s.score, "metadata": s.metadata}
            for s in sources
        ]
        result = await pipeline.run(
            query=query,
            sources=source_dicts,
            query_complexity=req.query_complexity,
            engine_strategy=req.strategy,
            domain=req.domain,
            tenant_id=tenant_id,
        )
        return result.answer, result.quality_score, result.quality_breakdown
    except Exception as e:
        logger.warning("GenerationPipeline failed, falling back to direct generation: %s", e)
        return "", 0.0, {}


def _build_messages(
    system_prompt: str,
    history: list[dict],
    query: str,
    retrieved: list[QuerySource],
) -> list[dict]:
    """Build the LLM messages array with context and history."""
    messages = [{"role": "system", "content": system_prompt}]
    for msg in history[-10:]:
        messages.append(msg)

    user_content = query
    if retrieved:
        context_parts = [f"[Document {i + 1}]\n{src.content}" for i, src in enumerate(retrieved) if src.content]
        if context_parts:
            context = "\n\n".join(context_parts)
            user_content = f"Context:\n{context}\n\nQuestion: {query}"

    messages.append({"role": "user", "content": user_content})
    return messages


# -- Endpoints ------------------------------------------------------------------


@router.post("", response_model=QueryResponse)
async def query(
    req: QueryRequest,
    request: Request,
    workspace_id: str = Query(..., description="Workspace ID"),
    auth: AuthContext = Depends(get_current_user),
):
    """Query documents using RAG retrieval and LLM generation."""
    auth.require_workspace_role(workspace_id, "viewer")
    start = time.monotonic()
    query_id = str(uuid.uuid4())
    conv_id = req.conversation_id or str(uuid.uuid4())
    history = _get_conversation(request, workspace_id, conv_id)

    # Retrieve context
    retrieved: list[QuerySource] = []
    strategy = "direct"

    try:
        query_embedding = await _get_query_embedding(req.query)

        if req.datastore_id:
            # DataStore-aware retrieval
            retrieved, strategy = await _retrieve_from_datastore(
                request, workspace_id, req.datastore_id, req.query, query_embedding, req.strategy, req.top_k,
            )
        else:
            # Fallback: try default FAISS index
            if os.path.exists(DEFAULT_INDEX_PATH):
                retrieved = _retrieve_from_faiss(query_embedding, req.top_k, DEFAULT_INDEX_PATH)
                retrieved = [r for r in retrieved if r.content]
                if retrieved:
                    strategy = "vector"
    except ImportError:
        logger.debug("Retrieval dependencies not available, falling back to direct LLM")
    except Exception as e:
        logger.warning(f"Retrieval failed, falling back to direct LLM: {e}")

    # Generate answer
    from rrag_ingestion.services import llm_service
    answer = ""
    quality_score: float | None = None
    quality_breakdown: dict = {}
    tokens_used = 0

    if req.synthesis and retrieved:
        # ADR-0021: full generation pipeline (evidence ranking, guard, citations)
        answer, quality_score, quality_breakdown = await _run_synthesis(
            request, req.query, retrieved, req, tenant_id=workspace_id
        )

    if not answer:
        # Direct LLM path: synthesis disabled, no sources, or synthesis failed.
        messages = _build_messages(req.system_prompt, history, req.query, retrieved)
        answer, tokens_used = await _generate_answer(
            messages, req.model, req.tier, req.temperature, req.max_tokens
        )

    used_model = req.model or llm_service.select_model(req.tier)

    # Save to conversation history
    history.append({"role": "user", "content": req.query})
    history.append({"role": "assistant", "content": answer})
    _save_conversation(request, workspace_id, conv_id, history)

    duration_ms = round((time.monotonic() - start) * 1000, 2)

    return QueryResponse(
        id=query_id,
        conversation_id=conv_id,
        query=req.query,
        answer=answer,
        sources=retrieved,
        model=used_model,
        tokens_used=tokens_used,
        duration_ms=duration_ms,
        strategy=strategy,
        quality_score=quality_score,
        quality_breakdown=quality_breakdown,
        synthesis_enabled=req.synthesis,
    )


@router.post("/stream")
async def query_stream(
    req: QueryRequest,
    request: Request,
    workspace_id: str = Query(..., description="Workspace ID"),
    auth: AuthContext = Depends(get_current_user),
):
    """Stream a query response via Server-Sent Events."""
    auth.require_workspace_role(workspace_id, "viewer")
    query_id = str(uuid.uuid4())
    conv_id = req.conversation_id or str(uuid.uuid4())
    history = _get_conversation(request, workspace_id, conv_id)

    async def generate() -> AsyncGenerator[str, None]:
        yield f"data: {json.dumps({'type': 'start', 'id': query_id, 'conversation_id': conv_id})}\n\n"

        # Retrieve context
        retrieved: list[QuerySource] = []
        strategy = "direct"
        try:
            query_embedding = await _get_query_embedding(req.query)

            if req.datastore_id:
                retrieved, strategy = await _retrieve_from_datastore(
                    request, workspace_id, req.datastore_id, req.query, query_embedding, req.strategy, req.top_k,
                )
            else:
                if os.path.exists(DEFAULT_INDEX_PATH):
                    retrieved = _retrieve_from_faiss(query_embedding, req.top_k, DEFAULT_INDEX_PATH)
                    retrieved = [r for r in retrieved if r.content]
                    if retrieved:
                        strategy = "vector"
        except Exception:
            pass

        # Send sources
        if retrieved:
            yield f"data: {json.dumps({'type': 'sources', 'sources': [s.model_dump() for s in retrieved], 'strategy': strategy})}\n\n"

        # Build messages and stream LLM
        messages = _build_messages(req.system_prompt, history, req.query, retrieved)

        try:
            from rrag_ingestion.services import llm_service

            full_answer = ""
            async for chunk in llm_service.stream_completion(
                messages=messages,
                model=req.model,
                tier=req.tier,
                temperature=req.temperature,
                max_tokens=req.max_tokens,
            ):
                delta = chunk.choices[0].delta.content if chunk.choices[0].delta.content else ""
                if delta:
                    full_answer += delta
                    yield f"data: {json.dumps({'type': 'token', 'content': delta})}\n\n"

            history.append({"role": "user", "content": req.query})
            history.append({"role": "assistant", "content": full_answer})
            _save_conversation(request, workspace_id, conv_id, history)

            yield f"data: {json.dumps({'type': 'done', 'answer': full_answer, 'strategy': strategy})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    request: Request,
    workspace_id: str = Query(..., description="Workspace ID"),
    auth: AuthContext = Depends(get_current_user),
):
    """Get conversation history."""
    auth.require_workspace_role(workspace_id, "viewer")
    history = _get_conversation(request, workspace_id, conversation_id)
    return {"conversation_id": conversation_id, "messages": history}


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    request: Request,
    workspace_id: str = Query(..., description="Workspace ID"),
    auth: AuthContext = Depends(get_current_user),
):
    """Delete a conversation."""
    auth.require_workspace_role(workspace_id, "developer")
    request.app.state.redis.delete(_conv_key(workspace_id, conversation_id))
    return {"status": "deleted"}
