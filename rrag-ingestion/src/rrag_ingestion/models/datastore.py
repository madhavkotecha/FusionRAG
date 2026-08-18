from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DataStoreTarget(BaseModel):
    """A single storage backend within a DataStore."""

    type: str  # "vector" | "graph" | "metadata"
    backend: str  # "faiss" | "milvus" | "pgvector" | "neo4j" | "redis"
    config: dict[str, Any] = Field(default_factory=dict)
    stats: dict[str, Any] = Field(default_factory=dict)


class DataStoreCreate(BaseModel):
    name: str
    description: str = ""
    pipeline_name: str
    source_document_ids: list[str]
    created_by_job_id: str


class DataStore(BaseModel):
    id: str
    workspace_id: str = ""
    name: str
    description: str = ""
    pipeline_name: str
    source_document_ids: list[str] = Field(default_factory=list)
    created_by_job_id: str
    status: str = "building"  # "building" | "ready" | "failed"
    targets: list[DataStoreTarget] = Field(default_factory=list)
    created_at: str
    updated_at: str | None = None
