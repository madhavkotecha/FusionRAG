from __future__ import annotations

import logging
import os

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..cache import cache_get, cache_set, cache_invalidate_entity, TTL_LONG, TTL_MEDIUM
from ..models.pipeline import Pipeline, PipelineType, PipelineVersion
from ..schemas.pipeline import PipelineCreate, PipelineUpdate
from .query_pipeline_compiler import compile_query_pipeline

logger = logging.getLogger(__name__)

INGESTION_SERVICE_URL = os.environ.get(
    "INGESTION_SERVICE_URL", "http://ingestion:8001"
)


def _pipeline_to_cache(p) -> dict:
    """Convert Pipeline ORM object to a JSON-serializable dict for caching."""
    if isinstance(p, dict):
        return p
    return {
        "id": p.id,
        "workspace_id": p.workspace_id,
        "name": p.name,
        "description": p.description,
        "definition": p.definition,
        "status": p.status.value if hasattr(p.status, "value") else p.status,
        "pipeline_type": p.pipeline_type.value if hasattr(p.pipeline_type, "value") else p.pipeline_type,
        "datastore_id": p.datastore_id,
        "created_by": p.created_by,
        "created_at": p.created_at.isoformat() if hasattr(p.created_at, "isoformat") else p.created_at,
        "updated_at": p.updated_at.isoformat() if hasattr(p.updated_at, "isoformat") else p.updated_at,
    }


async def list_pipelines(
    db: AsyncSession,
    workspace_id: str | None,
    pipeline_type: PipelineType | None = None,
    *,
    redis=None,
) -> list[Pipeline]:
    """List pipelines, optionally filtered by workspace. Pass None for all."""
    cache_ws = workspace_id or "_all"
    cache_suffix = f"list:{pipeline_type.value if pipeline_type else 'all'}"
    if redis:
        cached = cache_get(redis, "pipe", cache_ws, cache_suffix)
        if cached is not None:
            return cached
    stmt = select(Pipeline)
    if workspace_id is not None:
        stmt = stmt.where(Pipeline.workspace_id == workspace_id)
    if pipeline_type is not None:
        stmt = stmt.where(Pipeline.pipeline_type == pipeline_type)
    stmt = stmt.order_by(Pipeline.updated_at.desc())
    result = await db.execute(stmt)
    rows = list(result.scalars().all())
    if redis:
        data = [_pipeline_to_cache(p) for p in rows]
        cache_set(redis, "pipe", cache_ws, data, suffix=cache_suffix, ttl=TTL_MEDIUM)
    return rows


async def get_pipeline(
    db: AsyncSession, pipeline_id: str, workspace_id: str, *, redis=None
) -> Pipeline:
    """Get a single pipeline, verifying workspace ownership."""
    if redis:
        cached = cache_get(redis, "pipe", workspace_id, pipeline_id)
        if cached is not None:
            return cached
    result = await db.execute(
        select(Pipeline).where(
            Pipeline.id == pipeline_id,
            Pipeline.workspace_id == workspace_id,
        )
    )
    pipeline = result.scalar_one_or_none()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    if redis:
        cache_set(redis, "pipe", workspace_id, _pipeline_to_cache(pipeline), suffix=pipeline_id, ttl=TTL_LONG)
    return pipeline


async def create_pipeline(
    db: AsyncSession, data: PipelineCreate, user_id: str, *, redis=None
) -> Pipeline:
    """Create a new pipeline."""
    pipeline = Pipeline(
        workspace_id=data.workspace_id,
        name=data.name,
        description=data.description,
        definition=data.definition,
        pipeline_type=data.pipeline_type,
        datastore_id=data.datastore_id,
        created_by=user_id,
    )
    db.add(pipeline)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"A pipeline named '{data.name}' already exists in this workspace",
        )
    await db.refresh(pipeline)

    if redis:
        cache_invalidate_entity(redis, "pipe", data.workspace_id)

    # For query pipelines, sync compiled config to rrag-ingestion
    if pipeline.pipeline_type == PipelineType.query and pipeline.definition:
        await _sync_query_pipeline(pipeline)

    return pipeline


async def update_pipeline(
    db: AsyncSession,
    pipeline_id: str,
    workspace_id: str,
    data: PipelineUpdate,
    *,
    redis=None,
) -> Pipeline:
    """Partially update a pipeline."""
    pipeline = await get_pipeline(db, pipeline_id, workspace_id)
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(pipeline, key, value)
    await db.commit()
    await db.refresh(pipeline)

    if redis:
        cache_invalidate_entity(redis, "pipe", workspace_id, pipeline_id)

    # For query pipelines, sync compiled config to rrag-ingestion
    if pipeline.pipeline_type == PipelineType.query and pipeline.definition:
        await _sync_query_pipeline(pipeline)

    return pipeline


