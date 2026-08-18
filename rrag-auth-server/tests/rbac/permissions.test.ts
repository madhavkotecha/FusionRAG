/**
 * RBAC permission tests (pure logic, no DB/Redis needed).
 */

import { describe, it, expect } from "vitest";
import {
  getEffectivePermissions,
  hasPermission,
  checkRoleHierarchy,
  VIEWER_PERMISSIONS,
  DEVELOPER_PERMISSIONS,
  WORKSPACE_ADMIN_PERMISSIONS,
  ORG_ADMIN_PERMISSIONS,
} from "../../src/rbac/permissions.js";
import type { AuthContext } from "../../src/types.js";

function makeAuth(overrides: Partial<AuthContext> = {}): AuthContext {
  return {
    userId: "user-1",
    orgId: "org-1",
    orgRole: "member",
    email: "test@test.com",
    name: "Test",
    workspaceMemberships: {},
    isPlatformAdmin: false,
    ...overrides,
  };
}

describe("Permission Sets", () => {
  it("viewer permissions are a subset of developer", () => {
    for (const perm of VIEWER_PERMISSIONS) {
      expect(DEVELOPER_PERMISSIONS.has(perm)).toBe(true);
    }
  });

  it("developer permissions are a subset of workspace admin", () => {
    for (const perm of DEVELOPER_PERMISSIONS) {
      expect(WORKSPACE_ADMIN_PERMISSIONS.has(perm)).toBe(true);
    }
  });

  it("workspace admin permissions are a subset of org admin", () => {
    for (const perm of WORKSPACE_ADMIN_PERMISSIONS) {
      expect(ORG_ADMIN_PERMISSIONS.has(perm)).toBe(true);
    }
  });

  it("org admin has org-level permissions", () => {
    expect(ORG_ADMIN_PERMISSIONS.has("org.settings:read")).toBe(true);
    expect(ORG_ADMIN_PERMISSIONS.has("org.billing:manage")).toBe(true);
    expect(ORG_ADMIN_PERMISSIONS.has("org.sso:manage")).toBe(true);
  });
});

describe("getEffectivePermissions", () => {
  it("platform admin gets all permissions plus platform:admin", () => {
    const auth = makeAuth({ isPlatformAdmin: true });
    const perms = getEffectivePermissions(auth);
    expect(perms.has("platform:admin")).toBe(true);
    expect(perms.has("org.settings:read")).toBe(true);
  });

  it("org_admin gets org admin permissions without workspace context", () => {
    const auth = makeAuth({ orgRole: "org_admin" });
    const perms = getEffectivePermissions(auth);
    expect(perms.has("workspace:delete")).toBe(true);
    expect(perms.has("org.billing:manage")).toBe(true);
  });

  it("regular member with no workspace context gets empty permissions", () => {
    const auth = makeAuth({ orgRole: "member" });
    const perms = getEffectivePermissions(auth);
    expect(perms.size).toBe(0);
  });

  it("viewer gets viewer permissions for their workspace", () => {
    const auth = makeAuth({
      workspaceMemberships: { "ws-1": "viewer" },
    });
    const perms = getEffectivePermissions(auth, "ws-1");
    expect(perms.has("workspace:read")).toBe(true);
    expect(perms.has("pipeline:read")).toBe(true);
    expect(perms.has("pipeline:create")).toBe(false);
  });

  it("developer gets developer permissions for their workspace", () => {
    const auth = makeAuth({
      workspaceMemberships: { "ws-1": "developer" },
    });
    const perms = getEffectivePermissions(auth, "ws-1");
    expect(perms.has("pipeline:create")).toBe(true);
    expect(perms.has("pipeline:execute")).toBe(true);
    expect(perms.has("workspace:update")).toBe(false);
  });

  it("admin gets workspace admin permissions", () => {
    const auth = makeAuth({
      workspaceMemberships: { "ws-1": "admin" },
    });
    const perms = getEffectivePermissions(auth, "ws-1");
    expect(perms.has("workspace:update")).toBe(true);
    expect(perms.has("workspace.members:manage")).toBe(true);
    expect(perms.has("audit_log:read")).toBe(true);
  });

  it("returns empty set for non-member workspace", () => {
    const auth = makeAuth({
      workspaceMemberships: { "ws-1": "developer" },
    });
    const perms = getEffectivePermissions(auth, "ws-2");
    expect(perms.size).toBe(0);
  });
});

describe("hasPermission", () => {
  it("returns true for valid permission", () => {
    const auth = makeAuth({
      workspaceMemberships: { "ws-1": "developer" },
    });
    expect(hasPermission(auth, "ws-1", "pipeline", "create")).toBe(true);
  });

  it("returns false for insufficient permission", () => {
    const auth = makeAuth({
      workspaceMemberships: { "ws-1": "viewer" },
    });
    expect(hasPermission(auth, "ws-1", "pipeline", "create")).toBe(false);
  });

  it("org_admin has permission on any workspace", () => {
    const auth = makeAuth({ orgRole: "org_admin" });
    expect(hasPermission(auth, "any-ws", "workspace", "delete")).toBe(true);
  });
});

describe("checkRoleHierarchy", () => {
  it("admin >= viewer", () => {
    expect(checkRoleHierarchy("admin", "viewer")).toBe(true);
  });

  it("admin >= developer", () => {
    expect(checkRoleHierarchy("admin", "developer")).toBe(true);
  });

  it("admin >= admin", () => {
    expect(checkRoleHierarchy("admin", "admin")).toBe(true);
  });

  it("developer < admin", () => {
    expect(checkRoleHierarchy("developer", "admin")).toBe(false);
  });

  it("viewer < developer", () => {
    expect(checkRoleHierarchy("viewer", "developer")).toBe(false);
  });

  it("returns false for unknown roles", () => {
    expect(checkRoleHierarchy("unknown", "admin")).toBe(false);
    expect(checkRoleHierarchy("admin", "unknown")).toBe(false);
  });
});
