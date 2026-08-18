from __future__ import annotations

import logging

from rrag_ingestion.components.retrievers.base import BaseRetriever
from rrag_ingestion.core.base import ComponentResult, register_component
from rrag_ingestion.models.document import RetrievalResult

logger = logging.getLogger(__name__)


@register_component
class OpenSearchRetriever(BaseRetriever):
    """Hybrid retriever using OpenSearch kNN + BM25 with RRF fusion."""

    name = "opensearch_retriever"
    version = "0.1.0"
    description = "Hybrid vector (kNN) + text (BM25) retrieval from OpenSearch with RRF fusion"
    config_schema = {
        "host": {"type": "string", "default": "localhost"},
        "port": {"type": "integer", "default": 9200},
        "index_name": {"type": "string", "default": "rrag_vectors"},
        "top_k": {"type": "integer", "default": 20},
        "search_mode": {
            "type": "string",
            "default": "hybrid",
            "enum": ["knn", "bm25", "hybrid"],
        },
        "alpha": {"type": "number", "default": 0.5, "description": "Weight for kNN vs BM25 in hybrid mode (1.0 = pure kNN)"},
        "rrf_k": {"type": "integer", "default": 60, "description": "RRF constant k"},
        "use_ssl": {"type": "boolean", "default": False},
        "embedding_model": {
            "type": "string",
            "default": "openai",
            "enum": ["openai", "e5", "sentence_transformer"],
        },
        "workspace_id_filter": {"type": "string", "default": ""},
    }

    async def invoke(self, input_data: ComponentResult, config: dict) -> ComponentResult:
        query = input_data.data.get("query", "")
        subqueries = input_data.data.get("subqueries", [])
        queries = subqueries if subqueries else [query] if query else []

        if not queries:
            return ComponentResult(data=input_data.data, errors=["No query provided"])

        host = config.get("host", "localhost")
        port = config.get("port", 9200)
        index_name = config.get("index_name", "rrag_vectors")
        top_k = config.get("top_k", 20)
        search_mode = config.get("search_mode", "hybrid")
        rrf_k = config.get("rrf_k", 60)
        use_ssl = config.get("use_ssl", False)
        workspace_filter = config.get("workspace_id_filter", "")

        try:
            from opensearchpy import OpenSearch

            client = OpenSearch(
                hosts=[{"host": host, "port": port}],
                use_ssl=use_ssl,
                verify_certs=False,
                ssl_show_warn=False,
            )

            all_results = []
            for q in queries:
                query_embedding = await self._embed_query(q, config)

                results = _search_opensearch(
                    client=client,
                    index_name=index_name,
                    query_text=q,
                    query_embedding=query_embedding,
                    top_k=top_k,
                    search_mode=search_mode,
                    rrf_k=rrf_k,
                    workspace_filter=workspace_filter,
                )
                all_results.extend(results)

            # Deduplicate
            seen = set()
            unique = []
            for r in sorted(all_results, key=lambda x: x.score, reverse=True):
                if r.id not in seen:
                    seen.add(r.id)
                    unique.append(r)

            return ComponentResult(
                data={**input_data.data, "retrieved": unique[:top_k]},
                metadata={"result_count": len(unique[:top_k]), "search_mode": search_mode},
            )

        except ImportError:
            return ComponentResult(
                data=input_data.data,
                errors=["opensearch-py not installed. Install with: pip install opensearch-py"],
            )
        except Exception as e:
            return ComponentResult(data=input_data.data, errors=[f"OpenSearch retrieval failed: {e}"])

    async def _embed_query(self, query: str, config: dict) -> list[float]:
        prefix = config.get("query_prefix", "query: ")
        model_type = config.get("embedding_model", "openai")

        if model_type == "openai":
            from rrag_ingestion.services.openai_client import get_openai_client
            client = get_openai_client()
            response = await client.embeddings.create(model="text-embedding-3-small", input=[query])
            return response.data[0].embedding
        elif model_type in ("ollama", "vllm"):
            from rrag_ingestion.services import llm_service
            from rrag_ingestion.config import settings
            embeddings = await llm_service.embedding(query, model=settings.default_embedding_model)
            return embeddings[0]
        else:
            from sentence_transformers import SentenceTransformer
            model_name = "intfloat/e5-large-v2" if model_type == "e5" else "all-MiniLM-L6-v2"
            model = SentenceTransformer(model_name)
            vec = model.encode([prefix + query], normalize_embeddings=True)
            return vec[0].tolist()


