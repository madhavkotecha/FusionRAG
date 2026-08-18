from __future__ import annotations

from pydantic import BaseModel, Field


class PipelineStepConfig(BaseModel):
    component: str
    config: dict = Field(default_factory=dict)
    condition: str | None = None


class PipelineConfig(BaseModel):
    name: str
    description: str = ""
    steps: list[PipelineStepConfig] = Field(default_factory=list)
