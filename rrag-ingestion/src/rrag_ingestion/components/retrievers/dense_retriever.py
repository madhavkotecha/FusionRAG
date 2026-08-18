from __future__ import annotations

import logging

from rrag_ingestion.components.retrievers.base import BaseRetriever
from rrag_ingestion.core.base import ComponentResult, register_component
from rrag_ingestion.models.document import RetrievalResult

logger = logging.getLogger(__name__)


@register_component
class CoRAGDenseRetriever(BaseRetriever):
    """Dense vector retrieval using FAISS, inspired by CoRAG's E5 retriever."""

    name = "corag.dense_retriever"
    version = "0.1.0"
    description = "Dense vector similarity search using FAISS index (from CoRAG)"
    config_schema = {
        "index_path": {"type": "string", "default": "/data/documents/faiss_index"},
        "top_k": {"type": "integer", "default": 20},
        "embedding_model": {"type": "string", "default": "openai", "enum": ["openai", "e5", "sentence_transformer"]},
        "query_prefix": {"type": "string", "default": "query: "},
    }

    async def invoke(self, input_data: ComponentResult, config: dict) -> ComponentResult:
        query = input_data.data.get("query", "")
        subqueries = input_data.data.get("subqueries", [])
        queries = subqueries if subqueries else [query] if query else []

        if not queries:
            return ComponentResult(data=input_data.data, errors=["No query provided"])

        index_path = config.get("index_path", "/data/documents/faiss_index")
        top_k = config.get("top_k", 20)
        index_id_map = input_data.data.get("index_id_map", {})
        chunks = input_data.data.get("chunks", [])

        try:
            import faiss
            import numpy as np

            index = faiss.read_index(index_path)

            all_results = []
            for q in queries:
                # Get query embedding
                query_vec = await self._embed_query(q, config)
                query_vec = np.array([query_vec], dtype=np.float32)

                scores, indices = index.search(query_vec, top_k)

                for score, idx in zip(scores[0], indices[0]):
                    if idx == -1:
                        continue
                    chunk_id = index_id_map.get(int(idx), str(idx))
                    # Find chunk content
                    content = ""
                    for c in chunks:
                        cid = c.id if hasattr(c, "id") else c.get("id", "")
                        if cid == chunk_id:
                            content = c.content if hasattr(c, "content") else c.get("content", "")
                            break

                    all_results.append(RetrievalResult(
                        id=str(chunk_id),
                        content=content,
                        score=float(score),
                        metadata={"source": "dense_faiss", "query": q},
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
                metadata={"result_count": len(unique[:top_k])},
            )

        except ImportError:
            return ComponentResult(data=input_data.data, errors=["faiss-cpu not installed"])
        except Exception as e:
            return ComponentResult(data=input_data.data, errors=[f"Dense retrieval failed: {e}"])

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
