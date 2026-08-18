"""Admin API for component management — code viewing, editing, versioning."""
from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..dependencies import AuthContext, get_current_user
from ..framework.minio_client import (
    download_component_file,
    get_minio_client,
    upload_component_file,
)
from ..framework.scanner import ComponentScanner
from ..models.component import Component
from ..schemas.component_admin import (
    CodeUpdateRequest,
    ComponentResponse,
    RevertRequest,
    VersionDetailResponse,
    VersionListResponse,
    VersionResponse,
)
from ..services.component_versions import (
    create_version,
    get_version,
    get_version_code,
    list_versions,
)

router = APIRouter(prefix="/admin/components", tags=["admin-components"])
scanner = ComponentScanner()

# Map component categories → local source file in the components package
_COMPONENTS_DIR = Path(__file__).resolve().parent.parent / "components"
_CATEGORY_SOURCE_FILES: dict[str, str] = {
    "parser": "data_sources.py",
    "chunker": "chunkers.py",
    "embedder": "embedders.py",
    "extractor": "extractors.py",
    "graph_builder": "graph_builders.py",
    "indexer": "indexers.py",
    "storage": "storage.py",
    "retriever": "retrievers.py",
    "reranker": "rerankers.py",
    "generator": "generators.py",
    "planner": "planners.py",
    "agent": "agents.py",
}


def _require_admin(auth: AuthContext) -> None:
    """Raise 403 if user is neither org_admin nor platform_admin.
    Note: AuthContext.is_org_admin already returns True for platform_admin."""
    auth.require_org_admin()


def _can_edit(auth: AuthContext, source: str, workspace_id: str) -> bool:
    """Check if user can edit this component."""
    if auth.is_platform_admin:
        return True
    if source == "seed":
        return False  # org_admin cannot edit seed
    # org_admin can edit custom components in their own workspaces
    return auth.has_workspace_access(workspace_id)


def _normalize_workspace_id(ws: str | None) -> str | None:
    """Convert _global to None for API responses."""
    return None if ws == "_global" else ws


# ── List all components ───────────────────────────────────────

@router.get("", response_model=list[ComponentResponse])
async def admin_list_components(
    source: str | None = Query(None),
    category: str | None = Query(None),
    search: str | None = Query(None),
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_current_user),
):
    _require_admin(auth)

    stmt = select(Component)

    # Scope: platform_admin sees all; org_admin sees seed + own workspaces
    if not auth.is_platform_admin:
        accessible_ws = list(auth.workspace_roles.keys()) + ["_global"]
        stmt = stmt.where(Component.workspace_id.in_(accessible_ws))

    if source:
        stmt = stmt.where(Component.source == source)
    if category:
        stmt = stmt.where(Component.category == category)
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(
            or_(
                Component.name.ilike(pattern),
                Component.type.ilike(pattern),
                Component.description.ilike(pattern),
            )
        )

    stmt = stmt.order_by(Component.category, Component.name)
    result = await db.execute(stmt)
    components = result.scalars().all()

    out = []
    for c in components:
        d = ComponentResponse.model_validate(c)
        d.workspace_id = _normalize_workspace_id(c.workspace_id)
        out.append(d)
    return out


# ── Get component code ────────────────────────────────────────

@router.get("/{component_type}/code")
async def admin_get_code(
    component_type: str,
    workspace_id: str = Query("_global"),
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_current_user),
):
    _require_admin(auth)

    comp = await db.scalar(
        select(Component).where(
            Component.type == component_type,
            Component.workspace_id == workspace_id,
        )
    )
    if not comp:
        raise HTTPException(404, "Component not found")

    code: str | None = None

    if comp.file_path:
        # Custom component or seed with uploaded code — read from MinIO
        minio = get_minio_client()
        try:
            raw = await asyncio.to_thread(
                download_component_file, minio, comp.file_path
            )
            code = raw.decode("utf-8")
        except Exception:
            pass  # fall through to local file lookup

    if code is None and comp.source == "seed":
        # Fall back to local source file in the components package
        src_file = _CATEGORY_SOURCE_FILES.get(comp.category)
        if src_file:
            local_path = _COMPONENTS_DIR / src_file
            if local_path.is_file():
                code = local_path.read_text(encoding="utf-8")

    if code is None:
        raise HTTPException(404, "No source code available for this component")

    return {
        "type": component_type,
        "workspace_id": _normalize_workspace_id(workspace_id),
        "code": code,
        "current_version": comp.current_version,
        "can_edit": _can_edit(auth, comp.source, comp.workspace_id),
    }


# ── Update component code ────────────────────────────────────

