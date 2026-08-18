from __future__ import annotations

import logging
import os
import uuid

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile

from rrag_ingestion.config import settings
from rrag_ingestion.db import stores as db
from rrag_ingestion.dependencies import AuthContext, get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


def _is_minio_available() -> bool:
    """Check if MinIO client can be created."""
    try:
        from rrag_ingestion.services import object_store
        object_store.get_client()
        return True
    except Exception:
        return False


@router.post("/upload")
async def upload_documents(
    files: list[UploadFile],
    request: Request,
    workspace_id: str = Query(..., description="Workspace ID"),
    auth: AuthContext = Depends(get_current_user),
):
    auth.require_workspace_role(workspace_id, "developer")
    results = []
    for file in files:
        doc_id = str(uuid.uuid4())
        # Sanitize filename to prevent path traversal
        safe_filename = os.path.basename(file.filename or "upload")
        if not safe_filename or safe_filename in (".", ".."):
            safe_filename = "upload"

        # Enforce upload size limit
        max_bytes = settings.max_upload_size_mb * 1024 * 1024
        content = await file.read()
        if len(content) > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File '{safe_filename}' exceeds max upload size of {settings.max_upload_size_mb}MB",
            )

        content_type = file.content_type or "application/octet-stream"
        metadata = {"size_bytes": len(content)}

        # Try MinIO first, fall back to local filesystem
        try:
            from rrag_ingestion.services import object_store

            key = object_store.make_object_key(workspace_id, doc_id, safe_filename)
            object_store.upload_object(key, content, content_type)
            file_path = key  # Store S3 key as file_path
            metadata["storage"] = "minio"
        except Exception as e:
            logger.info(f"MinIO upload failed ({e}), falling back to local filesystem")
            file_path = os.path.join(settings.storage_dir, workspace_id, doc_id, safe_filename)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            async with aiofiles.open(file_path, "wb") as f:
                await f.write(content)
            metadata["storage"] = "local"

        doc_data = {
            "id": doc_id,
            "workspace_id": workspace_id,
            "filename": safe_filename,
            "content_type": content_type,
            "file_path": file_path,
            "metadata": metadata,
        }
        async with request.app.state.db_session_factory() as session:
            await db.save_document(session, doc_data, redis=request.app.state.redis)
        results.append({"id": doc_id, "filename": safe_filename})

    return {"uploaded": results}


@router.get("")
async def list_documents(
    request: Request,
    workspace_id: str = Query(..., description="Workspace ID"),
    auth: AuthContext = Depends(get_current_user),
):
    auth.require_workspace_role(workspace_id, "viewer")
    async with request.app.state.db_session_factory() as session:
        docs = await db.list_documents(session, workspace_id, redis=request.app.state.redis)
    return {"documents": docs}


@router.get("/{doc_id}")
async def get_document(
    doc_id: str,
    request: Request,
    workspace_id: str = Query(..., description="Workspace ID"),
    auth: AuthContext = Depends(get_current_user),
):
    auth.require_workspace_role(workspace_id, "viewer")
    async with request.app.state.db_session_factory() as session:
        doc = await db.get_document(session, workspace_id, doc_id, redis=request.app.state.redis)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.get("/{doc_id}/download-url")
async def get_document_download_url(
    doc_id: str,
    request: Request,
    workspace_id: str = Query(..., description="Workspace ID"),
    auth: AuthContext = Depends(get_current_user),
):
    """Get a presigned download URL for a document stored in MinIO."""
    auth.require_workspace_role(workspace_id, "viewer")
    async with request.app.state.db_session_factory() as session:
        doc = await db.get_document(session, workspace_id, doc_id, redis=request.app.state.redis)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.get("metadata", {}).get("storage") != "minio":
        raise HTTPException(status_code=400, detail="Document is not stored in object storage")

    try:
        from rrag_ingestion.services import object_store

        url = object_store.get_presigned_url(doc["file_path"])
        return {"download_url": url, "filename": doc["filename"]}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to generate download URL: {e}")


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: str,
    request: Request,
    workspace_id: str = Query(..., description="Workspace ID"),
    auth: AuthContext = Depends(get_current_user),
):
    auth.require_workspace_role(workspace_id, "developer")
    async with request.app.state.db_session_factory() as session:
        doc = await db.delete_document(session, workspace_id, doc_id, redis=request.app.state.redis)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete from the appropriate storage backend
    if doc.get("metadata", {}).get("storage") == "minio":
        try:
            from rrag_ingestion.services import object_store
            object_store.delete_object(doc["file_path"])
        except Exception as e:
            logger.warning(f"Failed to delete from MinIO: {e}")
    else:
        try:
            os.remove(doc["file_path"])
        except FileNotFoundError:
            pass

    return {"deleted": doc_id}
