/**
 * RBAC authorization middleware factories.
 */

import { createMiddleware } from "hono/factory";
import type { AppEnv } from "../types.js";
import { hasPermission } from "./permissions.js";
import { AppError } from "../middleware/error-handler.js";

/**
 * Require a specific permission. Extracts workspace ID from route params.
 */
export function requirePermission(resource: string, action: string) {
  return createMiddleware<AppEnv>(async (c, next) => {
    const auth = c.get("auth");
    if (!auth) {
      throw new AppError(401, "Authentication required", "AUTH_REQUIRED");
    }

    const wsId = c.req.param("wsId") ?? null;

    if (!hasPermission(auth, wsId, resource, action)) {
      throw new AppError(
        403,
        `Insufficient permissions: ${resource}:${action}`,
        "FORBIDDEN",
      );
    }

    await next();
  });
}

/**
 * Require org_admin role.
 */
export function requireOrgAdmin() {
  return createMiddleware<AppEnv>(async (c, next) => {
    const auth = c.get("auth");
    if (!auth) {
      throw new AppError(401, "Authentication required", "AUTH_REQUIRED");
    }

    if (auth.orgRole !== "org_admin" && !auth.isPlatformAdmin) {
      throw new AppError(403, "Organization admin access required", "FORBIDDEN");
    }

    await next();
  });
}

/**
 * Require workspace membership (any role).
 */
export function requireWsMember() {
  return createMiddleware<AppEnv>(async (c, next) => {
    const auth = c.get("auth");
    if (!auth) {
      throw new AppError(401, "Authentication required", "AUTH_REQUIRED");
    }

    // Org admins can access any workspace in their org
    if (auth.orgRole === "org_admin" || auth.isPlatformAdmin) {
      await next();
      return;
    }

    const wsId = c.req.param("wsId");
    if (!wsId || !auth.workspaceMemberships[wsId]) {
      throw new AppError(403, "Workspace membership required", "FORBIDDEN");
    }

    await next();
  });
}
