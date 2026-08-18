from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rrag_ingestion.core.base import BaseComponent, ComponentType
from rrag_ingestion.core.schemas import RetrieverConfig


@dataclass
class RetrieverInput:
    """Typed input for retrievers."""
    query: str = ""
    subqueries: list[str] = field(default_factory=list)
    filters: dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrieverOutput:
    """Typed output from retrievers."""
    documents: list[dict[str, Any]] = field(default_factory=list)


class BaseRetriever(BaseComponent):
    """Base class for document retrieval.

    Input:  query string (and optional subqueries, filters)
    Output: list[RetrievalResult] with content, score, metadata

    Research:
    - Hybrid (dense+BM25) → +26-31% NDCG (ACM TOIS)
    - ColBERTv2 (arXiv:2112.01488): finest-grained matching
    - MMR for relevance-diversity balance
    - HippoRAG (NeurIPS 2024): graph-based retrieval via PageRank
    """

    component_type = ComponentType.RETRIEVER
    ConfigModel = RetrieverConfig

    input_ports = [
        {"name": "query", "type": "string", "description": "Search query"},
    ]
    output_ports = [
        {"name": "documents", "type": "document_list", "description": "Retrieved documents"},
    ]

    def validate_config(self, config: dict) -> list[str]:
        """Validate config using Pydantic model."""
        try:
            RetrieverConfig(**config)
            return []
        except Exception as e:
            return [str(e)]
