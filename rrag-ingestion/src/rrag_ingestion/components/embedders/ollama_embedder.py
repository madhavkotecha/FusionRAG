from __future__ import annotations

import logging
import uuid
from typing import Any

import httpx

from rrag_ingestion.components.embedders.base import BaseEmbedder
from rrag_ingestion.core.base import ComponentResult, register_component
from rrag_ingestion.models.document import EmbeddingResult

logger = logging.getLogger(__name__)


@register_component
class OllamaEmbedder(BaseEmbedder):
    """Ollama embedding component — runs on host with MPS acceleration."""

    name = "ollama_embedder"
    version = "0.1.0"
    description = "Local embeddings via Ollama (MPS-accelerated on Apple Silicon)"
    config_schema = {
        "model": {"type": "string", "default": "nomic-embed-text"},
        "base_url": {"type": "string", "default": ""},
        "batch_size": {"type": "integer", "default": 50},
    }

    async def invoke(self, input_data: ComponentResult, config: dict) -> ComponentResult:
        import os

        from rrag_ingestion.config import settings

        chunks = input_data.data.get("chunks", [])
        if not chunks:
            return ComponentResult(data=input_data.data, errors=["No chunks to embed"])

        model = config.get("model", "nomic-embed-text")
        base_url = (
            config.get("base_url")
            or settings.ollama_base_url
            or os.environ.get("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
        )
        batch_size = config.get("batch_size", 50)

        try:
            texts: list[str] = []
            chunk_ids: list[str] = []
            for c in chunks:
                content = c.content if hasattr(c, "content") else c.get("content", "")
                cid = c.id if hasattr(c, "id") else c.get("id", str(uuid.uuid4()))
                if content:
                    texts.append(content)
                    chunk_ids.append(cid)

            embeddings: list[EmbeddingResult] = []
            total_batches = (len(texts) + batch_size - 1) // batch_size

            async with httpx.AsyncClient(timeout=120.0) as client:
                for batch_idx, i in enumerate(range(0, len(texts), batch_size)):
                    batch_texts = texts[i : i + batch_size]
                    self.report_progress(
                        f"Embedding batch {batch_idx + 1}/{total_batches} "
                        f"({min(i + batch_size, len(texts))}/{len(texts)} chunks)",
                        items_done=i,
                        items_total=len(texts),
                    )

                    # Ollama embed endpoint supports multiple inputs
                    resp = await client.post(
                        f"{base_url}/api/embed",
                        json={"model": model, "input": batch_texts},
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    vectors = data["embeddings"]

                    for j, vec in enumerate(vectors):
                        embeddings.append(
                            EmbeddingResult(
                                id=chunk_ids[i + j],
                                vector=vec,
                                text=batch_texts[j],
                            )
                        )

            return ComponentResult(
                data={**input_data.data, "embeddings": embeddings},
                metadata={
                    "embedded_count": len(embeddings),
                    "model": model,
                    "provider": "ollama",
                    "dimensions": len(embeddings[0].vector) if embeddings else 0,
                },
            )

        except Exception as e:
            return ComponentResult(
                data=input_data.data,
                errors=[f"Ollama embedding failed: {e}"],
            )
