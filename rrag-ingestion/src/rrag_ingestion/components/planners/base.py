from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rrag_ingestion.core.base import BaseComponent, ComponentType
from rrag_ingestion.core.schemas import PlannerConfig


@dataclass
class PlannerInput:
    """Typed input for planners."""
    query: str = ""
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class PlannerOutput:
    """Typed output from planners."""
    plan: dict[str, Any] = field(default_factory=dict)
    subqueries: list[str] = field(default_factory=list)
    reasoning_trace: list[str] = field(default_factory=list)


class BasePlanner(BaseComponent):
    """Base class for query planning and decomposition.

    Input:  query string
    Output: plan (sub-queries, execution DAG, reasoning trace)

    Research:
    - CoRAG (arXiv:2501.14342): rejection sampling for multi-hop chains
    - MCTS-RAG (arXiv:2503.20757): +20% improvement with tree search
    - Self-RAG (arXiv:2310.11511, ICLR 2024): reflection tokens
    - IRCoT: interleaved reasoning and retrieval
    """

    component_type = ComponentType.PLANNER
    ConfigModel = PlannerConfig

    input_ports = [
        {"name": "query", "type": "string", "description": "Query to decompose"},
    ]
    output_ports = [
        {"name": "plan", "type": "object", "description": "Execution plan"},
    ]

    def validate_config(self, config: dict) -> list[str]:
        """Validate config using Pydantic model."""
        try:
            PlannerConfig(**config)
            return []
        except Exception as e:
            return [str(e)]
