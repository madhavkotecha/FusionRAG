from __future__ import annotations

import logging
import uuid
from typing import Any

from rrag_ingestion.components.embedders.base import BaseEmbedder
from rrag_ingestion.core.base import ComponentResult, register_component
from rrag_ingestion.models.document import EmbeddingResult

logger = logging.getLogger(__name__)


@register_component
class VLLMEmbedder(BaseEmbedder):
    """Text embedding via vLLM — OpenAI-compatible API with GPU acceleration."""

    name = "vllm_embedder"
    version = "0.1.0"
    description = "Text embeddings via vLLM (GPU-accelerated, OpenAI-compatible)"
    config_schema = {
        "model": {"type": "string", "default": "BAAI/bge-large-en-v1.5"},
        "base_url": {"type": "string", "default": ""},
        "api_key": {"type": "string", "default": ""},
        "batch_size": {"type": "integer", "default": 50},
    }

    async def invoke(self, input_data: ComponentResult, config: dict) -> ComponentResult:
        chunks = input_data.data.get("chunks", [])
        if not chunks:
            return ComponentResult(data=input_data.data, errors=["No chunks to embed"])

        model = config.get("model", "BAAI/bge-large-en-v1.5")
        batch_size = config.get("batch_size", 50)

        try:
            from rrag_ingestion.services.openai_client import get_vllm_client

            client = get_vllm_client(
                api_key=config.get("api_key") or None,
                base_url=config.get("base_url") or None,
            )

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
                batch_texts = texts[i : i + batch_size]
                self.report_progress(
                    f"Embedding batch {batch_idx + 1}/{total_batches} "
                    f"({min(i + batch_size, len(texts))}/{len(texts)} chunks)",
                    items_done=i,
                    items_total=len(texts),
                )
                kwargs: dict[str, Any] = {"model": model, "input": batch_texts}
                response = await client.embeddings.create(**kwargs)
                for j, emb_data in enumerate(response.data):
                    embeddings.append(
                        EmbeddingResult(
                            id=chunk_ids[i + j],
                            vector=emb_data.embedding,
                            text=batch_texts[j],
                        )
                    )

            return ComponentResult(
                data={**input_data.data, "embeddings": embeddings},
                metadata={
                    "provider": "vllm",
                    "embedded_count": len(embeddings),
                    "model": model,
                },
            )

        except Exception as e:
            return ComponentResult(
                data=input_data.data,
                errors=[f"vLLM embedding failed: {e}"],
            )
