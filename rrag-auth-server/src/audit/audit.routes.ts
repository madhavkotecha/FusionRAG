/**
 * Audit log routes.
 */

import { Hono } from "hono";
import { zValidator } from "@hono/zod-validator";
import type { AppEnv } from "../types.js";
import { AuditService } from "./audit.service.js";
import { auditLogQuerySchema } from "./audit.schemas.js";
import { AppError } from "../middleware/error-handler.js";
import { hasPermission } from "../rbac/permissions.js";

export const auditRoutes = new Hono<AppEnv>();

// GET /audit-logs
auditRoutes.get("/", async (c) => {
  const auth = c.get("auth");
  if (!auth) throw new AppError(401, "Authentication required", "AUTH_REQUIRED");

  // audit_log:read requires at least workspace admin or org_admin
  if (
    auth.orgRole !== "org_admin" &&
    !auth.isPlatformAdmin &&
    !Object.values(auth.workspaceMemberships).some((role) => role === "admin")
  ) {
    throw new AppError(403, "Insufficient permissions to view audit logs", "FORBIDDEN");
  }

  const db = c.get("db");
  const query = auditLogQuerySchema.parse(c.req.query());

  const service = new AuditService(db);
  const result = await service.queryLogs(auth.orgId, query);

  return c.json(result);
});
