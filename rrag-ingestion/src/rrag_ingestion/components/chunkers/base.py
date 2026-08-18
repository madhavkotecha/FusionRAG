from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rrag_ingestion.core.base import BaseComponent, ComponentType
from rrag_ingestion.core.schemas import ChunkerConfig


@dataclass
class ChunkerInput:
    """Typed input for chunkers."""
    documents: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ChunkerOutput:
    """Typed output from chunkers."""
    chunks: list[dict[str, Any]] = field(default_factory=list)
    documents: list[dict[str, Any]] = field(default_factory=list)


class BaseChunker(BaseComponent):
    """Base class for text chunking components.

    Input:  list[Document] with raw_text
    Output: list[Chunk] with content, tokens, order_index, metadata

    Research-backed strategies:
    - Recursive: 88-89% recall (Chroma 2024, best general-purpose)
    - Semantic: 91% recall (embedding similarity boundaries)
    - Proposition: +10 Recall@20 (Dense X, arXiv:2312.06648)
    - Late Chunking: context-preserving (arXiv:2409.04701)
    - Contextual: -49% retrieval failures (Anthropic 2024)
    """

    component_type = ComponentType.CHUNKER
    ConfigModel = ChunkerConfig

    input_ports = [
        {"name": "documents", "type": "document_list", "description": "Documents to chunk"},
    ]
    output_ports = [
        {"name": "chunks", "type": "chunk_list", "description": "Text chunks"},
    ]

    def validate_config(self, config: dict) -> list[str]:
        """Validate config using Pydantic model."""
        try:
            ChunkerConfig(**config)
            return []
        except Exception as e:
            return [str(e)]
