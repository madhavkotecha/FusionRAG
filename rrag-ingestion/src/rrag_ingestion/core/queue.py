from __future__ import annotations

import json
import logging
import time as _time
import uuid
from datetime import datetime, timezone
from typing import Any

from redis import Redis
from rq import Queue

from rrag_ingestion.config import settings

logger = logging.getLogger(__name__)

# Redis key for ephemeral real-time progress during job execution
PROGRESS_PREFIX = "rrag:progress:"

# Maps storage component names to (target_type, backend) for DataStore creation
STORAGE_COMPONENT_MAP = {
    "faiss_indexer": ("vector", "faiss"),
    "milvus_indexer": ("vector", "milvus"),
    "opensearch_indexer": ("vector", "opensearch"),
    "qdrant_indexer": ("vector", "qdrant"),
    "lightrag.pg_vector": ("vector", "pgvector"),
    "lightrag.neo4j_graph": ("graph", "neo4j"),
    "lightrag.redis_kv": ("metadata", "redis"),
}

_CONFIG_KEYS = {"index_path", "collection_name", "table", "store", "key_prefix", "uri", "index_name"}

_STEP_CONFIG_KEYS = {
    "faiss_indexer": {"index_path"},
    "milvus_indexer": {"host", "port", "collection_name"},
    "opensearch_indexer": {"host", "port", "index_name"},
    "qdrant_indexer": {"url", "api_key", "collection_name"},
    "lightrag.pg_vector": {"connection_string", "table_name"},
    "lightrag.neo4j_graph": {"uri", "username", "password", "database"},
    "lightrag.redis_kv": {"redis_url", "key_prefix"},
}


def _progress_key(workspace_id: str, job_id: str) -> str:
    return f"{PROGRESS_PREFIX}{workspace_id}:{job_id}"


def get_queue(redis_conn: Redis | None = None) -> Queue:
    conn = redis_conn or Redis.from_url(settings.redis_url)
    return Queue(settings.rq_queue_name, connection=conn)


async def enqueue_pipeline_job(
    session,
    redis_conn: Redis,
    pipeline_name: str,
    document_ids: list[str],
    config_overrides: dict | None = None,
    datastore_id: str | None = None,
    workspace_id: str | None = None,
) -> str:
    """Create a job in PostgreSQL and enqueue it in RQ."""
    from rrag_ingestion.db import stores as db

    job_id = str(uuid.uuid4())
    job_data = {
        "id": job_id,
        "workspace_id": workspace_id or "",
        "pipeline_name": pipeline_name,
        "document_ids": document_ids,
        "config_overrides": config_overrides or {},
        "datastore_id": datastore_id,
    }
    await db.create_job(session, job_data)

    # Mark datastore as building
    if datastore_id and workspace_id:
        await db.update_datastore(session, workspace_id, datastore_id, status="building")

    queue = get_queue(redis_conn)
    queue.enqueue(
        "rrag_ingestion.core.queue.run_pipeline_job",
        job_id,
        job_timeout=settings.rq_job_timeout,
    )
    return job_id


def _extract_summary(result: Any) -> dict:
    """Extract lightweight metrics from ComponentResult metadata and data."""
    summary: dict[str, Any] = {}
    if result and result.metadata:
        for k, v in result.metadata.items():
            if not k.startswith("_") and isinstance(v, (int, float, str, bool)):
                summary[k] = v
    if result and isinstance(result.data, dict):
        for key in ("chunks", "embeddings", "entities", "documents", "relations"):
            val = result.data.get(key)
            if isinstance(val, list):
                summary[f"{key}_count"] = len(val)
    return summary


