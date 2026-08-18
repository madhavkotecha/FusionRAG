from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rrag_ingestion.core.base import BaseComponent, ComponentType
from rrag_ingestion.core.schemas import AgentConfig


@dataclass
class AgentInput:
    """Typed input for agents."""
    query: str = ""
    response: str = ""
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentOutput:
    """Typed output from agents."""
    routing: dict[str, Any] = field(default_factory=dict)
    score: float = 0.0
    feedback: str = ""
    context: str = ""
    tool_results: list[dict[str, Any]] = field(default_factory=list)


class BaseAgent(BaseComponent):
    """Base class for agentic RAG components.

    Supports 5 agent patterns:
    - Router: routes queries to optimal retrieval strategy (CRAG, Adaptive-RAG)
    - Reflection: evaluates response quality and triggers retry (Self-RAG, RAG-HAT)
    - Memory: manages conversation context (A-Mem, MemR3)
    - Tool Use: executes external tools
    - Orchestrator: coordinates multi-agent workflows

    Research:
    - Agentic RAG Survey (arXiv:2501.09136)
    - CRAG (arXiv:2401.15884): correctness-based routing
    - A-Mem (arXiv:2502.12110): self-organizing memory
    """

    component_type = ComponentType.AGENT
    ConfigModel = AgentConfig

    input_ports = [
        {"name": "query", "type": "string", "description": "Query or input"},
    ]
    output_ports = [
        {"name": "routing", "type": "object", "description": "Routing decision or agent output"},
    ]

    def validate_config(self, config: dict) -> list[str]:
        """Validate config using Pydantic model."""
        try:
            AgentConfig(**config)
            return []
        except Exception as e:
            return [str(e)]
