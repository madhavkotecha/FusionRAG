"""Admin API endpoints for system administration."""
from __future__ import annotations

import asyncio
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from rrag_ingestion.config import settings
from rrag_ingestion.core.queue import get_queue, enqueue_pipeline_job
from rrag_ingestion.db import stores as db
from rrag_ingestion.dependencies import AuthContext, get_current_user

router = APIRouter()

# -- Models -----------------------------------------------------------

class SystemStatsResponse(BaseModel):
    totalJobs: int
    jobsByStatus: dict[str, int]
    totalDocuments: int
    totalDataStores: int
    totalPipelines: int
    totalQueryPipelines: int
    redisConnected: bool
    uptimeSeconds: float


class QueueStatsResponse(BaseModel):
    totalJobs: int
    queued: int
    running: int
    completed: int
    failed: int
    cancelled: int
    avgDurationMs: float | None
    recentThroughput: float | None  # jobs/hour over last hour
    oldestQueuedAge: float | None   # seconds


class ServiceHealth(BaseModel):
    name: str
    status: str  # healthy, degraded, down
    url: str
    responseTimeMs: float | None
    version: str | None
    details: dict[str, Any] | None


class HealthCheckResponse(BaseModel):
    overall: str  # healthy, degraded, down
    services: list[ServiceHealth]
    checkedAt: str


class SystemConfigResponse(BaseModel):
    llm: dict[str, Any]
    embedding: dict[str, Any]
    queue: dict[str, Any]
    storage: dict[str, Any]


class SystemConfigUpdate(BaseModel):
    defaultLlmModel: str | None = None
    defaultEmbeddingModel: str | None = None
    rqJobTimeout: int | None = None
    maxUploadSizeMb: int | None = None
    llmProvider: str | None = None
    openaiApiKey: str | None = None
    openaiBaseUrl: str | None = None
    ollamaBaseUrl: str | None = None
    vllmBaseUrl: str | None = None
    vllmApiKey: str | None = None

    def validate_values(self) -> list[str]:
        """Return list of validation errors."""
        errors: list[str] = []
        if self.rqJobTimeout is not None and self.rqJobTimeout <= 0:
            errors.append("rqJobTimeout must be a positive integer")
        if self.maxUploadSizeMb is not None and self.maxUploadSizeMb <= 0:
            errors.append("maxUploadSizeMb must be a positive integer")
        if self.defaultLlmModel is not None and not self.defaultLlmModel.strip():
            errors.append("defaultLlmModel cannot be empty")
        if self.defaultEmbeddingModel is not None and not self.defaultEmbeddingModel.strip():
            errors.append("defaultEmbeddingModel cannot be empty")
        if self.llmProvider is not None and self.llmProvider not in ("openai", "ollama", "vllm"):
            errors.append("llmProvider must be 'openai', 'ollama', or 'vllm'")
        if self.openaiBaseUrl is not None and self.openaiBaseUrl:
            if not self.openaiBaseUrl.startswith(("http://", "https://")):
                errors.append("openaiBaseUrl must start with http:// or https://")
        if self.ollamaBaseUrl is not None and self.ollamaBaseUrl:
            if not self.ollamaBaseUrl.startswith(("http://", "https://")):
                errors.append("ollamaBaseUrl must start with http:// or https://")
        if self.vllmBaseUrl is not None and self.vllmBaseUrl:
            if not self.vllmBaseUrl.startswith(("http://", "https://")):
                errors.append("vllmBaseUrl must start with http:// or https://")
        return errors


def _mask_api_key(key: str) -> str:
    """Mask an API key for display, showing only first 3 and last 4 chars."""
    if not key:
        return ""
    if len(key) <= 8:
        return "****"
    return f"{key[:3]}...{key[-4:]}"


class QueueActionRequest(BaseModel):
    action: str  # purge_failed, purge_completed, retry_all_failed, pause, resume


class QueueActionResponse(BaseModel):
    action: str
    affected: int
    message: str


# Track app startup time
_start_time = time.monotonic()


# -- System Stats -----------------------------------------------------

