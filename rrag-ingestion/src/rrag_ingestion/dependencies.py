from __future__ import annotations

import json
from dataclasses import dataclass

from fastapi import HTTPException, Request


ROLE_HIERARCHY = {"viewer": 0, "developer": 1, "admin": 2}


@dataclass
class AuthContext:
    user_id: str
    org_id: str
    org_role: str
    email: str
    workspace_roles: dict[str, str]
    is_platform_admin: bool = False

    @property
    def is_org_admin(self) -> bool:
        return self.org_role in ("owner", "org_admin") or self.is_platform_admin

    def has_workspace_access(self, workspace_id: str) -> bool:
        """Check if user has any role in the given workspace."""
        if self.is_org_admin:
            return True
        return workspace_id in self.workspace_roles

    def get_workspace_role(self, workspace_id: str) -> str | None:
        """Return the user's effective role in the workspace, or None."""
        if self.is_org_admin or self.is_platform_admin:
            return "admin"
        return self.workspace_roles.get(workspace_id)

    def require_workspace_access(self, workspace_id: str) -> None:
        """Raise 403 if user lacks access to the workspace."""
        if not self.has_workspace_access(workspace_id):
            raise HTTPException(
                status_code=403,
                detail=f"No access to workspace '{workspace_id}'",
            )

    def require_workspace_role(self, workspace_id: str, min_role: str) -> None:
        """Raise 403 if user's workspace role is below min_role."""
        role = self.get_workspace_role(workspace_id)
        if role is None:
            raise HTTPException(
                status_code=403,
                detail=f"No access to workspace '{workspace_id}'",
            )
        if ROLE_HIERARCHY.get(role, -1) < ROLE_HIERARCHY.get(min_role, 99):
            raise HTTPException(
                status_code=403,
                detail=f"Requires at least '{min_role}' role in workspace (you have '{role}')",
            )

    def require_org_admin(self) -> None:
        """Raise 403 if user is not an org admin."""
        if not self.is_org_admin:
            raise HTTPException(
                status_code=403,
                detail="Organization admin privileges required",
            )


async def get_current_user(request: Request) -> AuthContext:
    user_id = request.headers.get("X-Auth-User-Id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    org_id = request.headers.get("X-Auth-Org-Id")
    if not org_id:
        raise HTTPException(status_code=401, detail="Missing organization context")

    raw_roles = request.headers.get("X-Auth-Workspace-Roles", "{}")
    try:
        workspace_roles = json.loads(raw_roles)
    except (json.JSONDecodeError, TypeError):
        workspace_roles = {}

    is_platform_admin = (
        request.headers.get("X-Auth-Platform-Admin", "false").lower() == "true"
    )

    return AuthContext(
        user_id=user_id,
        org_id=org_id,
        org_role=request.headers.get("X-Auth-Org-Role", ""),
        email=request.headers.get("X-Auth-Email", ""),
        workspace_roles=workspace_roles,
        is_platform_admin=is_platform_admin,
    )
