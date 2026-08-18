/**
 * Auth routes: verify (ForwardAuth), me (profile + provisioning), logout.
 * Local login/register/refresh removed — Keycloak is the sole identity provider.
 */

import { Hono } from "hono";
import { eq, and, inArray } from "drizzle-orm";
import type { AppEnv } from "../types.js";
import { TokenService } from "../token/token.service.js";
import { validateKcToken } from "../oidc/kc-jwt.js";
import { resolveWorkspaceRoles } from "./resolve-workspace-roles.js";
import { resolveOrProvision } from "./user-provisioning.js";
import { logAuditEvent } from "../audit/audit.logger.js";
import { AppError } from "../middleware/error-handler.js";
import * as schema from "../db/schema.js";

export const authRoutes = new Hono<AppEnv>();

// ── GET /auth/me — Profile with auto-provisioning ───────────────────

authRoutes.get("/me", async (c) => {
  const auth = c.get("auth");
  if (!auth) throw new AppError(401, "Authentication required", "AUTH_REQUIRED");

  const db = c.get("db");

  // Validate KC token to get claims (for provisioning if needed)
  const authHeader = c.req.header("Authorization");
  if (authHeader?.startsWith("Bearer ")) {
    const token = authHeader.slice(7);
    try {
      const claims = await validateKcToken(token);
      await resolveOrProvision(db, claims);
    } catch {
      // Token already validated by middleware — just proceed with existing auth context
    }
  }

  // Fetch full profile with workspaces
  const [user] = await db
    .select()
    .from(schema.users)
    .where(eq(schema.users.id, auth.userId));

  if (!user) throw new AppError(404, "User not found", "USER_NOT_FOUND");

  // Get all effective workspace roles (direct + personal + team-derived)
  const effectiveRoles = await resolveWorkspaceRoles(db, user.id);
  const wsIds = Object.keys(effectiveRoles);

  const workspaceDetails = wsIds.length > 0
    ? await db
        .select({
          id: schema.workspaces.id,
          name: schema.workspaces.name,
          slug: schema.workspaces.slug,
          scope: schema.workspaces.scope,
        })
        .from(schema.workspaces)
        .where(inArray(schema.workspaces.id, wsIds))
    : [];

  return c.json({
    id: user.id,
    email: user.email,
    name: user.name,
    orgId: user.orgId,
    orgRole: user.orgRole,
    isPlatformAdmin: user.isPlatformAdmin ?? false,
    status: user.status,
    createdAt: user.createdAt.toISOString(),
    workspaces: workspaceDetails.map((ws: any) => ({
      workspaceId: ws.id,
      workspaceName: ws.name,
      workspaceSlug: ws.slug,
      scope: ws.scope,
      role: effectiveRoles[ws.id],
    })),
  });
});

// ── POST /auth/logout — Audit log only (KC handles session revocation) ──

authRoutes.post("/logout", async (c) => {
  const auth = c.get("auth");

  if (auth) {
    const db = c.get("db");
    logAuditEvent(db, {
      orgId: auth.orgId,
      userId: auth.userId,
      action: "logout",
      resourceType: "session",
      status: "success",
      requestId: c.get("requestId"),
    });
  }

  return c.json({ message: "Logged out" });
});

// ── ALL /auth/verify — Traefik ForwardAuth endpoint ─────────────────
// Validates KC JWT or API key, returns X-Auth-* headers for downstream services.

authRoutes.all("/verify", async (c) => {
  const db = c.get("db");

  // Try Bearer token (Keycloak JWT)
  const authHeader = c.req.header("Authorization");
  if (authHeader?.startsWith("Bearer ")) {
    const token = authHeader.slice(7);
    try {
      const claims = await validateKcToken(token);

      // Resolve user from DB to get org/workspace info
      const user = await resolveOrProvision(db, claims);

      // Compute effective workspace roles (direct + personal + team-derived)
      const wsRoles = await resolveWorkspaceRoles(db, user.id);

      c.header("X-Auth-User-Id", user.id);
      c.header("X-Auth-Org-Id", user.orgId);
      c.header("X-Auth-Org-Role", user.orgRole);
      c.header("X-Auth-Email", user.email);
      c.header("X-Auth-Workspace-Roles", JSON.stringify(wsRoles));
      c.header("X-Auth-Platform-Admin", String(user.isPlatformAdmin ?? false));
      return c.json({ status: "ok" }, 200);
    } catch {
      return c.json({ error: "Invalid or expired token", code: "INVALID_TOKEN" }, 401);
    }
  }

  // Try API key
  const apiKeyHeader = c.req.header("X-API-Key");
  if (apiKeyHeader) {
    const keyHash = TokenService.hashToken(apiKeyHeader);

    const [keyRecord] = await db
      .select()
      .from(schema.apiKeys)
      .where(and(eq(schema.apiKeys.keyHash, keyHash), eq(schema.apiKeys.status, "active")));

    if (!keyRecord) {
      return c.json({ error: "Invalid API key", code: "INVALID_API_KEY" }, 401);
    }

    if (keyRecord.expiresAt && new Date(keyRecord.expiresAt) < new Date()) {
      return c.json({ error: "API key has expired", code: "API_KEY_EXPIRED" }, 401);
    }

    const [workspace] = await db
      .select()
      .from(schema.workspaces)
      .where(eq(schema.workspaces.id, keyRecord.workspaceId));

    if (!workspace) {
      return c.json({ error: "API key workspace not found", code: "INVALID_API_KEY" }, 401);
    }

    c.header("X-Auth-User-Id", keyRecord.createdBy);
    c.header("X-Auth-Org-Id", workspace.orgId);
    c.header("X-Auth-Org-Role", "member");
    c.header("X-Auth-Email", "");
    c.header("X-Auth-Workspace-Roles", JSON.stringify({ [keyRecord.workspaceId]: keyRecord.role }));
    c.header("X-Auth-Platform-Admin", "false");
    return c.json({ status: "ok" }, 200);
  }

  return c.json({ error: "Authentication required", code: "AUTH_REQUIRED" }, 401);
});