async def _sync_query_pipeline(pipeline: Pipeline) -> None:
    """Compile visual definition and sync to rrag-ingestion's query pipeline store."""
    try:
        compiled = compile_query_pipeline(
            pipeline_id=pipeline.id,
            name=pipeline.name,
            description=pipeline.description,
            datastore_id=pipeline.datastore_id,
            definition=pipeline.definition,
        )

        async with httpx.AsyncClient(timeout=10.0) as client:
            # Try update first, then create
            url = f"{INGESTION_SERVICE_URL}/api/v1/ingestion/query-pipelines"
            resp = await client.put(f"{url}/{pipeline.id}", json=compiled)
            if resp.status_code == 404:
                # Pipeline doesn't exist yet, create it
                compiled["id"] = pipeline.id
                resp = await client.post(url, json=compiled)

            if resp.status_code not in (200, 201):
                logger.warning(
                    f"Failed to sync query pipeline {pipeline.id}: "
                    f"{resp.status_code} {resp.text}"
                )
    except Exception as e:
        # Don't fail the save if sync fails — it can be retried
        logger.warning(f"Query pipeline sync failed for {pipeline.id}: {e}")


async def delete_pipeline(
    db: AsyncSession, pipeline_id: str, workspace_id: str, *, redis=None
) -> None:
    """Hard-delete a pipeline."""
    pipeline = await get_pipeline(db, pipeline_id, workspace_id)

    # For query pipelines, also delete from rrag-ingestion
    if pipeline.pipeline_type == PipelineType.query:
        await _delete_synced_query_pipeline(pipeline_id)

    await db.delete(pipeline)
    await db.commit()

    if redis:
        cache_invalidate_entity(redis, "pipe", workspace_id, pipeline_id)


async def _delete_synced_query_pipeline(pipeline_id: str) -> None:
    """Delete the synced query pipeline from rrag-ingestion."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            url = f"{INGESTION_SERVICE_URL}/api/v1/ingestion/query-pipelines/{pipeline_id}"
            resp = await client.delete(url)
            if resp.status_code not in (200, 404):
                logger.warning(
                    f"Failed to delete synced query pipeline {pipeline_id}: "
                    f"{resp.status_code}"
                )
    except Exception as e:
        logger.warning(f"Query pipeline delete sync failed for {pipeline_id}: {e}")


async def create_version(
    db: AsyncSession,
    pipeline_id: str,
    workspace_id: str,
    user_id: str,
    change_message: str | None = None,
    *,
    redis=None,
) -> PipelineVersion:
    """Snapshot the current pipeline definition as a new version."""
    pipeline = await get_pipeline(db, pipeline_id, workspace_id)

    # Determine the next version number
    result = await db.execute(
        select(PipelineVersion)
        .where(PipelineVersion.pipeline_id == pipeline_id)
        .order_by(PipelineVersion.version.desc())
    )
    latest = result.scalar_one_or_none()
    next_version = (latest.version + 1) if latest else 1

    version = PipelineVersion(
        pipeline_id=pipeline_id,
        version=next_version,
        definition=pipeline.definition,
        change_message=change_message,
        created_by=user_id,
    )
    db.add(version)
    await db.commit()
    await db.refresh(version)

    if redis:
        cache_invalidate_entity(redis, "pver", workspace_id, pipeline_id)

    return version


async def list_versions(
    db: AsyncSession, pipeline_id: str, workspace_id: str, *, redis=None
) -> list[PipelineVersion]:
    """List all versions for a pipeline."""
    if redis:
        cached = cache_get(redis, "pver", workspace_id, f"{pipeline_id}:list")
        if cached is not None:
            return cached
    # Verify workspace ownership
    await get_pipeline(db, pipeline_id, workspace_id)
    result = await db.execute(
        select(PipelineVersion)
        .where(PipelineVersion.pipeline_id == pipeline_id)
        .order_by(PipelineVersion.version.desc())
    )
    rows = list(result.scalars().all())
    if redis:
        cache_set(redis, "pver", workspace_id, rows, suffix=f"{pipeline_id}:list", ttl=TTL_MEDIUM)
    return rows
