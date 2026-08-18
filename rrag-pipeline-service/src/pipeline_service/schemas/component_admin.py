from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ComponentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    type: str
    category: str
    name: str
    description: str
    config_schema: dict
    input_ports: list
    output_ports: list
    source: str
    is_composite: bool
    steps: dict | list | None = None

    @field_validator("config_schema", "input_ports", "output_ports", "steps", mode="before")
    @classmethod
    def _parse_json_strings(cls, v: Any) -> Any:
        if isinstance(v, str):
            return json.loads(v)
        return v
    workspace_id: str | None = None
    file_path: str | None = None
    current_version: int = 1
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CodeUpdateRequest(BaseModel):
    code: str = Field(..., max_length=524288)  # 512KB
    change_reason: str | None = Field(None, max_length=500)


class RevertRequest(BaseModel):
    version: int = Field(..., ge=1)


class VersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    component_type: str
    workspace_id: str
    version: int
    file_hash: str
    changed_by: str
    change_reason: str | None = None
    created_at: datetime


class VersionDetailResponse(VersionResponse):
    code: str


class VersionListResponse(BaseModel):
    items: list[VersionResponse]
    total: int
    page: int
    page_size: int