@router.get("/stats", response_model=SystemStatsResponse)
async def get_system_stats(
    request: Request,
    auth: AuthContext = Depends(get_current_user),
):
    """Aggregate system statistics across all services."""
    auth.require_org_admin()
    redis_conn = request.app.state.redis
    db_factory = request.app.state.db_session_factory

    # Use a temporary workspace_id="" to get all-workspace stats
    # For admin stats, query the DB directly
    from sqlalchemy import select, func
    from rrag_ingestion.db.models import DocumentRow, DataStoreRow, JobRow, QueryPipelineRow

    async with db_factory() as session:
        # Jobs
        job_rows = (await session.execute(select(JobRow))).scalars().all()
        jobs_by_status: dict[str, int] = {}
        for j in job_rows:
            jobs_by_status[j.status] = jobs_by_status.get(j.status, 0) + 1

        # Documents
        doc_count = (await session.execute(select(func.count(DocumentRow.id)))).scalar() or 0

        # DataStores
        ds_count = (await session.execute(select(func.count(DataStoreRow.id)))).scalar() or 0

        # Query Pipelines
        qp_count = (await session.execute(select(func.count(QueryPipelineRow.id)))).scalar() or 0

    # Pipelines (file-based)
    from pathlib import Path
    pipelines_dir = Path(settings.configs_dir) / "pipelines"
    pipeline_count = 0
    if pipelines_dir.exists():
        pipeline_count = len(list(pipelines_dir.rglob("*.yaml")))

    # Redis connectivity
    try:
        redis_conn.ping()
        redis_ok = True
    except Exception:
        redis_ok = False

    return SystemStatsResponse(
        totalJobs=len(job_rows),
        jobsByStatus=jobs_by_status,
        totalDocuments=doc_count,
        totalDataStores=ds_count,
        totalPipelines=pipeline_count,
        totalQueryPipelines=qp_count,
        redisConnected=redis_ok,
        uptimeSeconds=round(time.monotonic() - _start_time, 1),
    )


# -- Queue Stats ------------------------------------------------------

@router.get("/queue/stats", response_model=QueueStatsResponse)
async def get_queue_stats(
    request: Request,
    auth: AuthContext = Depends(get_current_user),
):
    """Detailed queue statistics."""
    auth.require_org_admin()
    db_factory = request.app.state.db_session_factory
    from sqlalchemy import select
    from rrag_ingestion.db.models import JobRow
    async with db_factory() as session:
        rows = (await session.execute(select(JobRow))).scalars().all()
    jobs = [db._job_row_to_dict(r) for r in rows]

    by_status: dict[str, int] = {"queued": 0, "running": 0, "completed": 0, "failed": 0, "cancelled": 0}
    durations: list[float] = []
    recent_completed = 0
    hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    oldest_queued_at: datetime | None = None

    for j in jobs:
        st = j.get("status", "unknown")
        by_status[st] = by_status.get(st, 0) + 1

        dur = j.get("total_duration_ms")
        if dur is not None:
            durations.append(dur)

        # Recent throughput
        completed_at = j.get("completed_at")
        if completed_at and st == "completed":
            try:
                ct = datetime.fromisoformat(completed_at)
                if ct > hour_ago:
                    recent_completed += 1
            except Exception:
                pass

        # Oldest queued job
        if st == "queued":
            created = j.get("created_at")
            if created:
                try:
                    ct = datetime.fromisoformat(created)
                    if oldest_queued_at is None or ct < oldest_queued_at:
                        oldest_queued_at = ct
                except Exception:
                    pass

    avg_dur = round(sum(durations) / len(durations), 1) if durations else None
    oldest_age = (
        round((datetime.now(timezone.utc) - oldest_queued_at).total_seconds(), 1)
        if oldest_queued_at
        else None
    )

    return QueueStatsResponse(
        totalJobs=len(jobs),
        queued=by_status["queued"],
        running=by_status["running"],
        completed=by_status["completed"],
        failed=by_status["failed"],
        cancelled=by_status.get("cancelled", 0),
        avgDurationMs=avg_dur,
        recentThroughput=float(recent_completed) if recent_completed > 0 else None,
        oldestQueuedAge=oldest_age,
    )


# -- Queue Actions ----------------------------------------------------