@router.put("/{component_type}/code")
async def admin_update_code(
    component_type: str,
    body: CodeUpdateRequest,
    workspace_id: str = Query("_global"),
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_current_user),
):
    _require_admin(auth)

    comp = await db.scalar(
        select(Component).where(
            Component.type == component_type,
            Component.workspace_id == workspace_id,
        )
    )
    if not comp:
        raise HTTPException(404, "Component not found")

    if not _can_edit(auth, comp.source, comp.workspace_id):
        raise HTTPException(403, "You cannot edit this component")

    # Validate Python syntax
    try:
        meta = scanner.scan_source(body.code)
    except SyntaxError as e:
        raise HTTPException(422, f"Invalid Python syntax: {e}")
    if meta is None:
        raise HTTPException(422, "Code must contain a class with @component decorator")

    # Upload to MinIO
    code_bytes = body.code.encode("utf-8")
    file_hash = hashlib.sha256(code_bytes).hexdigest()
    filename = f"{component_type}.py"
    minio = get_minio_client()
    object_path = await asyncio.to_thread(
        upload_component_file, minio, workspace_id, filename, code_bytes
    )

    # Create version
    ver = await create_version(
        db=db,
        component_type=component_type,
        workspace_id=workspace_id,
        code=body.code,
        changed_by=auth.user_id,
        change_reason=body.change_reason,
    )

    # Update component record
    comp.file_path = object_path
    comp.file_hash = file_hash
    comp.current_version = ver.version

    # Update metadata from scanned code
    comp.name = meta.get("name", comp.name)
    comp.description = meta.get("description", comp.description)
    comp.category = meta.get("category", comp.category)
    comp.config_schema = meta.get("config_schema") or comp.config_schema
    comp.input_ports = meta.get("input_ports") or comp.input_ports
    comp.output_ports = meta.get("output_ports") or comp.output_ports

    await db.commit()

    return {
        "type": component_type,
        "version": ver.version,
        "file_hash": file_hash,
        "status": "updated",
    }


# ── Version history ───────────────────────────────────────────

@router.get("/{component_type}/versions", response_model=VersionListResponse)
async def admin_list_versions(
    component_type: str,
    workspace_id: str = Query("_global"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_current_user),
):
    _require_admin(auth)

    versions, total = await list_versions(
        db, component_type, workspace_id, page=page, page_size=page_size
    )

    return VersionListResponse(
        items=[VersionResponse.model_validate(v) for v in versions],
        total=total,
        page=page,
        page_size=page_size,
    )


# ── Get specific version ──────────────────────────────────────

@router.get(
    "/{component_type}/versions/{version}",
    response_model=VersionDetailResponse,
)
async def admin_get_version(
    component_type: str,
    version: int,
    workspace_id: str = Query("_global"),
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_current_user),
):
    _require_admin(auth)

    ver = await get_version(db, component_type, workspace_id, version)
    if not ver:
        raise HTTPException(404, "Version not found")

    return VersionDetailResponse.model_validate(ver)


# ── Revert to version ─────────────────────────────────────────

@router.post("/{component_type}/revert")
async def admin_revert(
    component_type: str,
    body: RevertRequest,
    workspace_id: str = Query("_global"),
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_current_user),
):
    _require_admin(auth)

    # Check component exists
    comp = await db.scalar(
        select(Component).where(
            Component.type == component_type,
            Component.workspace_id == workspace_id,
        )
    )
    if not comp:
        raise HTTPException(404, "Component not found")

    if not _can_edit(auth, comp.source, comp.workspace_id):
        raise HTTPException(403, "You cannot revert this component")

    # Get the target version's code
    old_code = await get_version_code(
        db, component_type, workspace_id, body.version
    )
    if old_code is None:
        raise HTTPException(404, f"Version {body.version} not found")

    # Upload reverted code to MinIO
    code_bytes = old_code.encode("utf-8")
    file_hash = hashlib.sha256(code_bytes).hexdigest()
    filename = f"{component_type}.py"
    minio = get_minio_client()
    object_path = await asyncio.to_thread(
        upload_component_file, minio, workspace_id, filename, code_bytes
    )

    # Create new version with the reverted code
    ver = await create_version(
        db=db,
        component_type=component_type,
        workspace_id=workspace_id,
        code=old_code,
        changed_by=auth.user_id,
        change_reason=f"Reverted to version {body.version}",
    )

    comp.file_path = object_path
    comp.file_hash = file_hash
    comp.current_version = ver.version
    await db.commit()

    return {
        "type": component_type,
        "reverted_from": body.version,
        "new_version": ver.version,
        "status": "reverted",
    }
