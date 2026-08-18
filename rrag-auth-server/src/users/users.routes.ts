/**
 * User management routes (org_admin only).
 */

import { Hono } from "hono";
import { zValidator } from "@hono/zod-validator";
import type { AppEnv } from "../types.js";
import { UsersService } from "./users.service.js";
import { inviteUserSchema, updateUserRoleSchema, updateUserStatusSchema } from "./users.schemas.js";
import { requireOrgAdmin } from "../rbac/rbac.middleware.js";
import { logAuditEvent } from "../audit/audit.logger.js";
import { AppError } from "../middleware/error-handler.js";

export const usersRoutes = new Hono<AppEnv>();

// All user management routes require org_admin
usersRoutes.use("/*", requireOrgAdmin());

// GET /users
usersRoutes.get("/", async (c) => {
  const auth = c.get("auth")!;
  const db = c.get("db");

  const service = new UsersService(db, c.get("redis"));
  const users = await service.listOrgUsers(auth.orgId);

  return c.json(
    users.map((u) => ({
      id: u.id,
      email: u.email,
      name: u.name,
      orgRole: u.orgRole,
      status: u.status,
      lastLoginAt: u.lastLoginAt instanceof Date ? u.lastLoginAt.toISOString() : (u.lastLoginAt ?? null),
      createdAt: u.createdAt instanceof Date ? u.createdAt.toISOString() : u.createdAt,
    })),
  );
});

// POST /users/invite
usersRoutes.post("/invite", zValidator("json", inviteUserSchema), async (c) => {
  const auth = c.get("auth")!;
  const db = c.get("db");
  const body = c.req.valid("json");

  const service = new UsersService(db, c.get("redis"));
  const { invitation, token } = await service.createInvitation(auth.orgId, auth.userId, body);

  logAuditEvent(db, {
    orgId: auth.orgId,
    userId: auth.userId,
    action: "user_invite",
    resourceType: "invitation",
    resourceId: invitation.id,
    status: "success",
    details: { email: body.email, role: body.role },
    requestId: c.get("requestId"),
  });

  return c.json(
    {
      id: invitation.id,
      email: invitation.email,
      role: invitation.role,
      expiresAt: invitation.expiresAt.toISOString(),
      inviteToken: token,
    },
    201,
  );
});

// PUT /users/:id/role
usersRoutes.put("/:id/role", zValidator("json", updateUserRoleSchema), async (c) => {
  const auth = c.get("auth")!;
  const db = c.get("db");
  const userId = c.req.param("id");
  const { orgRole } = c.req.valid("json");

  const service = new UsersService(db, c.get("redis"));
  const updated = await service.updateUserRole(auth.orgId, userId, orgRole);

  logAuditEvent(db, {
    orgId: auth.orgId,
    userId: auth.userId,
    action: "user_role_change",
    resourceType: "user",
    resourceId: userId,
    status: "success",
    details: { newRole: orgRole },
    requestId: c.get("requestId"),
  });

  return c.json({
    id: updated.id,
    email: updated.email,
    name: updated.name,
    orgRole: updated.orgRole,
    status: updated.status,
  });
});

// PUT /users/:id/status
usersRoutes.put("/:id/status", zValidator("json", updateUserStatusSchema), async (c) => {
  const auth = c.get("auth")!;
  const db = c.get("db");
  const userId = c.req.param("id");
  const { status } = c.req.valid("json");

  const service = new UsersService(db, c.get("redis"));
  const updated = await service.updateUserStatus(auth.orgId, userId, status);

  logAuditEvent(db, {
    orgId: auth.orgId,
    userId: auth.userId,
    action: `user_${status === "suspended" ? "suspend" : "activate"}`,
    resourceType: "user",
    resourceId: userId,
    status: "success",
    requestId: c.get("requestId"),
  });

  return c.json({
    id: updated.id,
    email: updated.email,
    name: updated.name,
    orgRole: updated.orgRole,
    status: updated.status,
  });
});
