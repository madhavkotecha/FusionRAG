from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..dependencies import AuthContext, get_current_user, get_db
from ..models.pipeline import PipelineType
from ..schemas.pipeline import (
    PipelineCreate,
    PipelineResponse,
    PipelineUpdate,
    PipelineVersionCreate,
    PipelineVersionResponse,
)
from ..services import pipeline_service as svc

router = APIRouter()


def _pipeline_to_dict(p) -> dict:
    """Convert Pipeline ORM object or dict to a serializable dict."""
    if isinstance(p, dict):
        return p
    return {
        "id": p.id,
        "workspace_id": p.workspace_id,
        "name": p.name,
        "description": p.description,
        "definition": p.definition,
        "status": p.status,
        "pipeline_type": p.pipeline_type,
        "datastore_id": p.datastore_id,
        "created_by": p.created_by,
        "created_at": p.created_at,
        "updated_at": p.updated_at,
    }


@router.get("")
async def list_pipelines(
    request: Request,
    workspace_id: str = Query(..., description="Workspace ID to filter by (use 'all' for org admins)"),
    pipeline_type: PipelineType | None = Query(None, description="Filter by pipeline type"),
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    redis = request.app.state.redis
    if workspace_id == "all":
        auth.require_org_admin()
        rows = await svc.list_pipelines(db, workspace_id=None, pipeline_type=pipeline_type, redis=redis)
    else:
        auth.require_workspace_role(workspace_id, "viewer")
        rows = await svc.list_pipelines(db, workspace_id, pipeline_type=pipeline_type, redis=redis)
    return [_pipeline_to_dict(p) for p in rows]


@router.post("", status_code=201)
async def create_pipeline(
    data: PipelineCreate,
    request: Request,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    auth.require_workspace_role(data.workspace_id, "developer")
    p = await svc.create_pipeline(db, data, auth.user_id, redis=request.app.state.redis)
    return _pipeline_to_dict(p)


@router.get("/{pipeline_id}")
async def get_pipeline(
    pipeline_id: str,
    request: Request,
    workspace_id: str = Query(..., description="Workspace ID"),
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    auth.require_workspace_role(workspace_id, "viewer")
    p = await svc.get_pipeline(db, pipeline_id, workspace_id, redis=request.app.state.redis)
    return _pipeline_to_dict(p)


@router.put("/{pipeline_id}")
async def update_pipeline(
    pipeline_id: str,
    data: PipelineUpdate,
    request: Request,
    workspace_id: str = Query(..., description="Workspace ID"),
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    auth.require_workspace_role(workspace_id, "developer")
    p = await svc.update_pipeline(db, pipeline_id, workspace_id, data, redis=request.app.state.redis)
    return _pipeline_to_dict(p)


@router.delete("/{pipeline_id}", status_code=204)
async def delete_pipeline(
    pipeline_id: str,
    request: Request,
    workspace_id: str = Query(..., description="Workspace ID"),
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    auth.require_workspace_role(workspace_id, "developer")
    await svc.delete_pipeline(db, pipeline_id, workspace_id, redis=request.app.state.redis)


@router.post(
    "/{pipeline_id}/versions",
    response_model=PipelineVersionResponse,
    status_code=201,
)
async def create_version(
    pipeline_id: str,
    data: PipelineVersionCreate,
    request: Request,
    workspace_id: str = Query(..., description="Workspace ID"),
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    auth.require_workspace_role(workspace_id, "developer")
    return await svc.create_version(
        db, pipeline_id, workspace_id, auth.user_id, data.change_message,
        redis=request.app.state.redis,
    )


@router.get(
    "/{pipeline_id}/versions", response_model=list[PipelineVersionResponse]
)
async def list_versions(
    pipeline_id: str,
    request: Request,
    workspace_id: str = Query(..., description="Workspace ID"),
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    auth.require_workspace_role(workspace_id, "viewer")
    return await svc.list_versions(db, pipeline_id, workspace_id, redis=request.app.state.redis)
