from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from ..models.pipeline import PipelineStatus, PipelineType


def _to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(w.capitalize() for w in parts[1:])


class PipelineCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)
    workspace_id: str = Field(..., min_length=1, max_length=36)
    definition: dict = {}
    pipeline_type: PipelineType = PipelineType.ingestion
    datastore_id: str | None = None


class PipelineUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)
    definition: dict | None = None
    status: PipelineStatus | None = None
    datastore_id: str | None = None


class PipelineResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=_to_camel,
        populate_by_name=True,
    )

    id: str
    workspace_id: str
    name: str
    description: str | None
    definition: dict
    status: PipelineStatus
    pipeline_type: PipelineType
    datastore_id: str | None
    created_by: str
    created_at: datetime
    updated_at: datetime


class PipelineVersionCreate(BaseModel):
    change_message: str | None = Field(None, max_length=500)


class PipelineVersionResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=_to_camel,
        populate_by_name=True,
    )

    id: str
    pipeline_id: str
    version: int
    definition: dict
    change_message: str | None
    created_by: str
    created_at: datetime
