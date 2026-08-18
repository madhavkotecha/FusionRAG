/**
 * RBAC permission definitions and resolution.
 *
 * Roles: platform_admin > org_admin > workspace_admin > developer > viewer
 * Permissions are expressed as 'resource:action' pairs.
 */

import type { AuthContext } from "../types.js";

// Role hierarchy (higher index = more privileged)
export const ROLE_HIERARCHY = ["viewer", "developer", "admin"] as const;
export const ORG_ROLES = ["member", "org_admin"] as const;

// Permission matrix: role -> set of permissions
export const VIEWER_PERMISSIONS = new Set([
  "workspace:read",
  "workspace.members:read",
  "workspace.connections:read",
  "pipeline:read",
  "knowledge_base:read",
  "experiment:read",
  "deployment:read",
  "api_key:read",
]);

export const DEVELOPER_PERMISSIONS = new Set([
  ...VIEWER_PERMISSIONS,
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
]);

export const WORKSPACE_ADMIN_PERMISSIONS = new Set([
  ...DEVELOPER_PERMISSIONS,
  "workspace:update",
  "workspace.members:manage",
  "workspace.connections:manage",
  "deployment:create",
  "deployment:update",
  "deployment:delete",
  "deployment.traffic:manage",
  "audit_log:read",
  "api_key:manage",
]);

export const ORG_ADMIN_PERMISSIONS = new Set([
  ...WORKSPACE_ADMIN_PERMISSIONS,
  "workspace:delete",
  "org.settings:read",
  "org.settings:update",
  "org.billing:read",
  "org.billing:manage",
  "org.sso:manage",
]);

export const ROLE_PERMISSIONS: Record<string, Set<string>> = {
  viewer: VIEWER_PERMISSIONS,
  developer: DEVELOPER_PERMISSIONS,
  admin: WORKSPACE_ADMIN_PERMISSIONS,
};

/**
 * Resolve the effective permissions for a user in a given workspace context.
 */
export function getEffectivePermissions(
  auth: AuthContext,
  workspaceId: string | null = null,
): Set<string> {
  if (auth.isPlatformAdmin) {
    return new Set([...ORG_ADMIN_PERMISSIONS, "platform:admin"]);
  }

  if (auth.orgRole === "org_admin") {
    return ORG_ADMIN_PERMISSIONS;
  }

  if (workspaceId === null) {
    return new Set();
  }

  const wsRole = auth.workspaceMemberships[workspaceId];
  if (!wsRole) {
    return new Set();
  }

  return ROLE_PERMISSIONS[wsRole] ?? new Set();
}

/**
 * Check if user has a specific permission in a workspace context.
 */
export function hasPermission(
  auth: AuthContext,
  workspaceId: string | null,
  resource: string,
  action: string,
): boolean {
  const permission = `${resource}:${action}`;
  const effective = getEffectivePermissions(auth, workspaceId);
  return effective.has(permission);
}

/**
 * Check if current_role is >= target_role in the hierarchy.
 * Used to prevent privilege escalation.
 */
export function checkRoleHierarchy(currentRole: string, targetRole: string): boolean {
  const currentIdx = ROLE_HIERARCHY.indexOf(currentRole as (typeof ROLE_HIERARCHY)[number]);
  const targetIdx = ROLE_HIERARCHY.indexOf(targetRole as (typeof ROLE_HIERARCHY)[number]);
  if (currentIdx === -1 || targetIdx === -1) return false;
  return currentIdx >= targetIdx;
}
