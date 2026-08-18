from __future__ import annotations

import hashlib

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..dependencies import AuthContext, get_current_user
from ..framework.minio_client import (
    delete_component_file,
    ensure_bucket,
    get_minio_client,
    upload_component_file,
)
from ..framework.scanner import ComponentScanner
from ..services.component_registry import (
    delete_component,
    get_component,
    get_seed_component,
    upsert_custom_component,
)
from ..services.component_versions import create_version

router = APIRouter()
scanner = ComponentScanner()
MAX_FILE_SIZE = 512 * 1024


async def _optional_auth(request: Request) -> AuthContext | None:
    """Try to get auth context, return None if not authenticated."""
    try:
        return await get_current_user(request)
    except Exception:
        return None


@router.post("/upload")
async def upload_component(
    file: UploadFile,
    request: "Request",
    workspace_id: str = Query(...),
    dry_run: bool = Query(False),
    db: AsyncSession = Depends(get_session),
    auth: AuthContext | None = Depends(_optional_auth),
):
    if not file.filename or not file.filename.endswith(".py"):
        raise HTTPException(400, "Only .py files accepted")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(400, f"File too large (max {MAX_FILE_SIZE // 1024}KB)")

    try:
        meta = scanner.scan_source(content.decode("utf-8"))
    except SyntaxError as e:
        raise HTTPException(422, f"Invalid Python syntax: {e}")

    if meta is None:
        raise HTTPException(422, "No @component decorated class found in file")

    # dry_run: just return extracted metadata without persisting
    if dry_run:
        return {
            "type": meta["type"],
            "category": meta["category"],
            "name": meta["name"],
            "description": meta.get("description", ""),
            "is_composite": meta.get("is_composite", False),
            "steps": meta.get("steps"),
            "input_ports": meta.get("input_ports"),
            "output_ports": meta.get("output_ports"),
            "config_schema": meta.get("config_schema"),
            "status": "preview",
        }

    seed = await get_seed_component(db, meta["type"])
    if seed:
        raise HTTPException(409, f"Cannot override built-in component '{meta['type']}'")

    minio = get_minio_client()
    ensure_bucket(minio)
    file_hash = hashlib.md5(content).hexdigest()
    minio_path = upload_component_file(minio, workspace_id, file.filename, content)

    comp = await upsert_custom_component(
        db,
        type=meta["type"],
        category=meta["category"],
        name=meta["name"],
        description=meta.get("description", ""),
        config_schema=meta.get("config_schema"),
        input_ports=meta.get("input_ports"),
        output_ports=meta.get("output_ports"),
        is_composite=meta.get("is_composite", False),
        steps=meta.get("steps"),
        source="custom",
        workspace_id=workspace_id,
        file_path=minio_path,
        file_hash=file_hash,
    )

    # Invalidate component list cache so new component appears immediately
    redis = getattr(request.app.state, "redis", None)
    if redis:
        try:
            from ..cache import cache_delete
            cache_delete(redis, "comp", "_global", suffix="list")
        except Exception:
            pass

    # Create version record
    try:
        await create_version(
            db=db,
            component_type=meta["type"],
            workspace_id=workspace_id,
            code=content.decode("utf-8"),
            changed_by=auth.user_id if auth else "anonymous",
            change_reason="Uploaded via component creator",
        )
    except Exception:
        pass  # Versioning is best-effort during upload

    return {
        "type": comp.type,
        "category": comp.category,
        "name": comp.name,
        "is_composite": comp.is_composite,
        "steps": comp.steps,
        "file_path": comp.file_path,
        "status": "registered",
    }


@router.delete("/custom/{component_type}")
async def delete_custom_component(
    component_type: str,
    workspace_id: str = Query(...),
    db: AsyncSession = Depends(get_session),
):
    comp = await get_component(db, component_type)
    if not comp or getattr(comp, "source", "seed") != "custom":
        raise HTTPException(404, "Custom component not found")

    if getattr(comp, "workspace_id", "_global") != workspace_id:
        raise HTTPException(403, "Component belongs to different workspace")

    if comp.file_path:
        try:
            minio = get_minio_client()
            delete_component_file(minio, comp.file_path)
        except Exception:
            pass

    await delete_component(db, component_type, workspace_id)
    return {"deleted": component_type}
