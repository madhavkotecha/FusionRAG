"""Version management for components. Append-only version history."""
from __future__ import annotations

import hashlib

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.component_version import ComponentVersion


async def create_version(
    db: AsyncSession,
    *,
    component_type: str,
    workspace_id: str,
    code: str,
    changed_by: str,
    change_reason: str | None = None,
) -> ComponentVersion:
    """Create a new version row. Computes next version number atomically."""
    # Use MAX + 1; unique constraint prevents races in production (PostgreSQL).
    # No FOR UPDATE — SQLite (used in tests) does not support it.
    max_version = await db.scalar(
        select(func.coalesce(func.max(ComponentVersion.version), 0)).where(
            ComponentVersion.component_type == component_type,
            ComponentVersion.workspace_id == workspace_id,
        )
    )
    next_version = max_version + 1

    file_hash = hashlib.sha256(code.encode()).hexdigest()

    ver = ComponentVersion(
        component_type=component_type,
        workspace_id=workspace_id,
        version=next_version,
        code=code,
        file_hash=file_hash,
        changed_by=changed_by,
        change_reason=change_reason,
    )
    db.add(ver)
    await db.flush()
    return ver


async def list_versions(
    db: AsyncSession,
    component_type: str,
    workspace_id: str,
    *,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[ComponentVersion], int]:
    """Return paginated version list (newest first) and total count."""
    base = select(ComponentVersion).where(
        ComponentVersion.component_type == component_type,
        ComponentVersion.workspace_id == workspace_id,
    )

    total = await db.scalar(
        select(func.count()).select_from(base.subquery())
    )

    rows = await db.scalars(
        base.order_by(ComponentVersion.version.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows), total or 0


async def get_version_code(
    db: AsyncSession,
    component_type: str,
    workspace_id: str,
    version: int,
) -> str | None:
    """Return the code for a specific version, or None if not found."""
    ver = await db.scalar(
        select(ComponentVersion.code).where(
            ComponentVersion.component_type == component_type,
            ComponentVersion.workspace_id == workspace_id,
            ComponentVersion.version == version,
        )
    )
    return ver


async def get_version(
    db: AsyncSession,
    component_type: str,
    workspace_id: str,
    version: int,
) -> ComponentVersion | None:
    """Return a full version record, or None."""
    return await db.scalar(
        select(ComponentVersion).where(
            ComponentVersion.component_type == component_type,
            ComponentVersion.workspace_id == workspace_id,
            ComponentVersion.version == version,
        )
    )
