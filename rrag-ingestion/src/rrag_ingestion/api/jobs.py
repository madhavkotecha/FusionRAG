from __future__ import annotations

import asyncio
import json
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from rrag_ingestion.core.queue import enqueue_pipeline_job
from rrag_ingestion.db import stores as db
from rrag_ingestion.dependencies import AuthContext, get_current_user
from rrag_ingestion.models.job import JobCreate

router = APIRouter()

# Redis key for ephemeral real-time progress (sub_progress, current_step during execution)
PROGRESS_PREFIX = "rrag:progress:"


def _progress_key(workspace_id: str, job_id: str) -> str:
    return f"{PROGRESS_PREFIX}{workspace_id}:{job_id}"


def _merge_live_progress(job: dict, redis_conn, workspace_id: str) -> dict:
    """Overlay ephemeral Redis progress data onto the durable PostgreSQL job data."""
    if job.get("status") not in ("queued", "running"):
        return job
    raw = redis_conn.get(_progress_key(workspace_id, job["id"]))
    if raw:
        live = json.loads(raw)
        job["sub_progress"] = live.get("sub_progress")
        if live.get("current_step"):
            job["current_step"] = live["current_step"]
        if live.get("progress"):
            job["progress"] = live["progress"]
        if live.get("step_results"):
            job["step_results"] = live["step_results"]
        if live.get("pipeline_steps"):
            job["pipeline_steps"] = live["pipeline_steps"]
        if live.get("total_steps"):
            job["total_steps"] = live["total_steps"]
    return job


@router.post("")
async def create_job(
    job: JobCreate,
    request: Request,
    workspace_id: str = Query(..., description="Workspace ID"),
    auth: AuthContext = Depends(get_current_user),
):
    auth.require_workspace_role(workspace_id, "developer")
    redis_conn = request.app.state.redis
    async with request.app.state.db_session_factory() as session:
        job_id = await enqueue_pipeline_job(
            session=session,
            redis_conn=redis_conn,
            workspace_id=workspace_id,
            pipeline_name=job.pipeline_name,
            document_ids=job.document_ids,
            config_overrides=job.config_overrides,
            datastore_id=job.datastore_id,
        )
    return {"job_id": job_id, "status": "queued"}


@router.get("/stream")
async def stream_jobs(
    request: Request,
    workspace_id: str = Query(..., description="Workspace ID"),
    auth: AuthContext = Depends(get_current_user),
    status: str | None = None,
):
    """Stream all job status updates via Server-Sent Events."""
    auth.require_workspace_role(workspace_id, "viewer")
    redis_conn = request.app.state.redis
    db_factory = request.app.state.db_session_factory

    async def generate() -> AsyncGenerator[str, None]:
        prev_snapshot = ""
        while True:
            if await request.is_disconnected():
                break
            async with db_factory() as session:
                jobs = await db.list_jobs(session, workspace_id, status_filter=status, redis=redis_conn)
            # Merge live progress from Redis for active jobs
            for j in jobs:
                _merge_live_progress(j, redis_conn, workspace_id)
            snapshot = json.dumps(jobs, sort_keys=True)
            if snapshot != prev_snapshot:
                prev_snapshot = snapshot
                yield f"data: {json.dumps({'type': 'jobs', 'jobs': jobs})}\n\n"
            has_active = any(
                j.get("status") in ("queued", "running") for j in jobs
            )
            if not has_active:
                yield f"data: {json.dumps({'type': 'idle'})}\n\n"
                break
            await asyncio.sleep(2)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("")
async def list_all_jobs(
    request: Request,
    workspace_id: str = Query(..., description="Workspace ID"),
    auth: AuthContext = Depends(get_current_user),
    status: str | None = None,
):
    auth.require_workspace_role(workspace_id, "viewer")
    redis_conn = request.app.state.redis
    async with request.app.state.db_session_factory() as session:
        jobs = await db.list_jobs(session, workspace_id, status_filter=status, redis=redis_conn)
    for j in jobs:
        _merge_live_progress(j, redis_conn, workspace_id)
    return {"jobs": jobs}