@router.post("/queue/actions", response_model=QueueActionResponse)
async def queue_action(
    body: QueueActionRequest,
    request: Request,
    auth: AuthContext = Depends(get_current_user),
):
    """Admin queue operations: purge, retry failed, etc."""
    auth.require_org_admin()
    redis_conn = request.app.state.redis
    db_factory = request.app.state.db_session_factory

    from sqlalchemy import select, delete as sa_delete
    from rrag_ingestion.db.models import JobRow

    affected = 0

    if body.action == "purge_failed":
        async with db_factory() as session:
            result = await session.execute(sa_delete(JobRow).where(JobRow.status == "failed"))
            affected = result.rowcount
            await session.commit()
        return QueueActionResponse(action=body.action, affected=affected, message=f"Purged {affected} failed jobs")

    elif body.action == "purge_completed":
        async with db_factory() as session:
            result = await session.execute(sa_delete(JobRow).where(JobRow.status == "completed"))
            affected = result.rowcount
            await session.commit()
        return QueueActionResponse(action=body.action, affected=affected, message=f"Purged {affected} completed jobs")

    elif body.action == "retry_all_failed":
        async with db_factory() as session:
            rows = (await session.execute(select(JobRow).where(JobRow.status == "failed"))).scalars().all()
            for j in rows:
                await enqueue_pipeline_job(
                    session=session,
                    redis_conn=redis_conn,
                    pipeline_name=j.pipeline_name,
                    document_ids=j.document_ids or [],
                    config_overrides=j.config_overrides,
                    datastore_id=j.datastore_id,
                    workspace_id=j.workspace_id,
                )
                affected += 1
        return QueueActionResponse(action=body.action, affected=affected, message=f"Retrying {affected} failed jobs")

    elif body.action == "purge_all":
        async with db_factory() as session:
            result = await session.execute(
                sa_delete(JobRow).where(JobRow.status.in_(["completed", "failed", "cancelled"]))
            )
            affected = result.rowcount
            await session.commit()
        return QueueActionResponse(action=body.action, affected=affected, message=f"Purged {affected} finished jobs")

    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {body.action}")


# -- Service Health ---------------------------------------------------

