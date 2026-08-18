/**
 * API key routes.
 */

import { Hono } from "hono";
import { zValidator } from "@hono/zod-validator";
import type { AppEnv } from "../types.js";
import { ApiKeysService } from "./api-keys.service.js";
import { createApiKeySchema } from "./api-keys.schemas.js";
import { requireWsMember, requirePermission } from "../rbac/rbac.middleware.js";
import { logAuditEvent } from "../audit/audit.logger.js";

export const apiKeysRoutes = new Hono<AppEnv>();

// GET /workspaces/:wsId/api-keys
apiKeysRoutes.get("/:wsId/api-keys", requireWsMember(), async (c) => {
  const db = c.get("db");
  const wsId = c.req.param("wsId");

  const service = new ApiKeysService(db, c.get("redis"));
  const keys = await service.listApiKeys(wsId);

  return c.json(
    keys.map((k) => ({
      id: k.id,
      name: k.name,
      keyPrefix: k.keyPrefix,
      role: k.role,
      rateLimitRpm: k.rateLimitRpm,
      status: k.status,
      lastUsedAt: k.lastUsedAt?.toISOString() ?? null,
      expiresAt: k.expiresAt?.toISOString() ?? null,
      createdAt: k.createdAt.toISOString(),
    })),
  );
});

// POST /workspaces/:wsId/api-keys
apiKeysRoutes.post(
  "/:wsId/api-keys",
  requirePermission("api_key", "manage"),
  zValidator("json", createApiKeySchema),
  async (c) => {
    const auth = c.get("auth")!;
    const db = c.get("db");
    const wsId = c.req.param("wsId");
    const body = c.req.valid("json");

    const service = new ApiKeysService(db, c.get("redis"));
    const { apiKey, rawKey } = await service.createApiKey(wsId, auth.userId, body);

    logAuditEvent(db, {
      orgId: auth.orgId,
      userId: auth.userId,
      action: "api_key_create",
      resourceType: "api_key",
      resourceId: apiKey.id,
      workspaceId: wsId,
      status: "success",
      details: { name: body.name, role: body.role },
      requestId: c.get("requestId"),
    });

    return c.json(
      {
        id: apiKey.id,
        name: apiKey.name,
        key: rawKey, // Only shown once
        keyPrefix: apiKey.keyPrefix,
        role: apiKey.role,
        expiresAt: apiKey.expiresAt?.toISOString() ?? null,
        createdAt: apiKey.createdAt.toISOString(),
      },
      201,
    );
  },
);

// DELETE /workspaces/:wsId/api-keys/:keyId
apiKeysRoutes.delete(
  "/:wsId/api-keys/:keyId",
  requirePermission("api_key", "manage"),
  async (c) => {
    const auth = c.get("auth")!;
    const db = c.get("db");
    const wsId = c.req.param("wsId");
    const keyId = c.req.param("keyId");

    const service = new ApiKeysService(db, c.get("redis"));
    await service.revokeApiKey(wsId, keyId);

    logAuditEvent(db, {
      orgId: auth.orgId,
      userId: auth.userId,
      action: "api_key_revoke",
      resourceType: "api_key",
      resourceId: keyId,
      workspaceId: wsId,
      status: "success",
      requestId: c.get("requestId"),
    });

    return c.json({ message: "API key revoked" });
  },
);
