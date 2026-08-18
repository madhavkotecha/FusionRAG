"""PostgreSQL-backed CRUD operations for documents, datastores, jobs, and query pipelines.

Provides both async (for FastAPI) and sync (for RQ workers) interfaces.
All async reads use Redis cache-aside when a redis client is provided.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from redis import Redis
from sqlalchemy import create_engine, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from rrag_ingestion.cache import (
    TTL_LONG,
    TTL_MEDIUM,
    TTL_SHORT,
    cache_delete,
    cache_get,
    cache_invalidate_entity,
    cache_set,
)
from rrag_ingestion.db.models import (
    DataStoreRow,
    DocumentRow,
    JobRow,
    KBDocumentRow,
    KBSegmentRow,
    KnowledgeBaseRow,
    QueryPipelineRow,
)

logger = logging.getLogger(__name__)

# Cache sync engines by URL to avoid creating a new engine per call
_sync_engines: dict[str, Any] = {}


def _get_sync_engine(db_url: str):
    if db_url not in _sync_engines:
        _sync_engines[db_url] = create_engine(db_url, pool_size=5, pool_pre_ping=True)
    return _sync_engines[db_url]


# ── Documents ────────────────────────────────────────────────────────────


async def save_document(session: AsyncSession, doc_data: dict, *, redis: Redis | None = None) -> dict:
    row = DocumentRow(
        id=doc_data["id"],
        workspace_id=doc_data["workspace_id"],
        filename=doc_data["filename"],
        content_type=doc_data["content_type"],
        file_path=doc_data["file_path"],
        metadata_=doc_data.get("metadata", {}),
    )
    if "created_at" in doc_data and isinstance(doc_data["created_at"], datetime):
        row.created_at = doc_data["created_at"]
    session.add(row)
    await session.commit()
    result = _doc_row_to_dict(row)
    if redis:
        cache_invalidate_entity(redis, "doc", doc_data["workspace_id"], doc_data["id"])
    return result


async def get_document(session: AsyncSession, workspace_id: str, doc_id: str, *, redis: Redis | None = None) -> dict | None:
    if redis:
        cached = cache_get(redis, "doc", workspace_id, doc_id)
        if cached is not None:
            return cached
    row = await session.get(DocumentRow, doc_id)
    if row is None or row.workspace_id != workspace_id:
        return None
    result = _doc_row_to_dict(row)
    if redis:
        cache_set(redis, "doc", workspace_id, result, suffix=doc_id, ttl=TTL_LONG)
    return result


async def list_documents(session: AsyncSession, workspace_id: str, *, redis: Redis | None = None) -> list[dict]:
    if redis:
        cached = cache_get(redis, "doc", workspace_id, "list")
        if cached is not None:
            return cached
    result = await session.execute(
        select(DocumentRow)
        .where(DocumentRow.workspace_id == workspace_id)
        .order_by(DocumentRow.created_at.desc())
    )
    docs = [_doc_row_to_dict(r) for r in result.scalars().all()]
    if redis:
        cache_set(redis, "doc", workspace_id, docs, suffix="list", ttl=TTL_MEDIUM)
    return docs


async def delete_document(session: AsyncSession, workspace_id: str, doc_id: str, *, redis: Redis | None = None) -> dict | None:
    row = await session.get(DocumentRow, doc_id)
    if row is None or row.workspace_id != workspace_id:
        return None
    data = _doc_row_to_dict(row)
    await session.delete(row)
    await session.commit()
    if redis:
        cache_invalidate_entity(redis, "doc", workspace_id, doc_id)
    return data


def _doc_row_to_dict(row: DocumentRow) -> dict:
    return {
        "id": row.id,
        "workspace_id": row.workspace_id,
        "filename": row.filename,
        "content_type": row.content_type,
        "file_path": row.file_path,
        "metadata": row.metadata_ or {},
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


# Sync helpers for RQ worker (runs in a separate process without async event loop)

def get_document_sync(db_url: str, workspace_id: str, doc_id: str) -> dict | None:
    engine = _get_sync_engine(db_url)
    with Session(engine) as session:
        row = session.get(DocumentRow, doc_id)
        if row is None or row.workspace_id != workspace_id:
            return None
        return _doc_row_to_dict(row)


# ── DataStores ───────────────────────────────────────────────────────────


async def create_datastore(
    session: AsyncSession,
    workspace_id: str,
    name: str,
    description: str = "",
    *,
    redis: Redis | None = None,
) -> dict:
    ds_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    row = DataStoreRow(
        id=ds_id,
        workspace_id=workspace_id,
        name=name,
        description=description,
        status="empty",
        targets=[],
        source_document_ids=[],
        created_at=now,
    )
    session.add(row)
    await session.commit()
    result = _ds_row_to_dict(row)
    if redis:
        cache_invalidate_entity(redis, "ds", workspace_id, ds_id)
    return result


async def get_datastore(session: AsyncSession, workspace_id: str, ds_id: str, *, redis: Redis | None = None) -> dict | None:
    if redis:
        cached = cache_get(redis, "ds", workspace_id, ds_id)
        if cached is not None:
            return cached
    row = await session.get(DataStoreRow, ds_id)
    if row is None or row.workspace_id != workspace_id:
        return None
    result = _ds_row_to_dict(row)
    if redis:
        cache_set(redis, "ds", workspace_id, result, suffix=ds_id, ttl=TTL_LONG)
    return result


async def list_datastores(session: AsyncSession, workspace_id: str, *, redis: Redis | None = None) -> list[dict]:
    if redis:
        cached = cache_get(redis, "ds", workspace_id, "list")
        if cached is not None:
            return cached
    result = await session.execute(
        select(DataStoreRow)
        .where(DataStoreRow.workspace_id == workspace_id)
        .order_by(DataStoreRow.created_at.desc())
    )
    stores = [_ds_row_to_dict(r) for r in result.scalars().all()]
    if redis:
        cache_set(redis, "ds", workspace_id, stores, suffix="list", ttl=TTL_MEDIUM)
    return stores


async def update_datastore(
    session: AsyncSession, workspace_id: str, ds_id: str, *, redis: Redis | None = None, **updates: Any
) -> dict | None:
    row = await session.get(DataStoreRow, ds_id)
    if row is None or row.workspace_id != workspace_id:
        return None
    for key, value in updates.items():
        if hasattr(row, key):
            setattr(row, key, value)
    row.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(row)
    result = _ds_row_to_dict(row)
    if redis:
        cache_invalidate_entity(redis, "ds", workspace_id, ds_id)
    return result


async def delete_datastore(session: AsyncSession, workspace_id: str, ds_id: str, *, redis: Redis | None = None) -> bool:
    row = await session.get(DataStoreRow, ds_id)
    if row is None or row.workspace_id != workspace_id:
        return False
    # Clean up external storage backends before deleting the row
    targets = row.targets or []
    await _cleanup_external_backends(targets, ds_id)
    await session.delete(row)
    await session.commit()
    if redis:
        cache_invalidate_entity(redis, "ds", workspace_id, ds_id)
    return True


async def _cleanup_external_backends(targets: list[dict], datastore_id: str) -> None:
    """Remove datastore-specific collections, indexes, and graph data from external backends."""
    import os

    for target in targets:
        backend = target.get("backend", "")
        config = target.get("config", {})
        try:
            if backend == "qdrant":
                from qdrant_client import QdrantClient
                url = config.get("url") or os.environ.get("RRAG_QDRANT_URL", "http://localhost:6333")
                api_key = config.get("api_key") or os.environ.get("RRAG_QDRANT_API_KEY") or None
                collection_name = config.get("collection_name", f"rrag_ds_{datastore_id}")
                client = QdrantClient(url=url, api_key=api_key)
                if client.collection_exists(collection_name):
                    client.delete_collection(collection_name)
                    logger.info(f"Deleted Qdrant collection: {collection_name}")

            elif backend == "opensearch":
                from opensearchpy import OpenSearch
                host = config.get("host") or os.environ.get("RRAG_OPENSEARCH_HOST", "localhost")
                port = int(config.get("port") or os.environ.get("RRAG_OPENSEARCH_PORT", 9200))
                index_name = config.get("index_name", f"rrag_ds_{datastore_id}")
                client = OpenSearch(
                    hosts=[{"host": host, "port": port}],
                    use_ssl=False, verify_certs=False, ssl_show_warn=False,
                )
                if client.indices.exists(index=index_name):
                    client.indices.delete(index=index_name)
                    logger.info(f"Deleted OpenSearch index: {index_name}")

            elif backend == "neo4j":
                from neo4j import AsyncGraphDatabase
                uri = config.get("uri") or os.environ.get("NEO4J_URI", "bolt://localhost:7687")
                username = config.get("username") or os.environ.get("NEO4J_USERNAME", "neo4j")
                password = config.get("password") or os.environ["NEO4J_PASSWORD"]
                driver = AsyncGraphDatabase.driver(uri, auth=(username, password))
                async with driver.session() as neo_session:
                    # Delete all nodes and relationships belonging to this datastore
                    await neo_session.run(
                        "MATCH (n {datastore_id: $ds_id}) DETACH DELETE n",
                        ds_id=datastore_id,
                    )
                    logger.info(f"Deleted Neo4j graph data for datastore: {datastore_id}")
                await driver.close()

        except ImportError:
            logger.debug(f"{backend} client not available for cleanup")
        except Exception as e:
            logger.warning(f"Failed to clean up {backend} for datastore {datastore_id}: {e}")


def _ds_row_to_dict(row: DataStoreRow) -> dict:
    return {
        "id": row.id,
        "workspace_id": row.workspace_id,
        "name": row.name,
        "description": row.description,
        "pipeline_name": row.pipeline_name,
        "source_document_ids": row.source_document_ids or [],
        "created_by_job_id": row.created_by_job_id,
        "status": row.status,
        "targets": row.targets or [],
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


# Sync helpers for RQ worker

def get_datastore_sync(db_url: str, workspace_id: str, ds_id: str) -> dict | None:
    engine = _get_sync_engine(db_url)
    with Session(engine) as session:
        row = session.get(DataStoreRow, ds_id)
        if row is None or row.workspace_id != workspace_id:
            return None
        return _ds_row_to_dict(row)


def update_datastore_sync(db_url: str, workspace_id: str, ds_id: str, **updates: Any) -> dict | None:
    engine = _get_sync_engine(db_url)
    with Session(engine) as session:
        row = session.get(DataStoreRow, ds_id)
        if row is None or row.workspace_id != workspace_id:
            return None
        for key, value in updates.items():
            if hasattr(row, key):
                setattr(row, key, value)
        row.updated_at = datetime.now(timezone.utc)
        session.commit()
        session.refresh(row)
        return _ds_row_to_dict(row)


def create_datastore_from_results_sync(
    db_url: str,
    workspace_id: str,
    job_id: str,
    pipeline_name: str,
    document_ids: list[str],
    step_results: list[dict],
    existing_datastore_id: str | None = None,
    pipeline_step_configs: dict[str, dict] | None = None,
) -> str | None:
    """Create or update a DataStore from completed pipeline results (sync, for RQ worker)."""
    from rrag_ingestion.core.queue import STORAGE_COMPONENT_MAP, _CONFIG_KEYS, _STEP_CONFIG_KEYS

    step_cfgs = pipeline_step_configs or {}
    targets = []
    for step in step_results:
        component = step.get("component", "")
        if component in STORAGE_COMPONENT_MAP:
            target_type, backend = STORAGE_COMPONENT_MAP[component]
            summary = step.get("output_summary", {})
            config = {k: v for k, v in summary.items() if k in _CONFIG_KEYS}
            allowed_keys = _STEP_CONFIG_KEYS.get(component, set())
            for k, v in step_cfgs.get(component, {}).items():
                if k in allowed_keys and k not in config and v is not None:
                    config[k] = v
            targets.append({
                "type": target_type,
                "backend": backend,
                "config": config,
                "stats": {k: v for k, v in summary.items() if k not in _CONFIG_KEYS},
            })

    if not targets:
        return existing_datastore_id

    now = datetime.now(timezone.utc)
    engine = _get_sync_engine(db_url)

    with Session(engine) as session:
        if existing_datastore_id:
            row = session.get(DataStoreRow, existing_datastore_id)
            if row and row.workspace_id == workspace_id:
                row.pipeline_name = pipeline_name
                row.source_document_ids = document_ids
                row.created_by_job_id = job_id
                row.status = "ready"
                row.targets = targets
                row.updated_at = now
                session.commit()
                return existing_datastore_id

        ds_id = str(uuid.uuid4())
        row = DataStoreRow(
            id=ds_id,
            workspace_id=workspace_id,
            name=f"{pipeline_name}_{now.strftime('%Y%m%d')}",
            description=f"Auto-created from pipeline '{pipeline_name}'",
            pipeline_name=pipeline_name,
            source_document_ids=document_ids,
            created_by_job_id=job_id,
            status="ready",
            targets=targets,
            created_at=now,
        )
        session.add(row)
        session.commit()
        return ds_id


# ── Jobs ─────────────────────────────────────────────────────────────────


async def create_job(session: AsyncSession, job_data: dict, *, redis: Redis | None = None) -> dict:
    now = datetime.now(timezone.utc)
    row = JobRow(
        id=job_data["id"],
        workspace_id=job_data.get("workspace_id", ""),
        pipeline_name=job_data["pipeline_name"],
        document_ids=job_data.get("document_ids", []),
        config_overrides=job_data.get("config_overrides", {}),
        status="queued",
        datastore_id=job_data.get("datastore_id"),
        created_at=now,
    )
    session.add(row)
    await session.commit()
    result = _job_row_to_dict(row)
    if redis:
        cache_invalidate_entity(redis, "job", job_data.get("workspace_id", ""))
    return result


async def get_job(session: AsyncSession, workspace_id: str, job_id: str, *, redis: Redis | None = None) -> dict | None:
    if redis:
        cached = cache_get(redis, "job", workspace_id, job_id)
        if cached is not None:
            return cached
    row = await session.get(JobRow, job_id)
    if row is None or row.workspace_id != workspace_id:
        return None
    result = _job_row_to_dict(row)
    if redis:
        cache_set(redis, "job", workspace_id, result, suffix=job_id, ttl=TTL_SHORT)
    return result


async def list_jobs(
    session: AsyncSession, workspace_id: str, status_filter: str | None = None, *, redis: Redis | None = None
) -> list[dict]:
    cache_suffix = f"list:{status_filter}" if status_filter else "list"
    if redis:
        cached = cache_get(redis, "job", workspace_id, cache_suffix)
        if cached is not None:
            return cached
    stmt = select(JobRow).where(JobRow.workspace_id == workspace_id)
    if status_filter:
        stmt = stmt.where(JobRow.status == status_filter)
    stmt = stmt.order_by(JobRow.created_at.desc())
    result = await session.execute(stmt)
    jobs = [_job_row_to_dict(r) for r in result.scalars().all()]
    if redis:
        cache_set(redis, "job", workspace_id, jobs, suffix=cache_suffix, ttl=TTL_SHORT)
    return jobs


async def update_job(session: AsyncSession, workspace_id: str, job_id: str, *, redis: Redis | None = None, **updates: Any) -> None:
    row = await session.get(JobRow, job_id)
    if row is None or row.workspace_id != workspace_id:
        return
    for key, value in updates.items():
        if key == "started_at" and isinstance(value, str):
            value = datetime.fromisoformat(value)
        elif key == "completed_at" and isinstance(value, str):
            value = datetime.fromisoformat(value)
        if hasattr(row, key):
            setattr(row, key, value)
    await session.commit()
    if redis:
        cache_invalidate_entity(redis, "job", workspace_id, job_id)


def _job_row_to_dict(row: JobRow) -> dict:
    return {
        "id": row.id,
        "workspace_id": row.workspace_id,
        "pipeline_name": row.pipeline_name,
        "document_ids": row.document_ids or [],
        "config_overrides": row.config_overrides or {},
        "status": row.status,
        "progress": row.progress,
        "current_step": row.current_step,
        "total_steps": row.total_steps,
        "errors": row.errors or [],
        "step_results": row.step_results or [],
        "pipeline_steps": row.pipeline_steps or [],
        "total_duration_ms": row.total_duration_ms,
        "datastore_id": row.datastore_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        "sub_progress": None,  # Always from Redis (ephemeral)
    }


# Sync helpers for RQ worker

def get_job_sync(db_url: str, workspace_id: str, job_id: str) -> dict | None:
    engine = _get_sync_engine(db_url)
    with Session(engine) as session:
        row = session.get(JobRow, job_id)
        if row is None or row.workspace_id != workspace_id:
            return None
        return _job_row_to_dict(row)


def update_job_sync(db_url: str, workspace_id: str, job_id: str, **updates: Any) -> None:
    engine = _get_sync_engine(db_url)
    with Session(engine) as session:
        row = session.get(JobRow, job_id)
        if row is None or row.workspace_id != workspace_id:
            return
        for key, value in updates.items():
            if key == "started_at" and isinstance(value, str):
                value = datetime.fromisoformat(value)
            elif key == "completed_at" and isinstance(value, str):
                value = datetime.fromisoformat(value)
            if hasattr(row, key):
                setattr(row, key, value)
        session.commit()


def create_job_sync(db_url: str, job_data: dict) -> dict:
    now = datetime.now(timezone.utc)
    engine = _get_sync_engine(db_url)
    with Session(engine) as session:
        row = JobRow(
            id=job_data["id"],
            workspace_id=job_data.get("workspace_id", ""),
            pipeline_name=job_data["pipeline_name"],
            document_ids=job_data.get("document_ids", []),
            config_overrides=job_data.get("config_overrides", {}),
            status="queued",
            datastore_id=job_data.get("datastore_id"),
            created_at=now,
        )
        session.add(row)
        session.commit()
        return _job_row_to_dict(row)


def find_job_by_id_sync(db_url: str, job_id: str) -> dict | None:
    """Find a job by ID without workspace scoping (for RQ worker discovery)."""
    engine = _get_sync_engine(db_url)
    with Session(engine) as session:
        row = session.get(JobRow, job_id)
        if row is None:
            return None
        return _job_row_to_dict(row)


# ── Query Pipelines ─────────────────────────────────────────────────────


async def create_query_pipeline(session: AsyncSession, workspace_id: str, data: dict, *, redis: Redis | None = None) -> dict:
    pipeline_id = data.pop("id", None) or str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    # Extract nested config objects, converting Pydantic models to dicts
    def _to_dict(v: Any) -> Any:
        if hasattr(v, "model_dump"):
            return v.model_dump()
        return v if isinstance(v, dict) else {}

    row = QueryPipelineRow(
        id=pipeline_id,
        workspace_id=workspace_id,
        name=data.get("name", ""),
        description=data.get("description", ""),
        datastore_id=data.get("datastore_id", ""),
        retrieval_strategy=data.get("retrieval_strategy", "auto"),
        retriever=_to_dict(data.get("retriever", {})),
        reranker=_to_dict(data.get("reranker", {})),
        generator=_to_dict(data.get("generator", {})),
        planner=_to_dict(data.get("planner", {})),
        agent=_to_dict(data.get("agent", {})),
        definition=data.get("definition"),
        created_at=now,
    )
    session.add(row)
    await session.commit()
    result = _qp_row_to_dict(row)
    if redis:
        cache_invalidate_entity(redis, "qp", workspace_id, pipeline_id)
    return result


async def get_query_pipeline(
    session: AsyncSession, workspace_id: str, pipeline_id: str, *, redis: Redis | None = None
) -> dict | None:
    if redis:
        cached = cache_get(redis, "qp", workspace_id, pipeline_id)
        if cached is not None:
            return cached
    row = await session.get(QueryPipelineRow, pipeline_id)
    if row is None or row.workspace_id != workspace_id:
        return None
    result = _qp_row_to_dict(row)
    if redis:
        cache_set(redis, "qp", workspace_id, result, suffix=pipeline_id, ttl=TTL_LONG)
    return result


async def list_query_pipelines(session: AsyncSession, workspace_id: str, *, redis: Redis | None = None) -> list[dict]:
    if redis:
        cached = cache_get(redis, "qp", workspace_id, "list")
        if cached is not None:
            return cached
    result = await session.execute(
        select(QueryPipelineRow)
        .where(QueryPipelineRow.workspace_id == workspace_id)
        .order_by(QueryPipelineRow.created_at.desc())
    )
    pipelines = [_qp_row_to_dict(r) for r in result.scalars().all()]
    if redis:
        cache_set(redis, "qp", workspace_id, pipelines, suffix="list", ttl=TTL_MEDIUM)
    return pipelines


async def update_query_pipeline(
    session: AsyncSession, workspace_id: str, pipeline_id: str, updates: dict, *, redis: Redis | None = None
) -> dict | None:
    row = await session.get(QueryPipelineRow, pipeline_id)
    if row is None or row.workspace_id != workspace_id:
        return None

    def _to_dict(v: Any) -> Any:
        if hasattr(v, "model_dump"):
            return v.model_dump()
        return v

    for key, value in updates.items():
        if hasattr(row, key):
            setattr(row, key, _to_dict(value))
    row.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(row)
    result = _qp_row_to_dict(row)
    if redis:
        cache_invalidate_entity(redis, "qp", workspace_id, pipeline_id)
    return result


async def delete_query_pipeline(session: AsyncSession, workspace_id: str, pipeline_id: str, *, redis: Redis | None = None) -> bool:
    row = await session.get(QueryPipelineRow, pipeline_id)
    if row is None or row.workspace_id != workspace_id:
        return False
    await session.delete(row)
    await session.commit()
    if redis:
        cache_invalidate_entity(redis, "qp", workspace_id, pipeline_id)
    return True


def _qp_row_to_dict(row: QueryPipelineRow) -> dict:
    return {
        "id": row.id,
        "workspace_id": row.workspace_id,
        "name": row.name,
        "description": row.description,
        "datastore_id": row.datastore_id,
        "retrieval_strategy": row.retrieval_strategy,
        "retriever": row.retriever or {},
        "reranker": row.reranker or {},
        "generator": row.generator or {},
        "planner": row.planner or {},
        "agent": row.agent or {},
        "definition": row.definition,
        "created_at": row.created_at.isoformat() if row.created_at else "",
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


# ── Knowledge Bases ─────────────────────────────────────────────────────


async def create_knowledge_base(
    session: AsyncSession,
    workspace_id: str,
    data: dict,
    *,
    redis: Redis | None = None,
) -> dict:
    kb_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    row = KnowledgeBaseRow(
        id=kb_id,
        workspace_id=workspace_id,
        name=data.get("name", ""),
        description=data.get("description", ""),
        embedding_model=data.get("embedding_model", "text-embedding-3-small"),
        embedding_provider=data.get("embedding_provider", "openai"),
        chunk_strategy=data.get("chunk_strategy", "recursive"),
        chunk_size=data.get("chunk_size", 512),
        chunk_overlap=data.get("chunk_overlap", 50),
        retrieval_config=data.get("retrieval_config", {}),
        status="ready",
        created_at=now,
    )
    session.add(row)
    await session.commit()
    result = _kb_row_to_dict(row)
    if redis:
        cache_invalidate_entity(redis, "kb", workspace_id, kb_id)
    return result


async def get_knowledge_base(
    session: AsyncSession, workspace_id: str, kb_id: str, *, redis: Redis | None = None
) -> dict | None:
    if redis:
        cached = cache_get(redis, "kb", workspace_id, kb_id)
        if cached is not None:
            return cached
    row = await session.get(KnowledgeBaseRow, kb_id)
    if row is None or row.workspace_id != workspace_id:
        return None
    result = _kb_row_to_dict(row)
    if redis:
        cache_set(redis, "kb", workspace_id, result, suffix=kb_id, ttl=TTL_LONG)
    return result


async def list_knowledge_bases(
    session: AsyncSession, workspace_id: str, *, redis: Redis | None = None
) -> list[dict]:
    if redis:
        cached = cache_get(redis, "kb", workspace_id, "list")
        if cached is not None:
            return cached
    result = await session.execute(
        select(KnowledgeBaseRow)
        .where(KnowledgeBaseRow.workspace_id == workspace_id)
        .order_by(KnowledgeBaseRow.created_at.desc())
    )
    kbs = [_kb_row_to_dict(r) for r in result.scalars().all()]
    if redis:
        cache_set(redis, "kb", workspace_id, kbs, suffix="list", ttl=TTL_MEDIUM)
    return kbs


async def update_knowledge_base(
    session: AsyncSession, workspace_id: str, kb_id: str, updates: dict, *, redis: Redis | None = None
) -> dict | None:
    row = await session.get(KnowledgeBaseRow, kb_id)
    if row is None or row.workspace_id != workspace_id:
        return None
    for key, value in updates.items():
        if hasattr(row, key):
            setattr(row, key, value)
    row.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(row)
    result = _kb_row_to_dict(row)
    if redis:
        cache_invalidate_entity(redis, "kb", workspace_id, kb_id)
    return result


async def delete_knowledge_base(
    session: AsyncSession, workspace_id: str, kb_id: str, *, redis: Redis | None = None
) -> bool:
    row = await session.get(KnowledgeBaseRow, kb_id)
    if row is None or row.workspace_id != workspace_id:
        return False
    # Delete all segments belonging to this KB
    seg_result = await session.execute(
        select(KBSegmentRow).where(KBSegmentRow.knowledge_base_id == kb_id)
    )
    for seg in seg_result.scalars().all():
        await session.delete(seg)
    # Delete all documents belonging to this KB
    doc_result = await session.execute(
        select(KBDocumentRow).where(KBDocumentRow.knowledge_base_id == kb_id)
    )
    for doc in doc_result.scalars().all():
        await session.delete(doc)
    await session.delete(row)
    await session.commit()
    if redis:
        cache_invalidate_entity(redis, "kb", workspace_id, kb_id)
    return True


def _kb_row_to_dict(row: KnowledgeBaseRow) -> dict:
    return {
        "id": row.id,
        "workspace_id": row.workspace_id,
        "name": row.name,
        "description": row.description,
        "embedding_model": row.embedding_model,
        "embedding_provider": row.embedding_provider,
        "chunk_strategy": row.chunk_strategy,
        "chunk_size": row.chunk_size,
        "chunk_overlap": row.chunk_overlap,
        "retrieval_config": row.retrieval_config or {},
        "document_count": row.document_count,
        "segment_count": row.segment_count,
        "word_count": row.word_count,
        "status": row.status,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


# ── KB Documents ────────────────────────────────────────────────────────


async def create_kb_document(
    session: AsyncSession, kb_id: str, data: dict, *, redis: Redis | None = None
) -> dict:
    doc_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    row = KBDocumentRow(
        id=doc_id,
        knowledge_base_id=kb_id,
        filename=data["filename"],
        source_type=data.get("source_type", "upload"),
        file_path=data["file_path"],
        content_type=data.get("content_type", ""),
        status="waiting",
        metadata_=data.get("metadata", {}),
        created_at=now,
    )
    session.add(row)
    await session.commit()
    result = _kbd_row_to_dict(row)
    if redis:
        cache_invalidate_entity(redis, "kbd", kb_id, doc_id)
    return result


async def list_kb_documents(
    session: AsyncSession, kb_id: str, *, redis: Redis | None = None
) -> list[dict]:
    if redis:
        cached = cache_get(redis, "kbd", kb_id, "list")
        if cached is not None:
            return cached
    result = await session.execute(
        select(KBDocumentRow)
        .where(KBDocumentRow.knowledge_base_id == kb_id)
        .order_by(KBDocumentRow.created_at.desc())
    )
    docs = [_kbd_row_to_dict(r) for r in result.scalars().all()]
    if redis:
        cache_set(redis, "kbd", kb_id, docs, suffix="list", ttl=TTL_MEDIUM)
    return docs


async def delete_kb_document(
    session: AsyncSession, kb_id: str, doc_id: str, *, redis: Redis | None = None
) -> bool:
    row = await session.get(KBDocumentRow, doc_id)
    if row is None or row.knowledge_base_id != kb_id:
        return False
    # Delete segments belonging to this document
    seg_result = await session.execute(
        select(KBSegmentRow).where(
            KBSegmentRow.knowledge_base_id == kb_id,
            KBSegmentRow.document_id == doc_id,
        )
    )
    for seg in seg_result.scalars().all():
        await session.delete(seg)
    await session.delete(row)
    await session.commit()
    if redis:
        cache_invalidate_entity(redis, "kbd", kb_id, doc_id)
    return True


def _kbd_row_to_dict(row: KBDocumentRow) -> dict:
    return {
        "id": row.id,
        "knowledge_base_id": row.knowledge_base_id,
        "filename": row.filename,
        "source_type": row.source_type,
        "file_path": row.file_path,
        "content_type": row.content_type,
        "status": row.status,
        "segment_count": row.segment_count,
        "word_count": row.word_count,
        "error": row.error,
        "metadata": row.metadata_ or {},
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


# ── KB Segments ─────────────────────────────────────────────────────────


async def list_kb_segments(
    session: AsyncSession,
    kb_id: str,
    *,
    document_id: str | None = None,
    offset: int = 0,
    limit: int = 50,
    redis: Redis | None = None,
) -> dict:
    cache_suffix = f"list:{document_id}:{offset}:{limit}"
    if redis:
        cached = cache_get(redis, "kbs", kb_id, cache_suffix)
        if cached is not None:
            return cached
    stmt = select(KBSegmentRow).where(KBSegmentRow.knowledge_base_id == kb_id)
    if document_id:
        stmt = stmt.where(KBSegmentRow.document_id == document_id)
    # Get total count
    from sqlalchemy import func as sa_func
    count_stmt = select(sa_func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar() or 0
    # Paginate
    stmt = stmt.order_by(KBSegmentRow.position).offset(offset).limit(limit)
    result = await session.execute(stmt)
    segments = [_kbs_row_to_dict(r) for r in result.scalars().all()]
    response = {"segments": segments, "total": total, "offset": offset, "limit": limit}
    if redis:
        cache_set(redis, "kbs", kb_id, response, suffix=cache_suffix, ttl=TTL_SHORT)
    return response


async def update_kb_segment(
    session: AsyncSession, kb_id: str, seg_id: str, updates: dict, *, redis: Redis | None = None
) -> dict | None:
    row = await session.get(KBSegmentRow, seg_id)
    if row is None or row.knowledge_base_id != kb_id:
        return None
    for key, value in updates.items():
        if hasattr(row, key):
            setattr(row, key, value)
    await session.commit()
    await session.refresh(row)
    result = _kbs_row_to_dict(row)
    if redis:
        cache_invalidate_entity(redis, "kbs", kb_id, seg_id)
    return result


def _kbs_row_to_dict(row: KBSegmentRow) -> dict:
    return {
        "id": row.id,
        "knowledge_base_id": row.knowledge_base_id,
        "document_id": row.document_id,
        "position": row.position,
        "content": row.content,
        "word_count": row.word_count,
        "tokens": row.tokens,
        "keywords": row.keywords or [],
        "status": row.status,
        "enabled": row.enabled,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
