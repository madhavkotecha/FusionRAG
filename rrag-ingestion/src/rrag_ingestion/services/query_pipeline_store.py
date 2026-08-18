"""PostgreSQL-backed storage for QueryPipeline objects.

Thin wrappers around db.stores to maintain the same API surface used by the
query_pipelines API router and chat/query modules.
"""
from __future__ import annotations

from redis import Redis

from rrag_ingestion.db import stores as db
from rrag_ingestion.db.session import get_session_factory
from rrag_ingestion.models.query_pipeline import QueryPipeline

# Module-level Redis reference, set during app startup via init_redis()
_redis: Redis | None = None


def init_redis(redis: Redis) -> None:
    """Called from main.py lifespan to make Redis available to this module."""
    global _redis
    _redis = redis


async def create_query_pipeline(workspace_id: str, data: dict) -> QueryPipeline:
    factory = get_session_factory()
    async with factory() as session:
        row_dict = await db.create_query_pipeline(session, workspace_id, data, redis=_redis)
    return QueryPipeline(**row_dict)


async def get_query_pipeline(workspace_id: str, pipeline_id: str) -> QueryPipeline | None:
    factory = get_session_factory()
    async with factory() as session:
        row_dict = await db.get_query_pipeline(session, workspace_id, pipeline_id, redis=_redis)
    if row_dict is None:
        return None
    return QueryPipeline(**row_dict)


async def list_query_pipelines(workspace_id: str) -> list[QueryPipeline]:
    factory = get_session_factory()
    async with factory() as session:
        rows = await db.list_query_pipelines(session, workspace_id, redis=_redis)
    return [QueryPipeline(**r) for r in rows]


async def update_query_pipeline(
    workspace_id: str, pipeline_id: str, updates: dict
) -> QueryPipeline | None:
    factory = get_session_factory()
    async with factory() as session:
        row_dict = await db.update_query_pipeline(session, workspace_id, pipeline_id, updates, redis=_redis)
    if row_dict is None:
        return None
    return QueryPipeline(**row_dict)


async def delete_query_pipeline(workspace_id: str, pipeline_id: str) -> bool:
    factory = get_session_factory()
    async with factory() as session:
        return await db.delete_query_pipeline(session, workspace_id, pipeline_id, redis=_redis)
