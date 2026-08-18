from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class JobCreate(BaseModel):
    workspace_id: str = ""
    pipeline_name: str
    document_ids: list[str]
    config_overrides: dict[str, Any] = Field(default_factory=dict)
    datastore_id: str | None = None


class StepResult(BaseModel):
    """Result of a single pipeline step execution."""

    step_index: int
    component: str
    status: str  # "ok" | "error"
    duration_ms: float = 0.0
    error: str | None = None
    output_summary: dict[str, Any] = Field(default_factory=dict)


class SubProgress(BaseModel):
    """Sub-step progress within a running pipeline component."""
    message: str = ""
    items_done: int = 0
    items_total: int = 0


class JobStatus(BaseModel):
    id: str
    workspace_id: str = ""
    pipeline_name: str
    document_ids: list[str]
    status: str = "queued"
    progress: int = 0
    current_step: str | None = None
    total_steps: int = 0
    sub_progress: SubProgress | None = None
    errors: list[str] = Field(default_factory=list)
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    step_results: list[StepResult] = Field(default_factory=list)
    total_duration_ms: float | None = None
    datastore_id: str | None = None
    pipeline_steps: list[str] = Field(default_factory=list)
