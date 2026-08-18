"""Base protocol for all three FusionRAG engines."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class EngineResult:
    engine: str
    chunks: list[dict] = field(default_factory=list)   # retrieved evidence
    answer: str = ""                                    # engine-generated answer (if any)
    confidence: float = 0.0
    metadata: dict = field(default_factory=dict)


@runtime_checkable
class RetrievalEngine(Protocol):
    name: str

    async def retrieve(
        self,
        query: str,
        datastore_id: str,
        top_k: int,
        **kwargs,
    ) -> EngineResult: ...
