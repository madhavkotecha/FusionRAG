from __future__ import annotations

import logging

from rrag_ingestion.components.retrievers.base import BaseRetriever
from rrag_ingestion.core.base import ComponentResult, register_component
from rrag_ingestion.models.document import RetrievalResult

logger = logging.getLogger(__name__)


@register_component
class QdrantRetriever(BaseRetriever):
    """Qdrant vector similarity retriever for dedicated vector search."""

    name = "qdrant_retriever"
    version = "0.1.0"
    description = "Vector similarity retrieval from Qdrant"
    config_schema = {
        "url": {"type": "string", "default": "http://localhost:6333"},
        "api_key": {"type": "string", "default": ""},
        "collection_name": {"type": "string", "default": "rrag_vectors"},
        "top_k": {"type": "integer", "default": 20},
        "score_threshold": {"type": "number", "default": 0.0, "description": "Minimum similarity score"},
        "embedding_model": {
            "type": "string",
            "default": "openai",
            "enum": ["openai", "e5", "sentence_transformer"],
        },
    }

    async def invoke(self, input_data: ComponentResult, config: dict) -> ComponentResult:
        query = input_data.data.get("query", "")
        subqueries = input_data.data.get("subqueries", [])
        queries = subqueries if subqueries else [query] if query else []

        if not queries:
            return ComponentResult(data=input_data.data, errors=["No query provided"])

        url = config.get("url", "http://localhost:6333")
        api_key = config.get("api_key", "") or None
        collection_name = config.get("collection_name", "rrag_vectors")
        top_k = config.get("top_k", 20)
        score_threshold = config.get("score_threshold", 0.0)

        try:
            from qdrant_client import QdrantClient

            client = QdrantClient(url=url, api_key=api_key)

            all_results = []
            for q in queries:
                query_embedding = await self._embed_query(q, config)

                search_result = client.query_points(
                    collection_name=collection_name,
                    query=query_embedding,
                    limit=top_k,
                    score_threshold=score_threshold if score_threshold > 0 else None,
                )

                for point in search_result.points:
                    payload = point.payload or {}
                    all_results.append(RetrievalResult(
                        id=payload.get("chunk_id", str(point.id)),
                        content=payload.get("content", ""),
                        score=point.score,
                        metadata={
                            "source": "qdrant",
                            "document_id": payload.get("document_id", ""),
                            "workspace_id": payload.get("workspace_id", ""),
                            **(payload.get("metadata", {})),
                        },
                    ))

            # Deduplicate
            seen = set()
            unique = []
            for r in sorted(all_results, key=lambda x: x.score, reverse=True):
                if r.id not in seen:
                    seen.add(r.id)
                    unique.append(r)

            return ComponentResult(
                data={**input_data.data, "retrieved": unique[:top_k]},
                metadata={"result_count": len(unique[:top_k]), "search_mode": "vector"},
            )

        except ImportError:
            return ComponentResult(
                data=input_data.data,
                errors=["qdrant-client not installed. Install with: pip install qdrant-client"],
            )
        except Exception as e:
            return ComponentResult(data=input_data.data, errors=[f"Qdrant retrieval failed: {e}"])

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
