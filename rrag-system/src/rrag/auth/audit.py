"""Audit logging service.

Writes immutable audit log entries for security-relevant actions.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from rrag.auth.models import AuditLog


async def log_audit_event(
    db: AsyncSession,
    *,
    org_id: str | uuid.UUID,
    action: str,
    resource_type: str,
    status: str = "success",
    user_id: str | uuid.UUID | None = None,
    resource_id: str | uuid.UUID | None = None,
    workspace_id: str | uuid.UUID | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    request_id: str | uuid.UUID | None = None,
) -> AuditLog:
    """Create an audit log entry."""
    entry = AuditLog(
        org_id=uuid.UUID(str(org_id)) if org_id else None,
        user_id=uuid.UUID(str(user_id)) if user_id else None,
        action=action,
        resource_type=resource_type,
        resource_id=uuid.UUID(str(resource_id)) if resource_id else None,
        workspace_id=uuid.UUID(str(workspace_id)) if workspace_id else None,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent,
        request_id=uuid.UUID(str(request_id)) if request_id else None,
        status=status,
        timestamp=datetime.now(timezone.utc),
    )
    db.add(entry)
    # Don't commit here -- let the session middleware handle commits
    return entry
