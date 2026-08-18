from fastapi import APIRouter

from rrag_ingestion.api.admin import router as admin_router
from rrag_ingestion.api.chat import router as chat_router
from rrag_ingestion.api.publish import router as publish_router
from rrag_ingestion.api.components import router as components_router
from rrag_ingestion.api.datastores import router as datastores_router
from rrag_ingestion.api.documents import router as documents_router
from rrag_ingestion.api.jobs import router as jobs_router
from rrag_ingestion.api.knowledge_bases import router as kb_router
from rrag_ingestion.api.pipelines import router as pipelines_router
from rrag_ingestion.api.query_pipelines import router as query_pipelines_router

api_router = APIRouter()

api_router.include_router(documents_router, prefix="/documents", tags=["documents"])
api_router.include_router(components_router, prefix="/components", tags=["components"])
api_router.include_router(pipelines_router, prefix="/pipelines", tags=["pipelines"])
api_router.include_router(jobs_router, prefix="/jobs", tags=["jobs"])
api_router.include_router(datastores_router, prefix="/datastores", tags=["datastores"])
api_router.include_router(kb_router, prefix="/knowledge-bases", tags=["knowledge-bases"])
api_router.include_router(query_pipelines_router, prefix="/query-pipelines", tags=["query-pipelines"])
api_router.include_router(chat_router, prefix="/chat", tags=["chat"])
api_router.include_router(admin_router, prefix="/admin", tags=["admin"])
api_router.include_router(publish_router, prefix="/publish", tags=["publish"])
