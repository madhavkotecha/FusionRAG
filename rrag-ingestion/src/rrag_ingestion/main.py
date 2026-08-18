import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis import Redis

from rrag_ingestion.config import settings
from rrag_ingestion.core.registry import ComponentRegistry
from rrag_ingestion.db import init_db
from rrag_ingestion.db.session import get_session_factory


registry = ComponentRegistry()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    os.makedirs(settings.storage_dir, exist_ok=True)
    registry.auto_discover()
    app.state.registry = registry
    app.state.redis = Redis.from_url(settings.redis_url)
    app.state.db_session_factory = get_session_factory()

    # Make Redis available to query_pipeline_store module
    from rrag_ingestion.services.query_pipeline_store import init_redis as _init_qp_redis
    _init_qp_redis(app.state.redis)

    # Initialize PostgreSQL tables
    await init_db()

    # Ensure MinIO bucket exists (non-fatal if MinIO is unavailable)
    try:
        from rrag_ingestion.services import object_store
        object_store.ensure_bucket()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"MinIO bucket init skipped: {e}")

    yield
    # Shutdown
    app.state.redis.close()


app = FastAPI(
    title="RRAG Ingestion Service",
    description="Modular RAG document ingestion with chainable components",
    version="0.1.0",
    lifespan=lifespan,
    redirect_slashes=False,
)

_cors_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key", "X-Request-ID"],
)


@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    return response


from rrag_ingestion.api.router import api_router  # noqa: E402

app.include_router(api_router, prefix="/api/v1/ingestion")


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "rrag-ingestion"}


@app.get("/health/llm")
async def health_llm():
    """Live readiness probe for the configured LLM inference backend (ADR-0018)."""
    from fastapi.responses import JSONResponse

    from rrag_ingestion.services import llm_service

    info = await llm_service.check_llm_health()
    ready = info.get("status") in ("ok", "configured")
    return JSONResponse(info, status_code=200 if ready else 503)
