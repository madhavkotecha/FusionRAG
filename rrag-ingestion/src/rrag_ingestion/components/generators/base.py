from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rrag_ingestion.core.base import BaseComponent, ComponentType
from rrag_ingestion.core.schemas import GeneratorConfig


@dataclass
class GeneratorInput:
    """Typed input for generators."""
    query: str = ""
    documents: list[dict[str, Any]] = field(default_factory=list)
    context: str = ""


@dataclass
class GeneratorOutput:
    """Typed output from generators."""
    answer: str = ""
    citations: list[dict[str, Any]] = field(default_factory=list)
    tokens_used: int = 0


class BaseGenerator(BaseComponent):
    """Base class for RAG answer generation.

    Input:  query + list[RetrievalResult] (or pre-built context)
    Output: answer string + citations + token usage

    Research:
    - Temperature 0.1-0.3 for factual RAG (arXiv:2512.01183)
    - Relevance-first context ordering beats random
    - Citation modes improve faithfulness (RAGCHECKER, NeurIPS 2024)
    """

    component_type = ComponentType.GENERATOR
    ConfigModel = GeneratorConfig

    input_ports = [
        {"name": "query", "type": "string", "description": "User question"},
        {"name": "documents", "type": "document_list", "description": "Retrieved context documents"},
    ]
    output_ports = [
        {"name": "response", "type": "string", "description": "Generated answer"},
    ]

    def validate_config(self, config: dict) -> list[str]:
        """Validate config using Pydantic model."""
        try:
            GeneratorConfig(**config)
            return []
        except Exception as e:
            return [str(e)]
