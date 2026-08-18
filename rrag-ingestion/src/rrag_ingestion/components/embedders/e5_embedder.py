from __future__ import annotations

import logging
import uuid

from rrag_ingestion.components.embedders.base import BaseEmbedder
from rrag_ingestion.core.base import ComponentResult, register_component
from rrag_ingestion.models.document import EmbeddingResult

logger = logging.getLogger(__name__)


@register_component
class E5Embedder(BaseEmbedder):
    """E5 embedding model from CoRAG for dense retrieval."""

    name = "e5_embedder"
    version = "0.1.0"
    description = "E5 dense embeddings for passage retrieval (from CoRAG)"
    config_schema = {
        "model_name": {"type": "string", "default": "intfloat/e5-large-v2"},
        "batch_size": {"type": "integer", "default": 32},
        "device": {"type": "string", "default": "cpu"},
        "query_prefix": {"type": "string", "default": "query: "},
        "passage_prefix": {"type": "string", "default": "passage: "},
    }

    async def invoke(self, input_data: ComponentResult, config: dict) -> ComponentResult:
        chunks = input_data.data.get("chunks", [])
        if not chunks:
            return ComponentResult(data=input_data.data, errors=["No chunks to embed"])

        model_name = config.get("model_name", "intfloat/e5-large-v2")
        batch_size = config.get("batch_size", 32)
        device = config.get("device", "cpu")
        passage_prefix = config.get("passage_prefix", "passage: ")

        try:
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer(model_name, device=device)

            texts = []
            chunk_ids = []
            for c in chunks:
                content = c.content if hasattr(c, "content") else c.get("content", "")
                cid = c.id if hasattr(c, "id") else c.get("id", str(uuid.uuid4()))
                if content:
                    texts.append(passage_prefix + content)
                    chunk_ids.append(cid)

            self.report_progress(f"Encoding {len(texts)} chunks with {model_name}", items_done=0, items_total=len(texts))
            vectors = model.encode(texts, batch_size=batch_size, normalize_embeddings=True)

            embeddings = []
            for i, (text, vec) in enumerate(zip(texts, vectors)):
                embeddings.append(EmbeddingResult(
                    id=chunk_ids[i],
                    vector=vec.tolist(),
                    text=text,
                ))

            return ComponentResult(
                data={**input_data.data, "embeddings": embeddings},
                metadata={"embedded_count": len(embeddings), "model": model_name},
            )

        except ImportError:
            return ComponentResult(data=input_data.data, errors=["sentence-transformers not installed"])
        except Exception as e:
            return ComponentResult(data=input_data.data, errors=[f"E5 embedding failed: {e}"])
