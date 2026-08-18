from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rrag_ingestion.core.base import BaseComponent, ComponentType
from rrag_ingestion.core.schemas import RerankerConfig


@dataclass
class RerankerInput:
    """Typed input for rerankers."""
    query: str = ""
    documents: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class RerankerOutput:
    """Typed output from rerankers."""
    documents: list[dict[str, Any]] = field(default_factory=list)


class BaseReranker(BaseComponent):
    """Base class for document reranking.

    Input:  query + list[RetrievalResult]
    Output: list[RetrievalResult] (rescored, reordered, truncated to top_k)

    Top models:
    - BGE-reranker-v2-m3: best open-source multilingual (Apache 2.0)
    - Jina-Reranker-v3 (arXiv:2509.25085): highest BEIR nDCG@10 (61.94)
    - RankZephyr (arXiv:2312.02724): matches GPT-4 at fraction of cost
    - Cohere Rerank 4 Pro: best API quality
    """

    component_type = ComponentType.RERANKER
    ConfigModel = RerankerConfig

    input_ports = [
        {"name": "query", "type": "string", "description": "Original query"},
        {"name": "documents", "type": "document_list", "description": "Documents to rerank"},
    ]
    output_ports = [
        {"name": "documents", "type": "document_list", "description": "Reranked documents"},
    ]

    def validate_config(self, config: dict) -> list[str]:
        """Validate config using Pydantic model."""
        try:
            RerankerConfig(**config)
            return []
        except Exception as e:
            return [str(e)]
