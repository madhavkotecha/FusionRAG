from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rrag_ingestion.core.base import BaseComponent, ComponentType
from rrag_ingestion.core.schemas import ExtractorConfig


@dataclass
class ExtractorInput:
    """Typed input for extractors."""
    chunks: list[dict[str, Any]] = field(default_factory=list)
    query: str = ""


@dataclass
class ExtractorOutput:
    """Typed output from extractors."""
    entities: list[dict[str, Any]] = field(default_factory=list)
    relations: list[dict[str, Any]] = field(default_factory=list)
    subqueries: list[str] = field(default_factory=list)


class BaseExtractor(BaseComponent):
    """Base class for entity/relation extraction and query decomposition.

    Input:  list[Chunk] or query string
    Output: list[Entity], list[Relation], or list[subqueries]

    Research:
    - KGGen (NeurIPS 2025, arXiv:2502.09956): 66% accuracy vs GraphRAG 48%
    - Schema-constrained: better precision
    - Schema-free: better recall
    """

    component_type = ComponentType.EXTRACTOR
    ConfigModel = ExtractorConfig

    input_ports = [
        {"name": "chunks", "type": "chunk_list", "description": "Chunks for extraction"},
    ]
    output_ports = [
        {"name": "entities", "type": "entity_list", "description": "Extracted entities"},
        {"name": "relations", "type": "relation_list", "description": "Extracted relations"},
    ]

    def validate_config(self, config: dict) -> list[str]:
        """Validate config using Pydantic model."""
        try:
            ExtractorConfig(**config)
            return []
        except Exception as e:
            return [str(e)]
