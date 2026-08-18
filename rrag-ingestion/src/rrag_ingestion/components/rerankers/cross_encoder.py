from __future__ import annotations

import logging

from rrag_ingestion.components.rerankers.base import BaseReranker
from rrag_ingestion.core.base import ComponentResult, register_component
from rrag_ingestion.models.document import RetrievalResult

logger = logging.getLogger(__name__)


@register_component
class CrossEncoderReranker(BaseReranker):
    """Cross-encoder reranker from LightRAG/UltraRAG using BAAI models."""

    name = "cross_encoder_reranker"
    version = "0.1.0"
    description = "Cross-encoder document reranker using sentence-transformers (from LightRAG/UltraRAG)"
    config_schema = {
        "model_name": {"type": "string", "default": "BAAI/bge-reranker-v2-m3"},
        "top_k": {"type": "integer", "default": 10},
        "min_score": {"type": "number", "default": 0.0},
        "device": {"type": "string", "default": "cpu"},
    }

    async def invoke(self, input_data: ComponentResult, config: dict) -> ComponentResult:
        retrieved = input_data.data.get("retrieved", [])
        query = input_data.data.get("query", "")

        if not retrieved or not query:
            return ComponentResult(data=input_data.data, errors=["No retrieved documents or query for reranking"])

        model_name = config.get("model_name", "BAAI/bge-reranker-v2-m3")
        top_k = config.get("top_k", 10)
        min_score = config.get("min_score", 0.0)
        device = config.get("device", "cpu")

        try:
            from sentence_transformers import CrossEncoder

            model = CrossEncoder(model_name, device=device)

            pairs = []
            for doc in retrieved:
                content = doc.content if hasattr(doc, "content") else doc.get("content", "")
                pairs.append((query, content))

            scores = model.predict(pairs)

            reranked = []
            for doc, score in sorted(zip(retrieved, scores), key=lambda x: x[1], reverse=True):
                if score >= min_score:
                    reranked.append(RetrievalResult(
                        id=doc.id if hasattr(doc, "id") else doc.get("id", ""),
                        content=doc.content if hasattr(doc, "content") else doc.get("content", ""),
                        score=float(score),
                        metadata={
                            **(doc.metadata if hasattr(doc, "metadata") else doc.get("metadata", {})),
                            "reranked": True,
                        },
                    ))

            return ComponentResult(
                data={**input_data.data, "retrieved": reranked[:top_k]},
                metadata={"reranked_count": len(reranked[:top_k]), "model": model_name},
            )

        except ImportError:
            return ComponentResult(data=input_data.data, errors=["sentence-transformers not installed for reranking"])
        except Exception as e:
            return ComponentResult(data=input_data.data, errors=[f"Reranking failed: {e}"])
