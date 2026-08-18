from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rrag_ingestion.core.base import BaseComponent, ComponentType
from rrag_ingestion.core.schemas import IndexerConfig


@dataclass
class IndexerInput:
    """Typed input for indexers."""
    embeddings: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class IndexerOutput:
    """Typed output from indexers."""
    index_path: str = ""
    index_stats: dict[str, Any] = field(default_factory=dict)


class BaseIndexer(BaseComponent):
    """Base class for vector index construction.

    Input:  list[EmbeddingResult] with vectors
    Output: VectorIndex reference (path or collection name)

    Research:
    - FAISS HNSW M=16, efConstruction=128: 97-99% recall
    - IVF-PQ for >1M vectors (memory-efficient)
    - Milvus DiskANN for >100M vectors
    """

    component_type = ComponentType.INDEXER
    ConfigModel = IndexerConfig

    input_ports = [
        {"name": "embeddings", "type": "embedding_list", "description": "Embedding vectors to index"},
    ]
    output_ports = [
        {"name": "index", "type": "vector_index", "description": "Built vector index"},
    ]

    def validate_config(self, config: dict) -> list[str]:
        """Validate config using Pydantic model."""
        try:
            IndexerConfig(**config)
            return []
        except Exception as e:
            return [str(e)]