def run_pipeline_job(job_id: str, resume_from_step: int = 0) -> dict:
    """RQ worker entry point. Runs synchronously in worker process.

    Uses PostgreSQL for durable state and Redis for ephemeral real-time progress.
    If ``resume_from_step`` > 0, skips already-completed steps and resumes
    from the specified step index.
    """
    import asyncio
    import os
    import shutil
    import tempfile

    import yaml
    from pathlib import Path

    from rrag_ingestion.core.base import ComponentResult
    from rrag_ingestion.core.pipeline import PipelineEngine
    from rrag_ingestion.core.registry import ComponentRegistry
    from rrag_ingestion.db import stores as db
    from rrag_ingestion.db.models import Base

    redis_conn = Redis.from_url(settings.redis_url)
    sync_db_url = settings.database_url.replace("+asyncpg", "")

    # Ensure tables exist (idempotent, safe for worker process)
    sync_engine = db._get_sync_engine(sync_db_url)
    Base.metadata.create_all(sync_engine)

    # Find the job in PostgreSQL (no workspace scoping needed for worker)
    job_data = db.find_job_by_id_sync(sync_db_url, job_id)
    if not job_data:
        return {"error": "Job not found"}

    workspace_id = job_data.get("workspace_id", "")
    progress_key = _progress_key(workspace_id, job_id)

    # Update job to running in PostgreSQL
    db.update_job_sync(
        sync_db_url, workspace_id, job_id,
        status="running",
        started_at=datetime.now(timezone.utc).isoformat(),
    )

    registry = ComponentRegistry()
    registry.auto_discover()
    engine = PipelineEngine(registry)

    pipeline_name = job_data["pipeline_name"]

    # Find pipeline YAML
    pipelines_dir = Path(settings.configs_dir) / "pipelines"
    pipeline_path = None

    ws_pipeline_path = pipelines_dir / workspace_id / f"{pipeline_name}.yaml"
    if ws_pipeline_path.exists():
        pipeline_path = ws_pipeline_path
    else:
        pipeline_path = pipelines_dir / f"{pipeline_name}.yaml"
        if not pipeline_path.exists():
            pipeline_path = None
            ws_dir = pipelines_dir / workspace_id
            if ws_dir.is_dir():
                for p in ws_dir.glob("*.yaml"):
                    with open(p) as f:
                        raw_yaml = yaml.safe_load(f)
                    if raw_yaml and raw_yaml.get("name") == pipeline_name:
                        pipeline_path = p
                        break
            if not pipeline_path:
                for p in pipelines_dir.glob("*.yaml"):
                    with open(p) as f:
                        raw_yaml = yaml.safe_load(f)
                    if raw_yaml and raw_yaml.get("name") == pipeline_name:
                        pipeline_path = p
                        break

    if not pipeline_path:
        db.update_job_sync(
            sync_db_url, workspace_id, job_id,
            status="failed",
            errors=[f"Pipeline '{pipeline_name}' not found"],
        )
        return {"error": "Pipeline not found"}

    pipeline_def = engine.load_pipeline(pipeline_path)

    # Store pipeline step names in PostgreSQL
    step_names = [s.component for s in pipeline_def.steps]
    db.update_job_sync(
        sync_db_url, workspace_id, job_id,
        total_steps=len(step_names),
        pipeline_steps=step_names,
    )

    # Also write initial progress to Redis for real-time SSE
    redis_conn.set(progress_key, json.dumps({
        "pipeline_steps": step_names,
        "total_steps": len(step_names),
        "current_step": None,
        "progress": 0,
        "sub_progress": None,
        "step_results": [],
    }), ex=86400)

    job_start = _time.monotonic()

    # Track step results in memory for progress updates
    accumulated_step_results: list[dict] = []

    def step_start_cb(step: int, total: int, component: str) -> None:
        """Update current_step when a step begins."""
        live = _get_live_progress(redis_conn, progress_key)
        live["current_step"] = component
        live["sub_progress"] = None
        redis_conn.set(progress_key, json.dumps(live), ex=86400)

    def sub_progress_cb(message: str, items_done: int = 0, items_total: int = 0) -> None:
        """Write sub-step progress to Redis for SSE."""
        live = _get_live_progress(redis_conn, progress_key)
        live["sub_progress"] = {
            "message": message,
            "items_done": items_done,
            "items_total": items_total,
        }
        redis_conn.set(progress_key, json.dumps(live), ex=86400)

    def progress_cb(job_id, step, total, component, status, result=None):
        step_result = {
            "step_index": step,
            "component": component,
            "status": status,
            "duration_ms": result.metadata.get("_duration_ms", 0) if result else 0,
            "error": result.errors[0] if result and result.errors else None,
            "output_summary": _extract_summary(result) if result else {},
        }
        accumulated_step_results.append(step_result)

        # Update PostgreSQL with durable step results
        db.update_job_sync(
            sync_db_url, workspace_id, job_id,
            progress=round(step / total * 100),
            current_step=component,
            total_steps=total,
            step_results=list(accumulated_step_results),
        )

        # Update Redis for real-time SSE
        live = _get_live_progress(redis_conn, progress_key)
        live["progress"] = round(step / total * 100)
        live["current_step"] = component
        live["step_results"] = list(accumulated_step_results)
        live["sub_progress"] = None
        redis_conn.set(progress_key, json.dumps(live), ex=86400)

    # Resolve document_ids to file_paths via PostgreSQL
    document_ids = job_data["document_ids"]
    file_paths = []
    temp_dir = None

    for doc_id in document_ids:
        doc = db.get_document_sync(sync_db_url, workspace_id, doc_id)
        if doc:
            if doc.get("metadata", {}).get("storage") == "minio":
                try:
                    from rrag_ingestion.services import object_store
                    if temp_dir is None:
                        temp_dir = tempfile.mkdtemp(prefix="rrag_job_")
                    local_path = os.path.join(temp_dir, doc_id, doc["filename"])
                    os.makedirs(os.path.dirname(local_path), exist_ok=True)
                    object_store.download_to_file(doc["file_path"], local_path)
                    file_paths.append(local_path)
                except Exception as e:
                    logger.warning(f"MinIO download failed for {doc_id}: {e}, trying local path")
                    if os.path.exists(doc["file_path"]):
                        file_paths.append(doc["file_path"])
                    else:
                        logger.warning(f"Document {doc_id} not found locally either, skipping")
            else:
                file_paths.append(doc["file_path"])
        else:
            logger.warning(f"Document {doc_id} not found in database, skipping")

    if not file_paths:
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)
        db.update_job_sync(
            sync_db_url, workspace_id, job_id,
            status="failed",
            errors=["No valid documents found"],
        )
        redis_conn.delete(progress_key)
        return {"error": "No valid documents"}

    initial_input = ComponentResult(data={
        "document_ids": document_ids,
        "file_paths": file_paths,
        "config_overrides": job_data.get("config_overrides", {}),
        "datastore_id": job_data.get("datastore_id") or "",
        "workspace_id": workspace_id,
    })

    # Checkpoint directory for intermediate results (enables resume)
    checkpoint_dir = Path(tempfile.gettempdir()) / "rrag_checkpoints" / job_id
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    # If resuming, try to load the last checkpoint
    if resume_from_step > 0:
        checkpoint_file = checkpoint_dir / f"step_{resume_from_step - 1}.json"
        if checkpoint_file.exists():
            import json as _json
            checkpoint_data = _json.loads(checkpoint_file.read_text())
            initial_input = ComponentResult(data=checkpoint_data.get("data", initial_input.data))
            logger.info(f"Resumed from checkpoint step {resume_from_step - 1}")

    def checkpoint_cb(step_index: int, result_data: dict) -> None:
        """Save intermediate result to disk after each successful step."""
        try:
            cp_file = checkpoint_dir / f"step_{step_index}.json"
            import json as _json
            cp_file.write_text(_json.dumps({"data": result_data}, default=str))
        except Exception as e:
            logger.debug(f"Checkpoint save failed for step {step_index}: {e}")

    result = asyncio.run(engine.execute(
        pipeline_def, initial_input, job_id, progress_cb, sub_progress_cb, step_start_cb,
        skip_steps=resume_from_step,
        checkpoint_callback=checkpoint_cb,
    ))

    # Clean up temp directory
    if temp_dir:
        shutil.rmtree(temp_dir, ignore_errors=True)

    job_elapsed = round((_time.monotonic() - job_start) * 1000, 2)

    if result.errors:
        db.update_job_sync(
            sync_db_url, workspace_id, job_id,
            status="failed",
            errors=result.errors,
            completed_at=datetime.now(timezone.utc).isoformat(),
            total_duration_ms=job_elapsed,
        )
    else:
        # Create or update DataStore from successful pipeline results
        existing_ds_id = job_data.get("datastore_id")
        pipe_step_configs = {s.component: s.config for s in pipeline_def.steps}
        datastore_id = db.create_datastore_from_results_sync(
            sync_db_url, workspace_id, job_id, pipeline_name, document_ids,
            accumulated_step_results,
            existing_datastore_id=existing_ds_id,
            pipeline_step_configs=pipe_step_configs,
        )
        db.update_job_sync(
            sync_db_url, workspace_id, job_id,
            status="completed",
            progress=100,
            completed_at=datetime.now(timezone.utc).isoformat(),
            total_duration_ms=job_elapsed,
            datastore_id=datastore_id,
        )

    # Clean up ephemeral progress from Redis
    redis_conn.delete(progress_key)

    # Clean up checkpoints on full success (keep on failure for resume)
    if not result.errors:
        shutil.rmtree(checkpoint_dir, ignore_errors=True)

    return {"status": "completed" if result.is_ok() else "failed"}


def _get_live_progress(redis_conn: Redis, key: str) -> dict:
    """Read current live progress from Redis, or return empty defaults."""
    raw = redis_conn.get(key)
    if raw:
        return json.loads(raw)
    return {
        "pipeline_steps": [],
        "total_steps": 0,
        "current_step": None,
        "progress": 0,
        "sub_progress": None,
        "step_results": [],
    }
