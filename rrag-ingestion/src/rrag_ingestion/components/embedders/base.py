from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rrag_ingestion.core.base import BaseComponent, ComponentType
from rrag_ingestion.core.schemas import EmbedderConfig


@dataclass
class EmbedderInput:
    """Typed input for embedders."""
    chunks: list[dict[str, Any]] = field(default_factory=list)
    texts: list[str] = field(default_factory=list)


@dataclass
class EmbedderOutput:
    """Typed output from embedders."""
    embeddings: list[dict[str, Any]] = field(default_factory=list)


class BaseEmbedder(BaseComponent):
    """Base class for text embedding components.

    Input:  list[Chunk] with content
    Output: list[EmbeddingResult] with vector, text, metadata

    Top models (MTEB 2025):
    - Qwen3-Embedding-8B: 70.58 (best multilingual, Apache 2.0)
    - BGE-M3: dense+sparse+ColBERT simultaneously (MIT)
    - OpenAI text-embedding-3-small: best cost-effective API
    - Jina-v3: LoRA task adapters (arXiv:2409.10173)
    """

    component_type = ComponentType.EMBEDDER
    ConfigModel = EmbedderConfig

    input_ports = [
        {"name": "chunks", "type": "chunk_list", "description": "Chunks to embed"},
    ]
    output_ports = [
        {"name": "embeddings", "type": "embedding_list", "description": "Embedding vectors"},
    ]

    def validate_config(self, config: dict) -> list[str]:
        """Validate config using Pydantic model."""
        try:
            EmbedderConfig(**config)
            return []
        except Exception as e:
            return [str(e)]