async def _check_service(name: str, url: str) -> ServiceHealth:
    """Check a single service's health endpoint."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            start = time.monotonic()
            resp = await client.get(url)
            elapsed = round((time.monotonic() - start) * 1000, 1)
            data: dict | None = None
            try:
                data = resp.json()
                if not isinstance(data, dict):
                    data = None
            except Exception:
                pass
            status = "healthy" if resp.status_code == 200 else "degraded"
            # OpenSearch cluster health: yellow (single-node) is acceptable
            if data and data.get("status") == "yellow":
                status = "healthy"
            return ServiceHealth(
                name=name,
                status=status,
                url=url,
                responseTimeMs=elapsed,
                version=data.get("version") if data else None,
                details=data if data else {"status": resp.text[:200]} if resp.status_code == 200 else None,
            )
    except Exception as e:
        return ServiceHealth(
            name=name,
            status="down",
            url=url,
            responseTimeMs=None,
            version=None,
            details={"error": str(e)},
        )


@router.get("/health", response_model=HealthCheckResponse)
async def check_all_health(
    request: Request,
    auth: AuthContext = Depends(get_current_user),
):
    """Check health of all platform services and dependencies."""
    auth.require_org_admin()
    redis_conn = request.app.state.redis

    services_to_check = [
        ("Ingestion Service", "http://localhost:8001/health"),
        ("Pipeline Service", f"{os.environ.get('PIPELINE_SERVICE_URL', 'http://pipeline-service:8080')}/health"),
        ("Auth Server", f"{os.environ.get('AUTH_SERVER_URL', 'http://auth-server:3000')}/health"),
        ("Keycloak", f"{os.environ.get('KEYCLOAK_HEALTH_URL', 'http://keycloak:9000')}/health/ready"),
        ("MinIO", f"http://{settings.minio_endpoint}/minio/health/ready"),
        ("OpenSearch", f"http://{settings.opensearch_host}:{settings.opensearch_port}/_cluster/health"),
        ("Qdrant", f"{settings.qdrant_url}/healthz"),
    ]

    # Check services concurrently
    results = await asyncio.gather(
        *[_check_service(name, url) for name, url in services_to_check],
        return_exceptions=True,
    )

    services: list[ServiceHealth] = []
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            svc_name, svc_url = services_to_check[i]
            services.append(ServiceHealth(
                name=svc_name, status="down", url=svc_url,
                responseTimeMs=None, version=None,
                details={"error": str(r)},
            ))
        else:
            services.append(r)

    # Check Redis
    try:
        redis_start = time.monotonic()
        redis_conn.ping()
        redis_ms = round((time.monotonic() - redis_start) * 1000, 1)
        info = redis_conn.info("server")
        services.append(ServiceHealth(
            name="Redis",
            status="healthy",
            url=settings.redis_url,
            responseTimeMs=redis_ms,
            version=info.get("redis_version"),
            details={
                "connectedClients": redis_conn.info("clients").get("connected_clients"),
                "usedMemoryHuman": redis_conn.info("memory").get("used_memory_human"),
            },
        ))
    except Exception as e:
        services.append(ServiceHealth(
            name="Redis", status="down", url=settings.redis_url,
            responseTimeMs=None, version=None, details={"error": str(e)},
        ))

    # Check PostgreSQL
    pg_url = settings.database_url.replace("+asyncpg", "").split("@")[-1].split("/")[0] if "@" in settings.database_url else "localhost:5432"
    try:
        import asyncpg  # noqa: F811
        dsn = settings.database_url.replace("+asyncpg", "").replace("postgresql://", "postgresql://")
        pg_start = time.monotonic()
        conn = await asyncpg.connect(dsn, timeout=5)
        pg_version = await conn.fetchval("SELECT version()")
        await conn.close()
        pg_ms = round((time.monotonic() - pg_start) * 1000, 1)
        services.append(ServiceHealth(
            name="PostgreSQL",
            status="healthy",
            url=pg_url,
            responseTimeMs=pg_ms,
            version=pg_version.split(",")[0] if pg_version else None,
            details=None,
        ))
    except Exception as e:
        services.append(ServiceHealth(
            name="PostgreSQL", status="down", url=pg_url,
            responseTimeMs=None, version=None, details={"error": str(e)},
        ))

    # Check Neo4j
    neo4j_uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    try:
        from neo4j import AsyncGraphDatabase
        neo4j_start = time.monotonic()
        driver = AsyncGraphDatabase.driver(
            neo4j_uri,
            auth=(
                os.environ.get("NEO4J_USERNAME", "neo4j"),
                os.environ["NEO4J_PASSWORD"],
            ),
        )
        async with driver.session() as session:
            result = await session.run("CALL dbms.components() YIELD name, versions RETURN name, versions[0] AS version")
            record = await result.single()
            neo4j_version = record["version"] if record else None
        await driver.close()
        neo4j_ms = round((time.monotonic() - neo4j_start) * 1000, 1)
        services.append(ServiceHealth(
            name="Neo4j",
            status="healthy",
            url=neo4j_uri,
            responseTimeMs=neo4j_ms,
            version=neo4j_version,
            details=None,
        ))
    except Exception as e:
        services.append(ServiceHealth(
            name="Neo4j", status="down", url=neo4j_uri,
            responseTimeMs=None, version=None, details={"error": str(e)},
        ))

    # Determine overall status
    statuses = [s.status for s in services]
    if all(s == "healthy" for s in statuses):
        overall = "healthy"
    elif any(s == "down" for s in statuses):
        overall = "degraded"
    else:
        overall = "degraded"

    return HealthCheckResponse(
        overall=overall,
        services=services,
        checkedAt=datetime.now(timezone.utc).isoformat(),
    )


# -- System Configuration ---------------------------------------------

@router.get("/config", response_model=SystemConfigResponse)
async def get_system_config(
    auth: AuthContext = Depends(get_current_user),
):
    """Get current system configuration (non-sensitive)."""
    auth.require_org_admin()
    has_key = bool(settings.openai_api_key or os.environ.get("OPENAI_API_KEY"))
    if settings.openai_api_key:
        key_display = _mask_api_key(settings.openai_api_key)
    elif os.environ.get("OPENAI_API_KEY"):
        key_display = "Configured via environment"
    else:
        key_display = ""
    vllm_key = settings.vllm_api_key
    vllm_key_display = _mask_api_key(vllm_key) if vllm_key and vllm_key != "EMPTY" else ""
    return SystemConfigResponse(
        llm={
            "defaultModel": settings.default_llm_model,
            "hasApiKey": has_key,
            "provider": settings.llm_provider,
            "openaiBaseUrl": settings.openai_base_url,
            "ollamaBaseUrl": settings.ollama_base_url,
            "apiKeyDisplay": key_display,
            "vllmBaseUrl": settings.vllm_base_url,
            "vllmApiKeyDisplay": vllm_key_display,
        },
        embedding={
            "defaultModel": settings.default_embedding_model,
        },
        queue={
            "name": settings.rq_queue_name,
            "jobTimeout": settings.rq_job_timeout,
            "redisUrl": settings.redis_url.rsplit("@", 1)[-1] if "@" in settings.redis_url else settings.redis_url,
        },
        storage={
            "storageDir": settings.storage_dir,
            "configsDir": settings.configs_dir,
            "maxUploadSizeMb": settings.max_upload_size_mb,
        },
    )


@router.put("/config")
async def update_system_config(
    body: SystemConfigUpdate,
    auth: AuthContext = Depends(get_current_user),
):
    """Update mutable system configuration."""
    auth.require_org_admin()
    validation_errors = body.validate_values()
    if validation_errors:
        raise HTTPException(status_code=422, detail="; ".join(validation_errors))

    updated: dict[str, Any] = {}
    if body.defaultLlmModel is not None:
        settings.default_llm_model = body.defaultLlmModel
        updated["defaultLlmModel"] = body.defaultLlmModel
    if body.defaultEmbeddingModel is not None:
        settings.default_embedding_model = body.defaultEmbeddingModel
        updated["defaultEmbeddingModel"] = body.defaultEmbeddingModel
    if body.rqJobTimeout is not None:
        settings.rq_job_timeout = body.rqJobTimeout
        updated["rqJobTimeout"] = body.rqJobTimeout
    if body.maxUploadSizeMb is not None:
        settings.max_upload_size_mb = body.maxUploadSizeMb
        updated["maxUploadSizeMb"] = body.maxUploadSizeMb
    if body.llmProvider is not None:
        settings.llm_provider = body.llmProvider
        updated["llmProvider"] = body.llmProvider
    if body.openaiApiKey is not None:
        settings.openai_api_key = body.openaiApiKey
        os.environ["OPENAI_API_KEY"] = body.openaiApiKey
        updated["openaiApiKey"] = "***"
    if body.openaiBaseUrl is not None:
        settings.openai_base_url = body.openaiBaseUrl
        updated["openaiBaseUrl"] = body.openaiBaseUrl
    if body.ollamaBaseUrl is not None:
        settings.ollama_base_url = body.ollamaBaseUrl
        updated["ollamaBaseUrl"] = body.ollamaBaseUrl
    if body.vllmBaseUrl is not None:
        settings.vllm_base_url = body.vllmBaseUrl
        updated["vllmBaseUrl"] = body.vllmBaseUrl
    if body.vllmApiKey is not None:
        settings.vllm_api_key = body.vllmApiKey
        updated["vllmApiKey"] = "***"

    if not updated:
        raise HTTPException(status_code=400, detail="No configuration changes provided")

    return {"updated": updated, "message": "Configuration updated successfully"}


# -- Recent Jobs Timeline ---------------------------------------------

@router.get("/queue/timeline")
async def get_queue_timeline(
    request: Request,
    auth: AuthContext = Depends(get_current_user),
    hours: int = 24,
):
    """Get job completion timeline for charting."""
    auth.require_org_admin()
    db_factory = request.app.state.db_session_factory
    from sqlalchemy import select
    from rrag_ingestion.db.models import JobRow
    async with db_factory() as session:
        rows = (await session.execute(select(JobRow))).scalars().all()
    jobs = [db._job_row_to_dict(r) for r in rows]
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    # Bucket by hour
    buckets: dict[str, dict[str, int]] = {}
    for j in jobs:
        completed_at = j.get("completed_at") or j.get("created_at")
        if not completed_at:
            continue
        try:
            ts = datetime.fromisoformat(completed_at)
        except Exception:
            continue
        if ts < cutoff:
            continue
        hour_key = ts.strftime("%Y-%m-%dT%H:00:00")
        if hour_key not in buckets:
            buckets[hour_key] = {"completed": 0, "failed": 0, "created": 0}
        status = j.get("status", "unknown")
        if status == "completed":
            buckets[hour_key]["completed"] += 1
        elif status == "failed":
            buckets[hour_key]["failed"] += 1
        buckets[hour_key]["created"] += 1

    timeline = [{"hour": k, **v} for k, v in sorted(buckets.items())]
    return {"timeline": timeline, "hours": hours}