def _search_opensearch(
    client,
    index_name: str,
    query_text: str,
    query_embedding: list[float],
    top_k: int,
    search_mode: str,
    rrf_k: int = 60,
    workspace_filter: str = "",
) -> list[RetrievalResult]:
    """Execute search against OpenSearch with kNN, BM25, or hybrid mode."""

    filter_clause = []
    if workspace_filter:
        filter_clause.append({"term": {"workspace_id": workspace_filter}})

    if search_mode == "knn":
        return _knn_search(client, index_name, query_embedding, top_k, filter_clause)
    elif search_mode == "bm25":
        return _bm25_search(client, index_name, query_text, top_k, filter_clause)
    else:  # hybrid
        knn_results = _knn_search(client, index_name, query_embedding, top_k, filter_clause)
        bm25_results = _bm25_search(client, index_name, query_text, top_k, filter_clause)
        return _rrf_fuse(knn_results, bm25_results, top_k, rrf_k)


def _knn_search(
    client, index_name: str, embedding: list[float], top_k: int, filter_clause: list
) -> list[RetrievalResult]:
    """Pure kNN vector similarity search."""
    body = {
        "size": top_k,
        "query": {
            "knn": {
                "embedding": {
                    "vector": embedding,
                    "k": top_k,
                },
            },
        },
    }
    if filter_clause:
        body["query"] = {
            "bool": {
                "must": [body["query"]],
                "filter": filter_clause,
            }
        }

    response = client.search(index=index_name, body=body)
    return _parse_hits(response, source_label="knn")


def _bm25_search(
    client, index_name: str, query_text: str, top_k: int, filter_clause: list
) -> list[RetrievalResult]:
    """Pure BM25 text search."""
    body = {
        "size": top_k,
        "query": {
            "match": {
                "content": {
                    "query": query_text,
                    "operator": "or",
                },
            },
        },
    }
    if filter_clause:
        body["query"] = {
            "bool": {
                "must": [body["query"]],
                "filter": filter_clause,
            }
        }

    response = client.search(index=index_name, body=body)
    return _parse_hits(response, source_label="bm25")


def _parse_hits(response: dict, source_label: str = "opensearch") -> list[RetrievalResult]:
    """Parse OpenSearch response hits into RetrievalResult objects."""
    results = []
    for hit in response.get("hits", {}).get("hits", []):
        source = hit.get("_source", {})
        results.append(RetrievalResult(
            id=source.get("chunk_id", hit.get("_id", "")),
            content=source.get("content", ""),
            score=float(hit.get("_score", 0.0)),
            metadata={
                "source": source_label,
                "document_id": source.get("document_id", ""),
                "workspace_id": source.get("workspace_id", ""),
                **(source.get("metadata", {})),
            },
        ))
    return results


def _rrf_fuse(
    knn_results: list[RetrievalResult],
    bm25_results: list[RetrievalResult],
    top_k: int,
    rrf_k: int = 60,
) -> list[RetrievalResult]:
    """Reciprocal Rank Fusion to merge kNN and BM25 result lists."""
    scores: dict[str, float] = {}
    result_map: dict[str, RetrievalResult] = {}

    for rank, r in enumerate(knn_results):
        scores[r.id] = scores.get(r.id, 0.0) + 1.0 / (rrf_k + rank + 1)
        result_map[r.id] = r

    for rank, r in enumerate(bm25_results):
        scores[r.id] = scores.get(r.id, 0.0) + 1.0 / (rrf_k + rank + 1)
        if r.id not in result_map:
            result_map[r.id] = r

    # Sort by fused score
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    fused = []
    for doc_id, fused_score in ranked[:top_k]:
        result = result_map[doc_id]
        fused.append(RetrievalResult(
            id=result.id,
            content=result.content,
            score=fused_score,
            metadata={**result.metadata, "source": "hybrid_rrf"},
        ))
    return fused
