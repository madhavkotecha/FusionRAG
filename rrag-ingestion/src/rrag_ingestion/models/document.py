from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class Document(BaseModel):
    id: str
    workspace_id: str = ""
    filename: str
    content_type: str
    raw_text: str | None = None
    file_path: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Chunk(BaseModel):
    id: str
    document_id: str
    content: str
    tokens: int = 0
    order_index: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class Entity(BaseModel):
    id: str
    name: str
    entity_type: str
    description: str = ""
    source_chunks: list[str] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)


class Relation(BaseModel):
    id: str
    source_entity: str
    target_entity: str
    relation_type: str
    description: str = ""
    keywords: list[str] = Field(default_factory=list)
    weight: float = 1.0
    source_chunks: list[str] = Field(default_factory=list)


class SubGraph(BaseModel):
    nodes: list[Entity] = Field(default_factory=list)
    edges: list[Relation] = Field(default_factory=list)


class EmbeddingResult(BaseModel):
    id: str
    vector: list[float]
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalResult(BaseModel):
    id: str
    content: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)
