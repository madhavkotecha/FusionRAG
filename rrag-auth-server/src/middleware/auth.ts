/**
 * Authentication middleware: Keycloak JWT (JWKS) + API key validation.
 * Validates KC tokens, looks up user in DB for org/workspace context.
 */

import { createMiddleware } from "hono/factory";
import type { AppEnv, AuthContext } from "../types.js";
import { TokenService } from "../token/token.service.js";
import { validateKcToken } from "../oidc/kc-jwt.js";
import { resolveWorkspaceRoles } from "../auth/resolve-workspace-roles.js";
import { resolveOrProvision } from "../auth/user-provisioning.js";
import { AppError } from "./error-handler.js";
import { eq, and } from "drizzle-orm";
import * as schema from "../db/schema.js";

/** Paths that do not require authentication. */
const PUBLIC_PATHS = [
  "/auth/verify",
  "/auth/oidc/config",
  "/auth/logout",
  "/health",
];

/**
 * Build AuthContext from a DB user row.
 * Computes effective workspace roles from direct memberships,
 * personal ownership, and team-derived access.
 */
async function buildAuthContext(
  db: any,
  user: any,
  kcName: string,
): Promise<AuthContext | null> {
  if (!user || user.status !== "active") return null;

  const wsRoles = await resolveWorkspaceRoles(db, user.id);

  return {
    userId: user.id,
    orgId: user.orgId,
    orgRole: user.orgRole,
    email: user.email,
    name: user.name || kcName,
    workspaceMemberships: wsRoles,
    isPlatformAdmin: user.isPlatformAdmin ?? false,
  };
}

export const authMiddleware = createMiddleware<AppEnv>(async (c, next) => {
  // Skip auth for public paths
  const path = c.req.path;
  if (PUBLIC_PATHS.some((p) => path === p || path === `/api/v1${p}`)) {
    c.set("auth", undefined);
    await next();
    return;
  }

  const db = c.get("db");

  // Try Bearer token (Keycloak JWT)
  const authHeader = c.req.header("Authorization");
  if (authHeader?.startsWith("Bearer ")) {
    const token = authHeader.slice(7);
    try {
      const claims = await validateKcToken(token);
      // Auto-provision on first SSO login, then build auth context
      const user = await resolveOrProvision(db, claims);
      const kcName = claims.name || claims.preferred_username || claims.email;
      const authContext = await buildAuthContext(db, user, kcName);

      if (!authContext) {
        throw new AppError(401, "User not provisioned", "USER_NOT_PROVISIONED");
      }

      c.set("auth", authContext);
      await next();
      return;
    } catch (err) {
      if (err instanceof AppError) throw err;
      throw new AppError(401, "Invalid or expired token", "INVALID_TOKEN");
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
      throw new AppError(401, "Invalid API key", "INVALID_API_KEY");
    }

    if (keyRecord.expiresAt && new Date(keyRecord.expiresAt) < new Date()) {
      throw new AppError(401, "API key has expired", "API_KEY_EXPIRED");
    }

    const [workspace] = await db
      .select()
      .from(schema.workspaces)
      .where(eq(schema.workspaces.id, keyRecord.workspaceId));

    if (!workspace) {
      throw new AppError(401, "API key workspace not found", "INVALID_API_KEY");
    }

    // Update last_used_at (fire and forget)
    db.update(schema.apiKeys)
      .set({ lastUsedAt: new Date() })
      .where(eq(schema.apiKeys.id, keyRecord.id))
      .then(() => {})
      .catch(() => {});

    const authContext: AuthContext = {
      userId: keyRecord.createdBy,
      orgId: workspace.orgId,
      orgRole: "member",
      email: "",
      name: `API Key: ${keyRecord.name}`,
      workspaceMemberships: { [keyRecord.workspaceId]: keyRecord.role },
      isPlatformAdmin: false,
    };

    c.set("auth", authContext);
    await next();
    return;
  }

  throw new AppError(401, "Authentication required", "AUTH_REQUIRED");
});
