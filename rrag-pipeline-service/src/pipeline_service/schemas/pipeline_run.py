from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from ..models.pipeline_run import RunStatus


def _to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(w.capitalize() for w in parts[1:])


class PipelineRunCreate(BaseModel):
    input_params: dict | None = None


class PipelineRunResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=_to_camel,
        populate_by_name=True,
    )

    id: str
    pipeline_id: str
    version_id: str | None
    status: RunStatus
    input_params: dict | None
    result: dict | None
    error: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_by: str
    created_at: datetime
