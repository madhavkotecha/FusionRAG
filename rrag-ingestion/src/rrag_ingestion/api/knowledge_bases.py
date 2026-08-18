from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from rrag_ingestion.db import stores as db
from rrag_ingestion.dependencies import AuthContext, get_current_user

router = APIRouter()


# ── Request models ──────────────────────────────────────────────────────


class KBCreateRequest(BaseModel):
    name: str
    description: str = ""
    embedding_model: str = "text-embedding-3-small"
    embedding_provider: str = "openai"
    chunk_strategy: str = "recursive"
    chunk_size: int = 512
    chunk_overlap: int = 50
    retrieval_config: dict = {}


class KBUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    embedding_model: str | None = None
    embedding_provider: str | None = None
    chunk_strategy: str | None = None
    chunk_size: int | None = None
    chunk_overlap: int | None = None
    retrieval_config: dict | None = None


class KBDocumentUploadRequest(BaseModel):
    filename: str
    file_path: str
    source_type: str = "upload"
    content_type: str = ""
    metadata: dict = {}


class KBSegmentPatchRequest(BaseModel):
    enabled: bool | None = None
    status: str | None = None
    keywords: list | None = None


# ── Knowledge Base CRUD ─────────────────────────────────────────────────


@router.post("")
async def create_knowledge_base(
    body: KBCreateRequest,
    request: Request,
    workspace_id: str = Query(..., description="Workspace ID"),
    auth: AuthContext = Depends(get_current_user),
):
    auth.require_workspace_role(workspace_id, "developer")
    async with request.app.state.db_session_factory() as session:
        kb = await db.create_knowledge_base(
            session, workspace_id, body.model_dump(), redis=request.app.state.redis
        )
    return kb


@router.get("")
async def list_knowledge_bases(
    request: Request,
    workspace_id: str = Query(..., description="Workspace ID"),
    auth: AuthContext = Depends(get_current_user),
):
    auth.require_workspace_role(workspace_id, "viewer")
    async with request.app.state.db_session_factory() as session:
        kbs = await db.list_knowledge_bases(session, workspace_id, redis=request.app.state.redis)
    return {"knowledge_bases": kbs}


@router.get("/{kb_id}")
async def get_knowledge_base(
    kb_id: str,
    request: Request,
    workspace_id: str = Query(..., description="Workspace ID"),
    auth: AuthContext = Depends(get_current_user),
):
    auth.require_workspace_role(workspace_id, "viewer")
    async with request.app.state.db_session_factory() as session:
        kb = await db.get_knowledge_base(session, workspace_id, kb_id, redis=request.app.state.redis)
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    return kb


@router.put("/{kb_id}")
async def update_knowledge_base(
    kb_id: str,
    body: KBUpdateRequest,
    request: Request,
    workspace_id: str = Query(..., description="Workspace ID"),
    auth: AuthContext = Depends(get_current_user),
):
    auth.require_workspace_role(workspace_id, "developer")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")
    async with request.app.state.db_session_factory() as session:
        kb = await db.update_knowledge_base(
            session, workspace_id, kb_id, updates, redis=request.app.state.redis
        )
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    return kb


@router.delete("/{kb_id}")
async def delete_knowledge_base(
    kb_id: str,
    request: Request,
    workspace_id: str = Query(..., description="Workspace ID"),
    auth: AuthContext = Depends(get_current_user),
):
    auth.require_workspace_role(workspace_id, "developer")
    async with request.app.state.db_session_factory() as session:
        deleted = await db.delete_knowledge_base(
            session, workspace_id, kb_id, redis=request.app.state.redis
        )
    if not deleted:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    return {"deleted": kb_id}


# ── KB Documents ────────────────────────────────────────────────────────


@router.post("/{kb_id}/documents")
async def upload_kb_document(
    kb_id: str,
    body: KBDocumentUploadRequest,
    request: Request,
    workspace_id: str = Query(..., description="Workspace ID"),
    auth: AuthContext = Depends(get_current_user),
):
    auth.require_workspace_role(workspace_id, "developer")
    # Verify KB exists and belongs to workspace
    async with request.app.state.db_session_factory() as session:
        kb = await db.get_knowledge_base(session, workspace_id, kb_id, redis=request.app.state.redis)
        if not kb:
            raise HTTPException(status_code=404, detail="Knowledge base not found")
        doc = await db.create_kb_document(
            session, kb_id, body.model_dump(), redis=request.app.state.redis
        )
    return doc


@router.get("/{kb_id}/documents")
async def list_kb_documents(
    kb_id: str,
    request: Request,
    workspace_id: str = Query(..., description="Workspace ID"),
    auth: AuthContext = Depends(get_current_user),
):
    auth.require_workspace_role(workspace_id, "viewer")
    async with request.app.state.db_session_factory() as session:
        kb = await db.get_knowledge_base(session, workspace_id, kb_id, redis=request.app.state.redis)
        if not kb:
            raise HTTPException(status_code=404, detail="Knowledge base not found")
        docs = await db.list_kb_documents(session, kb_id, redis=request.app.state.redis)
    return {"documents": docs}


@router.delete("/{kb_id}/documents/{doc_id}")
async def delete_kb_document(
    kb_id: str,
    doc_id: str,
    request: Request,
    workspace_id: str = Query(..., description="Workspace ID"),
    auth: AuthContext = Depends(get_current_user),
):
    auth.require_workspace_role(workspace_id, "developer")
    async with request.app.state.db_session_factory() as session:
        kb = await db.get_knowledge_base(session, workspace_id, kb_id, redis=request.app.state.redis)
        if not kb:
            raise HTTPException(status_code=404, detail="Knowledge base not found")
        deleted = await db.delete_kb_document(session, kb_id, doc_id, redis=request.app.state.redis)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"deleted": doc_id}


# ── KB Segments ─────────────────────────────────────────────────────────


@router.get("/{kb_id}/segments")
async def list_kb_segments(
    kb_id: str,
    request: Request,
    workspace_id: str = Query(..., description="Workspace ID"),
    document_id: str | None = Query(None, description="Filter by document ID"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    auth: AuthContext = Depends(get_current_user),
):
    auth.require_workspace_role(workspace_id, "viewer")
    async with request.app.state.db_session_factory() as session:
        kb = await db.get_knowledge_base(session, workspace_id, kb_id, redis=request.app.state.redis)
        if not kb:
            raise HTTPException(status_code=404, detail="Knowledge base not found")
        result = await db.list_kb_segments(
            session, kb_id, document_id=document_id, offset=offset, limit=limit,
            redis=request.app.state.redis,
        )
    return result


@router.patch("/{kb_id}/segments/{seg_id}")
async def patch_kb_segment(
    kb_id: str,
    seg_id: str,
    body: KBSegmentPatchRequest,
    request: Request,
    workspace_id: str = Query(..., description="Workspace ID"),
    auth: AuthContext = Depends(get_current_user),
):
    auth.require_workspace_role(workspace_id, "developer")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")
    async with request.app.state.db_session_factory() as session:
        kb = await db.get_knowledge_base(session, workspace_id, kb_id, redis=request.app.state.redis)
        if not kb:
            raise HTTPException(status_code=404, detail="Knowledge base not found")
        seg = await db.update_kb_segment(
            session, kb_id, seg_id, updates, redis=request.app.state.redis
        )
    if not seg:
        raise HTTPException(status_code=404, detail="Segment not found")
    return seg
