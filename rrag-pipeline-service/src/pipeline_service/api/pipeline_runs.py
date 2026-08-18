from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..cache import cache_get, cache_set, cache_invalidate_entity, TTL_SHORT, TTL_MEDIUM
from ..dependencies import AuthContext, get_current_user, get_db
from ..models.pipeline import Pipeline
from ..models.pipeline_run import PipelineRun, RunStatus
from ..schemas.pipeline_run import PipelineRunCreate, PipelineRunResponse
from ..services.execution_service import execute_pipeline

router = APIRouter()


@router.post(
    "/pipelines/{pipeline_id}/run",
    response_model=PipelineRunResponse,
    status_code=201,
)
async def run_pipeline(
    pipeline_id: str,
    data: PipelineRunCreate,
    request: Request,
    workspace_id: str = Query(..., description="Workspace ID"),
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    auth.require_workspace_role(workspace_id, "developer")
    redis = request.app.state.redis

    # Verify pipeline exists and belongs to workspace (use pipeline cache)
    from ..services.pipeline_service import get_pipeline as svc_get_pipeline
    pipeline = await svc_get_pipeline(db, pipeline_id, workspace_id, redis=redis)

    # Create the run record
    run = PipelineRun(
        pipeline_id=pipeline_id,
        status=RunStatus.pending,
        input_params=data.input_params,
        created_by=auth.user_id,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    # Execute with real-time SSE events via Redis
    run = await execute_pipeline(db, run, pipeline.definition, redis=redis)

    cache_invalidate_entity(redis, "prun", workspace_id, pipeline_id)

    return run


@router.get("/runs/{run_id}", response_model=PipelineRunResponse)
async def get_run(
    run_id: str,
    request: Request,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    redis = request.app.state.redis

    # Join through pipeline to verify workspace access
    result = await db.execute(
        select(PipelineRun)
        .join(Pipeline, PipelineRun.pipeline_id == Pipeline.id)
        .where(PipelineRun.id == run_id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Verify workspace access through the parent pipeline
    pipeline_result = await db.execute(
        select(Pipeline).where(Pipeline.id == run.pipeline_id)
    )
    pipeline = pipeline_result.scalar_one_or_none()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Run not found")

    auth.require_workspace_role(pipeline.workspace_id, "viewer")
    return run


@router.get(
    "/pipelines/{pipeline_id}/runs",
    response_model=list[PipelineRunResponse],
)
async def list_runs(
    pipeline_id: str,
    request: Request,
    workspace_id: str = Query(..., description="Workspace ID"),
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    auth.require_workspace_role(workspace_id, "viewer")
    redis = request.app.state.redis

    # Check cache for runs list
    cached = cache_get(redis, "prun", workspace_id, f"{pipeline_id}:list")
    if cached is not None:
        return cached

    # Verify pipeline belongs to workspace (use pipeline cache)
    from ..services.pipeline_service import get_pipeline as svc_get_pipeline
    await svc_get_pipeline(db, pipeline_id, workspace_id, redis=redis)

    result = await db.execute(
        select(PipelineRun)
        .where(PipelineRun.pipeline_id == pipeline_id)
        .order_by(PipelineRun.created_at.desc())
    )
    rows = list(result.scalars().all())
    cache_set(redis, "prun", workspace_id, rows, suffix=f"{pipeline_id}:list", ttl=TTL_SHORT)
    return rows
