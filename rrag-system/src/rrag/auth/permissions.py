"""RBAC permission definitions and resolution.

Roles: platform_admin > org_admin > workspace_admin > developer > viewer
Permissions are expressed as 'resource:action' pairs.
"""

from dataclasses import dataclass, field

# Role hierarchy (higher index = more privileged)
ROLE_HIERARCHY = ["viewer", "developer", "admin"]
ORG_ROLES = ["member", "org_admin"]

# Permission matrix: role -> set of permissions
VIEWER_PERMISSIONS: set[str] = {
    "workspace:read",
    "workspace.members:read",
    "workspace.connections:read",
    "pipeline:read",
    "knowledge_base:read",
    "experiment:read",
    "deployment:read",
    "api_key:read",
}

DEVELOPER_PERMISSIONS: set[str] = VIEWER_PERMISSIONS | {
    "pipeline:create",
    "pipeline:update",
    "pipeline:delete",
    "pipeline:execute",
    "knowledge_base:create",
    "knowledge_base:update",
    "knowledge_base:delete",
    "knowledge_base.documents:upload",
    "knowledge_base.documents:delete",
    "experiment:create",
    "experiment:execute",
}

WORKSPACE_ADMIN_PERMISSIONS: set[str] = DEVELOPER_PERMISSIONS | {
    "workspace:update",
    "workspace.members:manage",
    "workspace.connections:manage",
    "deployment:create",
    "deployment:update",
    "deployment:delete",
    "deployment.traffic:manage",
    "audit_log:read",
    "api_key:manage",
}

ORG_ADMIN_PERMISSIONS: set[str] = WORKSPACE_ADMIN_PERMISSIONS | {
    "workspace:delete",
    "org.settings:read",
    "org.settings:update",
    "org.billing:read",
    "org.billing:manage",
    "org.sso:manage",
}

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "viewer": VIEWER_PERMISSIONS,
    "developer": DEVELOPER_PERMISSIONS,
    "admin": WORKSPACE_ADMIN_PERMISSIONS,
}


@dataclass
class AuthContext:
    """Authentication context injected into every request."""

    user_id: str
    org_id: str
    org_role: str  # "org_admin" | "member"
    email: str = ""
    name: str = ""
    workspace_memberships: dict[str, str] = field(default_factory=dict)  # {ws_id: role}
    is_platform_admin: bool = False


def get_effective_permissions(auth: AuthContext, workspace_id: str | None = None) -> set[str]:
    """Resolve the effective permissions for a user in a given workspace context."""
    if auth.is_platform_admin:
        return ORG_ADMIN_PERMISSIONS | {"platform:admin"}

    if auth.org_role == "org_admin":
        return ORG_ADMIN_PERMISSIONS

    if workspace_id is None:
        # No workspace context -- only org-level permissions
        return set()

    ws_role = auth.workspace_memberships.get(workspace_id)
    if ws_role is None:
        return set()

    return ROLE_PERMISSIONS.get(ws_role, set())


def has_permission(
    auth: AuthContext,
    workspace_id: str | None,
    resource: str,
    action: str,
) -> bool:
    """Check if user has a specific permission in a workspace context."""
    permission = f"{resource}:{action}"
    effective = get_effective_permissions(auth, workspace_id)
    return permission in effective


def check_role_hierarchy(current_role: str, target_role: str) -> bool:
    """Check if current_role is >= target_role in the hierarchy.
    Used to prevent privilege escalation (can't assign a role higher than your own).
    """
    if current_role not in ROLE_HIERARCHY or target_role not in ROLE_HIERARCHY:
        return False
    return ROLE_HIERARCHY.index(current_role) >= ROLE_HIERARCHY.index(target_role)
