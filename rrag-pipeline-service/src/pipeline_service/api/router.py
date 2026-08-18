from fastapi import APIRouter

from .admin_components import router as admin_components_router
from .component_upload import router as component_upload_router
from .components import router as components_router
from .pipeline_run_stream import router as stream_router
from .pipeline_runs import router as runs_router
from .pipelines import router as pipelines_router
from .templates import router as templates_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(pipelines_router, prefix="/pipelines", tags=["pipelines"])
api_router.include_router(runs_router, tags=["runs"])
api_router.include_router(stream_router, tags=["pipeline-runs"])
api_router.include_router(components_router, prefix="/components", tags=["components"])
api_router.include_router(
    component_upload_router, prefix="/components", tags=["components"]
)
api_router.include_router(templates_router, prefix="/templates", tags=["templates"])
api_router.include_router(admin_components_router)
