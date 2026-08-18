"""CRUD API for QueryPipelines."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from rrag_ingestion.dependencies import AuthContext, get_current_user
from rrag_ingestion.models.query_pipeline import (
    AgentConfig,
    GeneratorConfig,
    PlannerConfig,
    QueryPipeline,
    RerankerConfig,
    RetrieverConfig,
    query_pipeline_to_tool,
)
from rrag_ingestion.services.query_pipeline_store import (
    create_query_pipeline,
    delete_query_pipeline,
    get_query_pipeline,
    list_query_pipelines,
    update_query_pipeline,
)

router = APIRouter()


class CreateQueryPipelineRequest(BaseModel):
    id: str | None = Field(None, description="Optional ID; auto-generated if omitted")
    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    datastore_id: str = Field(..., min_length=1)
    retrieval_strategy: str = Field("auto")
    retriever: RetrieverConfig = Field(default_factory=RetrieverConfig)
    reranker: RerankerConfig = Field(default_factory=RerankerConfig)
    generator: GeneratorConfig = Field(default_factory=GeneratorConfig)
    planner: PlannerConfig = Field(default_factory=PlannerConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    definition: dict | None = None


class UpdateQueryPipelineRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    datastore_id: str | None = None
    retrieval_strategy: str | None = None
    retriever: RetrieverConfig | None = None
    reranker: RerankerConfig | None = None
    generator: GeneratorConfig | None = None
    planner: PlannerConfig | None = None
    agent: AgentConfig | None = None
    definition: dict | None = None


@router.post("", response_model=QueryPipeline, status_code=201)
async def create(
    req: CreateQueryPipelineRequest,
    request: Request,
    workspace_id: str = Query(..., description="Workspace ID"),
    auth: AuthContext = Depends(get_current_user),
):
    """Create a new query pipeline."""
    auth.require_workspace_role(workspace_id, "developer")
    pipeline = await create_query_pipeline(workspace_id, req.model_dump())
    return pipeline


@router.get("", response_model=dict)
async def list_all(
    request: Request,
    workspace_id: str = Query(..., description="Workspace ID"),
    auth: AuthContext = Depends(get_current_user),
):
    """List all query pipelines."""
    auth.require_workspace_role(workspace_id, "viewer")
    pipelines = await list_query_pipelines(workspace_id)
    return {"query_pipelines": [p.model_dump() for p in pipelines]}


@router.get("/{pipeline_id}", response_model=QueryPipeline)
async def get(
    pipeline_id: str,
    request: Request,
    workspace_id: str = Query(..., description="Workspace ID"),
    auth: AuthContext = Depends(get_current_user),
):
    """Get a query pipeline by ID."""
    auth.require_workspace_role(workspace_id, "viewer")
    pipeline = await get_query_pipeline(workspace_id, pipeline_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Query pipeline not found")
    return pipeline


@router.get("/{pipeline_id}/tool-schema")
async def get_tool_schema(
    pipeline_id: str,
    request: Request,
    workspace_id: str = Query(..., description="Workspace ID"),
    auth: AuthContext = Depends(get_current_user),
):
    """Get the auto-generated tool schema for this query pipeline."""
    auth.require_workspace_role(workspace_id, "viewer")
    pipeline = await get_query_pipeline(workspace_id, pipeline_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Query pipeline not found")
    return query_pipeline_to_tool(pipeline)


@router.put("/{pipeline_id}", response_model=QueryPipeline)
async def update(
    pipeline_id: str,
    req: UpdateQueryPipelineRequest,
    request: Request,
    workspace_id: str = Query(..., description="Workspace ID"),
    auth: AuthContext = Depends(get_current_user),
):
    """Update a query pipeline."""
    auth.require_workspace_role(workspace_id, "developer")
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")
    pipeline = await update_query_pipeline(workspace_id, pipeline_id, updates)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Query pipeline not found")
    return pipeline


@router.delete("/{pipeline_id}")
async def delete(
    pipeline_id: str,
    request: Request,
    workspace_id: str = Query(..., description="Workspace ID"),
    auth: AuthContext = Depends(get_current_user),
):
    """Delete a query pipeline."""
    auth.require_workspace_role(workspace_id, "developer")
    if not await delete_query_pipeline(workspace_id, pipeline_id):
        raise HTTPException(status_code=404, detail="Query pipeline not found")
    return {"status": "deleted"}