@router.get("/{job_id}/stream")
async def stream_single_job(
    job_id: str,
    request: Request,
    workspace_id: str = Query(..., description="Workspace ID"),
    auth: AuthContext = Depends(get_current_user),
):
    """Stream a single job's status updates via Server-Sent Events."""
    auth.require_workspace_role(workspace_id, "viewer")
    redis_conn = request.app.state.redis
    db_factory = request.app.state.db_session_factory

    async def generate() -> AsyncGenerator[str, None]:
        prev_snapshot = ""
        while True:
            if await request.is_disconnected():
                break
            async with db_factory() as session:
                job = await db.get_job(session, workspace_id, job_id, redis=redis_conn)
            if not job:
                yield f"data: {json.dumps({'type': 'error', 'error': 'Job not found'})}\n\n"
                break
            _merge_live_progress(job, redis_conn, workspace_id)
            snapshot = json.dumps(job, sort_keys=True)
            if snapshot != prev_snapshot:
                prev_snapshot = snapshot
                yield f"data: {json.dumps({'type': 'job', 'job': job})}\n\n"
            status = job.get("status", "")
            if status not in ("queued", "running"):
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                break
            await asyncio.sleep(1)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{job_id}")
async def get_job(
    job_id: str,
    request: Request,
    workspace_id: str = Query(..., description="Workspace ID"),
    auth: AuthContext = Depends(get_current_user),
):
    auth.require_workspace_role(workspace_id, "viewer")
    redis_conn = request.app.state.redis
    async with request.app.state.db_session_factory() as session:
        job = await db.get_job(session, workspace_id, job_id, redis=redis_conn)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    _merge_live_progress(job, redis_conn, workspace_id)
    return job


@router.post("/{job_id}/resume")
async def resume_job(
    job_id: str,
    request: Request,
    workspace_id: str = Query(..., description="Workspace ID"),
    auth: AuthContext = Depends(get_current_user),
):
    """Resume a failed job from the step that failed."""
    auth.require_workspace_role(workspace_id, "developer")
    redis_conn = request.app.state.redis
    async with request.app.state.db_session_factory() as session:
        job = await db.get_job(session, workspace_id, job_id, redis=redis_conn)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        # Allow resuming failed jobs or completed jobs that have step errors
        step_results = job.get("step_results", [])
        has_step_errors = any(r.get("status") in ("error", "failed") for r in step_results)
        if job.get("status") not in ("failed",) and not has_step_errors:
            raise HTTPException(status_code=400, detail=f"No failed steps to resume (status: {job.get('status')})")

        # Determine which step to resume from
        step_results = job.get("step_results", [])
        completed_steps = [r for r in step_results if r.get("status") in ("completed", "ok")]
        resume_from = len(completed_steps)

        # Keep only the completed step results, reset failed/error ones
        kept_results = [r for r in step_results if r.get("status") in ("completed", "ok")]

        # Reset job status to queued, clear errors, keep completed step results
        await db.update_job(
            session, workspace_id, job_id, redis=redis_conn,
            status="queued",
            errors=[],
            step_results=kept_results,
        )

        # Mark datastore as building again
        datastore_id = job.get("datastore_id")
        if datastore_id:
            await db.update_datastore(session, workspace_id, datastore_id, status="building")

    # Re-enqueue with resume_from_step
    from rrag_ingestion.core.queue import get_queue
    queue = get_queue(redis_conn)
    queue.enqueue(
        "rrag_ingestion.core.queue.run_pipeline_job",
        job_id,
        resume_from_step=resume_from,
        job_timeout=1800,
    )
    return {
        "job_id": job_id,
        "status": "queued",
        "resume_from_step": resume_from,
        "completed_steps": len(completed_steps),
        "total_steps": job.get("total_steps", 0),
    }


@router.delete("/{job_id}")
async def cancel_job(
    job_id: str,
    request: Request,
    workspace_id: str = Query(..., description="Workspace ID"),
    auth: AuthContext = Depends(get_current_user),
):
    auth.require_workspace_role(workspace_id, "developer")
    redis_conn = request.app.state.redis
    async with request.app.state.db_session_factory() as session:
        job = await db.get_job(session, workspace_id, job_id, redis=redis_conn)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        await db.update_job(session, workspace_id, job_id, redis=redis_conn, status="cancelled")
    return {"cancelled": job_id}
