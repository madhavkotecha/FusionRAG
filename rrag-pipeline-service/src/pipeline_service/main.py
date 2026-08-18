import logging
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis import Redis

from .api.router import api_router
from .config import settings

logger = logging.getLogger("pipeline_service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = Redis.from_url(settings.redis_url)

    # Bootstrap seed component files into MinIO (idempotent)
    try:
        from .database import async_session
        from .services.seed_bootstrap import bootstrap_seed_files

        async with async_session() as session:
            await bootstrap_seed_files(session)
    except Exception:
        logger.warning("Seed bootstrap skipped (DB or MinIO unavailable)", exc_info=True)

    yield
    app.state.redis.close()


app = FastAPI(
    title="RAG Pipeline Service",
    version="0.1.0",
    lifespan=lifespan,
    redirect_slashes=False,
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error(
        "Unhandled error on %s %s: %s\n%s",
        request.method,
        request.url.path,
        exc,
        traceback.format_exc(),
    )
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

# CORS: restrict to known origins; Traefik fronts this in production
_allowed_origins = settings.cors_origins.split(",") if settings.cors_origins else []
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(api_router)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    return response


@app.get("/health")
async def health():
    return {"status": "ok", "service": "pipeline-service", "version": "0.1.0"}
