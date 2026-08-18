from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rrag_ingestion.core.base import BaseComponent, ComponentType
from rrag_ingestion.core.schemas import GraphBuilderConfig


@dataclass
class GraphBuilderInput:
    """Typed input for graph builders."""
    entities: list[dict[str, Any]] = field(default_factory=list)
    relations: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class GraphBuilderOutput:
    """Typed output from graph builders."""
    graph: dict[str, Any] = field(default_factory=dict)
    communities: list[dict[str, Any]] = field(default_factory=list)


class BaseGraphBuilder(BaseComponent):
    """Base class for knowledge graph construction.

    Input:  list[Entity], list[Relation]
    Output: KnowledgeGraph (nodes + edges + communities)

    Research:
    - Entity resolution quality is the #1 factor
    - Microsoft GraphRAG: Leiden community detection + hierarchical summaries
    - KGGen iterative clustering (arXiv:2502.09956): 66% accuracy
    """

    component_type = ComponentType.GRAPH_BUILDER
    ConfigModel = GraphBuilderConfig

    input_ports = [
        {"name": "entities", "type": "entity_list", "description": "Extracted entities"},
        {"name": "relations", "type": "relation_list", "description": "Extracted relations"},
    ]
    output_ports = [
        {"name": "graph", "type": "knowledge_graph", "description": "Constructed knowledge graph"},
    ]

    def validate_config(self, config: dict) -> list[str]:
        """Validate config using Pydantic model."""
        try:
            GraphBuilderConfig(**config)
            return []
        except Exception as e:
            return [str(e)]
