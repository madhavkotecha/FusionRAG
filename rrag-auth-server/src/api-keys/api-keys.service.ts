/**
 * API key management service.
 */

import crypto from "node:crypto";
import { eq, and } from "drizzle-orm";
import type { DrizzleDB } from "../db/index.js";
import type { RedisClient } from "../db/redis.js";
import * as schema from "../db/schema.js";
import { TokenService } from "../token/token.service.js";
import { AppError } from "../middleware/error-handler.js";
import { cacheGet, cacheSet, cacheInvalidateEntity, TTL_MEDIUM } from "../cache/cache.js";
import type { CreateApiKeyInput } from "./api-keys.schemas.js";

export class ApiKeysService {
  private redis?: RedisClient;
  constructor(private db: DrizzleDB, redis?: RedisClient) {
    this.redis = redis;
  }

  async listApiKeys(workspaceId: string) {
    if (this.redis) {
      const cached = await cacheGet<any[]>(this.redis, "apikey", workspaceId, "list");
      if (cached) return cached;
    }

    const rows = await this.db
      .select({
        id: schema.apiKeys.id,
        name: schema.apiKeys.name,
        keyPrefix: schema.apiKeys.keyPrefix,
        role: schema.apiKeys.role,
        rateLimitRpm: schema.apiKeys.rateLimitRpm,
        status: schema.apiKeys.status,
        lastUsedAt: schema.apiKeys.lastUsedAt,
        expiresAt: schema.apiKeys.expiresAt,
        createdAt: schema.apiKeys.createdAt,
      })
      .from(schema.apiKeys)
      .where(
        and(
          eq(schema.apiKeys.workspaceId, workspaceId),
          eq(schema.apiKeys.status, "active"),
        ),
      );

    if (this.redis) {
      await cacheSet(this.redis, "apikey", workspaceId, rows, "list", TTL_MEDIUM);
    }

    return rows;
  }

  async createApiKey(
    workspaceId: string,
    createdBy: string,
    input: CreateApiKeyInput,
  ) {
    // Generate API key: rrag_ws_{wsIdShort}_{random}
    const wsIdShort = workspaceId.slice(0, 8);
    const randomPart = crypto.randomBytes(24).toString("base64url");
    const rawKey = `rrag_ws_${wsIdShort}_${randomPart}`;

    const keyPrefix = rawKey.slice(0, 16);
    const keyHash = TokenService.hashToken(rawKey);

    const expiresAt = input.expiresInDays
      ? new Date(Date.now() + input.expiresInDays * 24 * 60 * 60 * 1000)
      : null;

    const [apiKey] = await this.db
      .insert(schema.apiKeys)
      .values({
        workspaceId,
        name: input.name,
        keyPrefix,
        keyHash,
        role: input.role,
        createdBy,
        expiresAt,
      })
      .returning();

    if (this.redis) {
      await cacheInvalidateEntity(this.redis, "apikey", workspaceId);
    }

    return { apiKey, rawKey };
  }

  async revokeApiKey(workspaceId: string, keyId: string) {
    const [key] = await this.db
      .select()
      .from(schema.apiKeys)
      .where(
        and(
          eq(schema.apiKeys.id, keyId),
          eq(schema.apiKeys.workspaceId, workspaceId),
          eq(schema.apiKeys.status, "active"),
        ),
      );

    if (!key) {
      throw new AppError(404, "API key not found", "API_KEY_NOT_FOUND");
    }

    await this.db
      .update(schema.apiKeys)
      .set({ status: "revoked", revokedAt: new Date() })
      .where(eq(schema.apiKeys.id, keyId));

    if (this.redis) {
      await cacheInvalidateEntity(this.redis, "apikey", workspaceId, keyId);
    }
  }
}
