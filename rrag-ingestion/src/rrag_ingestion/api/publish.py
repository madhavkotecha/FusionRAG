from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import select, delete as sa_delete

from rrag_ingestion.db.models import PublishedEndpointRow
from rrag_ingestion.dependencies import AuthContext, get_current_user

router = APIRouter()


class PublishRequest(BaseModel):
    name: str
    slug: str
    datastore_id: str
    query_pipeline_id: str
    description: str = ""


class QueryRequest(BaseModel):
    query: str
    top_k: int = 5


def _row_to_dict(row: PublishedEndpointRow) -> dict:
    return {
        "id": row.id,
        "slug": row.slug,
        "name": row.name,
        "description": row.description,
        "datastore_id": row.datastore_id,
        "query_pipeline_id": row.query_pipeline_id,
        "api_key": row.api_key,
        "workspace_id": row.workspace_id,
        "status": row.status,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.post("")
async def publish_endpoint(
    body: PublishRequest,
    request: Request,
    workspace_id: str = Query(...),
    auth: AuthContext = Depends(get_current_user),
):
    """Publish a Knowledge Store + Query Pipeline as a queryable API endpoint."""
    auth.require_workspace_role(workspace_id, "developer")

    api_key = "rrag_" + str(uuid.uuid4()).replace("-", "")[:28]

    row = PublishedEndpointRow(
        id=str(uuid.uuid4()),
        workspace_id=workspace_id,
        slug=body.slug,
        name=body.name,
        description=body.description,
        datastore_id=body.datastore_id,
        query_pipeline_id=body.query_pipeline_id,
        api_key=api_key,
        status="active",
    )

    async with request.app.state.db_session_factory() as session:
        # Check slug uniqueness
        existing = await session.execute(
            select(PublishedEndpointRow).where(PublishedEndpointRow.slug == body.slug)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail=f"Slug '{body.slug}' is already taken")

        session.add(row)
        await session.commit()
        await session.refresh(row)

    return _row_to_dict(row)


@router.get("")
async def list_published(
    request: Request,
    workspace_id: str = Query(...),
    auth: AuthContext = Depends(get_current_user),
):
    """List published endpoints for the workspace."""
    auth.require_workspace_role(workspace_id, "viewer")
    async with request.app.state.db_session_factory() as session:
        result = await session.execute(
            select(PublishedEndpointRow)
            .where(PublishedEndpointRow.workspace_id == workspace_id)
            .order_by(PublishedEndpointRow.created_at.desc())
        )
        rows = result.scalars().all()
    return {"endpoints": [_row_to_dict(r) for r in rows]}


@router.delete("/{endpoint_id}")
async def delete_published(
    endpoint_id: str,
    request: Request,
    workspace_id: str = Query(...),
    auth: AuthContext = Depends(get_current_user),
):
    """Delete a published endpoint."""
    auth.require_workspace_role(workspace_id, "developer")
    async with request.app.state.db_session_factory() as session:
        result = await session.execute(
            sa_delete(PublishedEndpointRow)
            .where(PublishedEndpointRow.id == endpoint_id)
            .where(PublishedEndpointRow.workspace_id == workspace_id)
        )
        await session.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Endpoint not found")
    return {"deleted": endpoint_id}


@router.patch("/{endpoint_id}")
async def update_published(
    endpoint_id: str,
    request: Request,
    workspace_id: str = Query(...),
    auth: AuthContext = Depends(get_current_user),
):
    """Toggle endpoint status (active/disabled)."""
    auth.require_workspace_role(workspace_id, "developer")
    body = await request.json()
    async with request.app.state.db_session_factory() as session:
        result = await session.execute(
            select(PublishedEndpointRow)
            .where(PublishedEndpointRow.id == endpoint_id)
            .where(PublishedEndpointRow.workspace_id == workspace_id)
        )
        row = result.scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="Endpoint not found")
        if "status" in body:
            row.status = body["status"]
        await session.commit()
        await session.refresh(row)
    return _row_to_dict(row)


@router.post("/{slug}/query")
async def query_published(
    slug: str,
    body: QueryRequest,
    request: Request,
    authorization: str | None = Header(None),
):
    """Public query endpoint for published Knowledge Store + Pipeline.

    Authenticated via API key in the Authorization header (Bearer <key>).
    This endpoint bypasses JWT auth via Traefik routing.
    """
    # Look up from DB
    async with request.app.state.db_session_factory() as session:
        result = await session.execute(
            select(PublishedEndpointRow).where(PublishedEndpointRow.slug == slug)
        )
        published = result.scalar_one_or_none()

    if not published:
        raise HTTPException(status_code=404, detail=f"Published endpoint '{slug}' not found")

    if published.status != "active":
        raise HTTPException(status_code=403, detail="This endpoint is currently disabled")

    # Validate API key (always required)
    if not authorization:
        raise HTTPException(status_code=401, detail="API key required. Pass Authorization: Bearer <api_key>")

    token = authorization.replace("Bearer ", "").strip()
    if token != published.api_key:
        raise HTTPException(status_code=403, detail="Invalid API key")

    # TODO: Execute the actual query pipeline against the datastore
    return {
        "answer": f"Published endpoint '{published.name}' received query: {body.query}. "
                  f"This would query datastore '{published.datastore_id}' "
                  f"using pipeline '{published.query_pipeline_id}' with top_k={body.top_k}.",
        "sources": [],
        "pipeline": slug,
        "datastore_id": published.datastore_id,
        "query_pipeline_id": published.query_pipeline_id,
        "top_k": body.top_k,
    }
