from __future__ import annotations

import logging
import uuid

from rrag_ingestion.components.embedders.base import BaseEmbedder
from rrag_ingestion.core.base import ComponentResult, register_component
from rrag_ingestion.models.document import EmbeddingResult

logger = logging.getLogger(__name__)


@register_component
class SentenceTransformerEmbedder(BaseEmbedder):
    """Sentence-Transformers embedding component from UltraRAG."""

    name = "sentence_transformer_embedder"
    version = "0.1.0"
    description = "Local sentence-transformers embeddings (from UltraRAG)"
    config_schema = {
        "model_name": {"type": "string", "default": "all-MiniLM-L6-v2"},
        "batch_size": {"type": "integer", "default": 64},
        "device": {"type": "string", "default": "cpu"},
        "normalize": {"type": "boolean", "default": True},
    }

    async def invoke(self, input_data: ComponentResult, config: dict) -> ComponentResult:
        chunks = input_data.data.get("chunks", [])
        if not chunks:
            return ComponentResult(data=input_data.data, errors=["No chunks to embed"])

        model_name = config.get("model_name", "all-MiniLM-L6-v2")
        batch_size = config.get("batch_size", 64)
        device = config.get("device", "cpu")
        normalize = config.get("normalize", True)

        try:
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer(model_name, device=device)

            texts = []
            chunk_ids = []
            for c in chunks:
                content = c.content if hasattr(c, "content") else c.get("content", "")
                cid = c.id if hasattr(c, "id") else c.get("id", str(uuid.uuid4()))
                if content:
                    texts.append(content)
                    chunk_ids.append(cid)

            self.report_progress(f"Encoding {len(texts)} chunks with {model_name}", items_done=0, items_total=len(texts))
            vectors = model.encode(texts, batch_size=batch_size, normalize_embeddings=normalize)

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
            return ComponentResult(data=input_data.data, errors=[f"Sentence transformer embedding failed: {e}"])
