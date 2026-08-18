from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from rrag_ingestion.db import stores as db
from rrag_ingestion.dependencies import AuthContext, get_current_user

router = APIRouter()


class DataStoreCreateRequest(BaseModel):
    name: str
    description: str = ""


@router.post("")
async def create_datastore_endpoint(
    body: DataStoreCreateRequest,
    request: Request,
    workspace_id: str = Query(..., description="Workspace ID"),
    auth: AuthContext = Depends(get_current_user),
):
    auth.require_workspace_role(workspace_id, "developer")
    async with request.app.state.db_session_factory() as session:
        ds = await db.create_datastore(session, workspace_id, name=body.name, description=body.description, redis=request.app.state.redis)
    return ds


@router.get("")
async def list_all_datastores(
    request: Request,
    workspace_id: str = Query(..., description="Workspace ID"),
    auth: AuthContext = Depends(get_current_user),
):
    auth.require_workspace_role(workspace_id, "viewer")
    async with request.app.state.db_session_factory() as session:
        stores = await db.list_datastores(session, workspace_id, redis=request.app.state.redis)
    return {"datastores": stores}


@router.get("/{datastore_id}")
async def get_datastore_detail(
    datastore_id: str,
    request: Request,
    workspace_id: str = Query(..., description="Workspace ID"),
    auth: AuthContext = Depends(get_current_user),
):
    auth.require_workspace_role(workspace_id, "viewer")
    async with request.app.state.db_session_factory() as session:
        store = await db.get_datastore(session, workspace_id, datastore_id, redis=request.app.state.redis)
    if not store:
        raise HTTPException(status_code=404, detail="DataStore not found")
    return store


@router.get("/{datastore_id}/strategies")
async def get_datastore_strategies(
    datastore_id: str,
    request: Request,
    workspace_id: str = Query(..., description="Workspace ID"),
    auth: AuthContext = Depends(get_current_user),
):
    """Return available retrieval strategies based on the DataStore's targets."""
    auth.require_workspace_role(workspace_id, "viewer")
    async with request.app.state.db_session_factory() as session:
        store = await db.get_datastore(session, workspace_id, datastore_id, redis=request.app.state.redis)
    if not store:
        raise HTTPException(status_code=404, detail="DataStore not found")

    targets = store.get("targets", [])
    has_vector = any(t["type"] == "vector" for t in targets)
    has_graph = any(t["type"] == "graph" for t in targets)

    vector_backend = next((t["backend"] for t in targets if t["type"] == "vector"), None)
    graph_backend = next((t["backend"] for t in targets if t["type"] == "graph"), None)

    strategies = []
    if has_vector or has_graph:
        strategies.append({"id": "auto", "label": "Auto", "description": "Use all available backends", "available": True})
    if has_vector:
        strategies.append({"id": "vector", "label": "Vector Search", "backend": vector_backend, "available": True})
        if vector_backend == "opensearch":
            strategies.append({"id": "hybrid_search", "label": "Hybrid Search", "backend": "opensearch", "description": "kNN + BM25 with RRF fusion", "available": True})
    if has_graph:
        strategies.append({"id": "graph", "label": "Knowledge Graph", "backend": graph_backend, "available": True})
    if has_vector and has_graph:
        strategies.append({"id": "hybrid", "label": "Hybrid", "description": "Vector + Graph combined", "available": True})

    return {"strategies": strategies}


@router.delete("/{datastore_id}")
async def delete_datastore_endpoint(
    datastore_id: str,
    request: Request,
    workspace_id: str = Query(..., description="Workspace ID"),
    auth: AuthContext = Depends(get_current_user),
):
    auth.require_workspace_role(workspace_id, "developer")
    async with request.app.state.db_session_factory() as session:
        deleted = await db.delete_datastore(session, workspace_id, datastore_id, redis=request.app.state.redis)
    if not deleted:
        raise HTTPException(status_code=404, detail="DataStore not found")
    return {"deleted": datastore_id}
