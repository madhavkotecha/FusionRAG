/**
 * User management service.
 */

import crypto from "node:crypto";
import { eq, and } from "drizzle-orm";
import type { DrizzleDB } from "../db/index.js";
import type { RedisClient } from "../db/redis.js";
import * as schema from "../db/schema.js";
import { TokenService } from "../token/token.service.js";
import { config } from "../config.js";
import { AppError } from "../middleware/error-handler.js";
import { cacheGet, cacheSet, cacheInvalidateEntity, TTL_MEDIUM } from "../cache/cache.js";
import type { InviteUserInput } from "./users.schemas.js";

export class UsersService {
  private redis?: RedisClient;
  constructor(private db: DrizzleDB, redis?: RedisClient) {
    this.redis = redis;
  }

  async listOrgUsers(orgId: string) {
    if (this.redis) {
      const cached = await cacheGet<any[]>(this.redis, "user", orgId, "list");
      if (cached) return cached;
    }

    const rows = await this.db
      .select({
        id: schema.users.id,
        email: schema.users.email,
        name: schema.users.name,
        orgRole: schema.users.orgRole,
        status: schema.users.status,
        lastLoginAt: schema.users.lastLoginAt,
        createdAt: schema.users.createdAt,
      })
      .from(schema.users)
      .where(eq(schema.users.orgId, orgId));

    if (this.redis) {
      await cacheSet(this.redis, "user", orgId, rows, "list", TTL_MEDIUM);
    }

    return rows;
  }

  async createInvitation(orgId: string, invitedBy: string, input: InviteUserInput) {
    // Check if user already exists in org
    const [existing] = await this.db
      .select()
      .from(schema.users)
      .where(and(eq(schema.users.orgId, orgId), eq(schema.users.email, input.email)));

    if (existing) {
      throw new AppError(409, "User already exists in this organization", "USER_EXISTS");
    }

    // Check for pending invitation
    const [pendingInvite] = await this.db
      .select()
      .from(schema.userInvitations)
      .where(
        and(
          eq(schema.userInvitations.orgId, orgId),
          eq(schema.userInvitations.email, input.email),
          eq(schema.userInvitations.status, "pending"),
        ),
      );

    if (pendingInvite) {
      throw new AppError(409, "Pending invitation already exists for this email", "INVITE_EXISTS");
    }

    const token = crypto.randomBytes(32).toString("base64url");
    const tokenHash = TokenService.hashToken(token);
    const expiresAt = new Date(Date.now() + config.invitationExpireHours * 60 * 60 * 1000);

    const [invitation] = await this.db
      .insert(schema.userInvitations)
      .values({
        orgId,
        email: input.email,
        workspaceId: input.workspaceId,
        role: input.role,
        tokenHash,
        invitedBy,
        expiresAt,
      })
      .returning();

    return { invitation, token };
  }

  async updateUserRole(orgId: string, userId: string, orgRole: string) {
    const [user] = await this.db
      .select()
      .from(schema.users)
      .where(and(eq(schema.users.id, userId), eq(schema.users.orgId, orgId)));

    if (!user) {
      throw new AppError(404, "User not found", "USER_NOT_FOUND");
    }

    const [updated] = await this.db
      .update(schema.users)
      .set({ orgRole, updatedAt: new Date() })
      .where(eq(schema.users.id, userId))
      .returning();

    if (this.redis) {
      await cacheInvalidateEntity(this.redis, "user", orgId, userId);
    }

    return updated;
  }

  async updateUserStatus(orgId: string, userId: string, status: string) {
    const [user] = await this.db
      .select()
      .from(schema.users)
      .where(and(eq(schema.users.id, userId), eq(schema.users.orgId, orgId)));

    if (!user) {
      throw new AppError(404, "User not found", "USER_NOT_FOUND");
    }

    const [updated] = await this.db
      .update(schema.users)
      .set({ status, updatedAt: new Date() })
      .where(eq(schema.users.id, userId))
      .returning();

    if (this.redis) {
      await cacheInvalidateEntity(this.redis, "user", orgId, userId);
    }

    return updated;
  }
}
