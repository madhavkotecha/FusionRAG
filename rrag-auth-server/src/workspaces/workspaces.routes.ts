/**
 * Workspace CRUD + member routes.
 */

import { Hono } from "hono";
import { zValidator } from "@hono/zod-validator";
import type { AppEnv } from "../types.js";
import { WorkspacesService } from "./workspaces.service.js";
import {
  createWorkspaceSchema,
  updateWorkspaceSchema,
  addMemberSchema,
  updateMemberRoleSchema,
} from "./workspaces.schemas.js";
import { requireWsMember, requirePermission } from "../rbac/rbac.middleware.js";
import { logAuditEvent } from "../audit/audit.logger.js";
import { AppError } from "../middleware/error-handler.js";

export const workspacesRoutes = new Hono<AppEnv>();

// ── Workspace CRUD ────────────────────────────────────────────

// POST /workspaces — create workspace
workspacesRoutes.post(
  "/",
  zValidator("json", createWorkspaceSchema),
  async (c) => {
    const auth = c.get("auth");
    if (!auth) throw new AppError(401, "Authentication required", "AUTH_REQUIRED");

    const db = c.get("db");
    const body = c.req.valid("json");

    const service = new WorkspacesService(db, c.get("redis"));
    const workspace = await service.createWorkspace(auth.orgId, body, auth);

    logAuditEvent(db, {
      orgId: auth.orgId,
      userId: auth.userId,
      action: "workspace_create",
      resourceType: "workspace",
      resourceId: workspace.id,
      status: "success",
      details: { name: body.name, scope: body.scope },
      requestId: c.get("requestId"),
    });

    return c.json(workspace, 201);
  },
);

// GET /workspaces — list workspaces user has access to
workspacesRoutes.get("/", async (c) => {
  const auth = c.get("auth");
  if (!auth) throw new AppError(401, "Authentication required", "AUTH_REQUIRED");

  const db = c.get("db");
  const service = new WorkspacesService(db, c.get("redis"));
  const workspaces = await service.listWorkspaces(
    auth.orgId,
    auth.userId,
    auth.orgRole === "org_admin",
  );

  return c.json(workspaces);
});

// ── Member management ─────────────────────────────────────────

// GET /workspaces/:wsId/members
workspacesRoutes.get("/:wsId/members", requireWsMember(), async (c) => {
  const db = c.get("db");
  const wsId = c.req.param("wsId");

  const service = new WorkspacesService(db, c.get("redis"));
  const members = await service.listMembers(wsId);

  return c.json(
    members.map((m) => ({
      userId: m.userId,
      name: m.userName,
      email: m.userEmail,
      role: m.role,
      createdAt: m.createdAt.toISOString(),
    })),
  );
});

// POST /workspaces/:wsId/members
workspacesRoutes.post(
  "/:wsId/members",
  requirePermission("workspace.members", "manage"),
  zValidator("json", addMemberSchema),
  async (c) => {
    const auth = c.get("auth")!;
    const db = c.get("db");
    const wsId = c.req.param("wsId");
    const body = c.req.valid("json");

    const service = new WorkspacesService(db, c.get("redis"));
    const member = await service.addMember(wsId, body.userId, body.role, auth);

    logAuditEvent(db, {
      orgId: auth.orgId,
      userId: auth.userId,
      action: "member_add",
      resourceType: "workspace_member",
      workspaceId: wsId,
      status: "success",
      details: { targetUserId: body.userId, role: body.role },
      requestId: c.get("requestId"),
    });

    return c.json(
      {
        id: member.id,
        workspaceId: member.workspaceId,
        userId: member.userId,
        role: member.role,
        createdAt: member.createdAt.toISOString(),
      },
      201,
    );
  },
);

// PUT /workspaces/:wsId/members/:userId
workspacesRoutes.put(
  "/:wsId/members/:userId",
  requirePermission("workspace.members", "manage"),
  zValidator("json", updateMemberRoleSchema),
  async (c) => {
    const auth = c.get("auth")!;
    const db = c.get("db");
    const wsId = c.req.param("wsId");
    const userId = c.req.param("userId");
    const { role } = c.req.valid("json");

    const service = new WorkspacesService(db, c.get("redis"));
    const updated = await service.updateMemberRole(wsId, userId, role, auth);

    logAuditEvent(db, {
      orgId: auth.orgId,
      userId: auth.userId,
      action: "member_role_change",
      resourceType: "workspace_member",
      resourceId: updated.id,
      workspaceId: wsId,
      status: "success",
      details: { targetUserId: userId, newRole: role },
      requestId: c.get("requestId"),
    });

    return c.json({
      id: updated.id,
      workspaceId: updated.workspaceId,
      userId: updated.userId,
      role: updated.role,
    });
  },
);

// DELETE /workspaces/:wsId/members/:userId
workspacesRoutes.delete(
  "/:wsId/members/:userId",
  requirePermission("workspace.members", "manage"),
  async (c) => {
    const auth = c.get("auth")!;
    const db = c.get("db");
    const wsId = c.req.param("wsId");
    const userId = c.req.param("userId");

    const service = new WorkspacesService(db, c.get("redis"));
    await service.removeMember(wsId, userId);

    logAuditEvent(db, {
      orgId: auth.orgId,
      userId: auth.userId,
      action: "member_remove",
      resourceType: "workspace_member",
      workspaceId: wsId,
      status: "success",
      details: { targetUserId: userId },
      requestId: c.get("requestId"),
    });

    return c.json({ message: "Member removed" });
  },
);
