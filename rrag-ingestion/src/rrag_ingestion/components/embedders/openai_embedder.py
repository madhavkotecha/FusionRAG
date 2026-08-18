from __future__ import annotations

import logging
import uuid
from typing import Any

from rrag_ingestion.components.embedders.base import BaseEmbedder
from rrag_ingestion.core.base import ComponentResult, register_component
from rrag_ingestion.models.document import EmbeddingResult

logger = logging.getLogger(__name__)


@register_component
class OpenAIEmbedder(BaseEmbedder):
    """OpenAI embedding component."""

    name = "openai_embedder"
    version = "0.1.0"
    description = "OpenAI text embeddings (text-embedding-3-small/large)"
    config_schema = {
        "model": {"type": "string", "default": "text-embedding-3-small"},
        "batch_size": {"type": "integer", "default": 100},
        "dimensions": {"type": "integer", "default": None},
    }

    async def invoke(self, input_data: ComponentResult, config: dict) -> ComponentResult:
        chunks = input_data.data.get("chunks", [])
        if not chunks:
            return ComponentResult(data=input_data.data, errors=["No chunks to embed"])

        model = config.get("model", "text-embedding-3-small")
        batch_size = config.get("batch_size", 100)
        dimensions = config.get("dimensions")

        try:
            from rrag_ingestion.services.openai_client import get_openai_client
            client = get_openai_client()

            texts = []
            chunk_ids = []
            for c in chunks:
                content = c.content if hasattr(c, "content") else c.get("content", "")
                cid = c.id if hasattr(c, "id") else c.get("id", str(uuid.uuid4()))
                if content:
                    texts.append(content)
                    chunk_ids.append(cid)

            embeddings = []
            total_batches = (len(texts) + batch_size - 1) // batch_size
            for batch_idx, i in enumerate(range(0, len(texts), batch_size)):
                batch_texts = texts[i:i + batch_size]
                self.report_progress(
                    f"Embedding batch {batch_idx + 1}/{total_batches} ({min(i + batch_size, len(texts))}/{len(texts)} chunks)",
                    items_done=i,
                    items_total=len(texts),
                )
                kwargs: dict[str, Any] = {"model": model, "input": batch_texts}
                if dimensions:
                    kwargs["dimensions"] = dimensions
                response = await client.embeddings.create(**kwargs)
                for j, emb_data in enumerate(response.data):
                    embeddings.append(EmbeddingResult(
                        id=chunk_ids[i + j],
                        vector=emb_data.embedding,
                        text=batch_texts[j],
                    ))

            return ComponentResult(
                data={**input_data.data, "embeddings": embeddings},
                metadata={"embedded_count": len(embeddings), "model": model},
            )

        except Exception as e:
            return ComponentResult(
                data=input_data.data,
                errors=[f"OpenAI embedding failed: {e}"],
            )
