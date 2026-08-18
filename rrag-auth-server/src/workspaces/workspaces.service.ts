/**
 * Workspace CRUD + member management service.
 */

import { eq, and, inArray } from "drizzle-orm";
import type { DrizzleDB } from "../db/index.js";
import type { RedisClient } from "../db/redis.js";
import * as schema from "../db/schema.js";
import { AppError } from "../middleware/error-handler.js";
import { checkRoleHierarchy } from "../rbac/permissions.js";
import { resolveWorkspaceRoles } from "../auth/resolve-workspace-roles.js";
import { cacheGet, cacheSet, cacheInvalidateEntity, TTL_LONG, TTL_MEDIUM } from "../cache/cache.js";
import type { AuthContext } from "../types.js";
import type { CreateWorkspaceInput, UpdateWorkspaceInput } from "./workspaces.schemas.js";

export class WorkspacesService {
  private redis?: RedisClient;
  constructor(private db: DrizzleDB, redis?: RedisClient) {
    this.redis = redis;
  }

  // ── Workspace CRUD ──────────────────────────────────────────

  async createWorkspace(orgId: string, input: CreateWorkspaceInput, auth: AuthContext) {
    // Scope-specific validation
    if (input.scope === "organization" && auth.orgRole !== "org_admin") {
      throw new AppError(403, "Only org admins can create organization workspaces", "FORBIDDEN");
    }

    if (input.scope === "personal") {
      // Check if user already has a personal workspace
      const [existing] = await this.db
        .select()
        .from(schema.workspaces)
        .where(
          and(
            eq(schema.workspaces.ownerUserId, auth.userId),
            eq(schema.workspaces.scope, "personal"),
          ),
        );
      if (existing) {
        throw new AppError(409, "You already have a personal workspace", "PERSONAL_WS_EXISTS");
      }
    }

    if (input.scope === "team") {
      if (!input.teamId) {
        throw new AppError(400, "teamId is required for team workspaces", "TEAM_ID_REQUIRED");
      }
      // Verify team exists in org and user is lead or org_admin
      const [team] = await this.db
        .select()
        .from(schema.teams)
        .where(and(eq(schema.teams.id, input.teamId), eq(schema.teams.orgId, orgId)));
      if (!team) {
        throw new AppError(404, "Team not found", "TEAM_NOT_FOUND");
      }
      if (auth.orgRole !== "org_admin") {
        const [lead] = await this.db
          .select()
          .from(schema.teamMembers)
          .where(
            and(
              eq(schema.teamMembers.teamId, input.teamId),
              eq(schema.teamMembers.userId, auth.userId),
              eq(schema.teamMembers.role, "lead"),
            ),
          );
        if (!lead) {
          throw new AppError(403, "Only team leads or org admins can create team workspaces", "FORBIDDEN");
        }
      }
    }

    // Check slug uniqueness within org
    const [existingSlug] = await this.db
      .select()
      .from(schema.workspaces)
      .where(and(eq(schema.workspaces.orgId, orgId), eq(schema.workspaces.slug, input.slug)));
    if (existingSlug) {
      throw new AppError(409, "Workspace slug already exists", "SLUG_EXISTS");
    }

    const [workspace] = await this.db
      .insert(schema.workspaces)
      .values({
        orgId,
        name: input.name,
        slug: input.slug,
        scope: input.scope,
        ownerUserId: input.scope === "personal" ? auth.userId : null,
        ownerTeamId: input.scope === "team" ? input.teamId! : null,
      })
      .returning();

    // For personal + org scope, add creator as admin member
    if (input.scope === "personal" || input.scope === "organization") {
      await this.db.insert(schema.workspaceMembers).values({
        workspaceId: workspace.id,
        userId: auth.userId,
        role: "admin",
      });
    }

    if (this.redis) {
      await cacheInvalidateEntity(this.redis, "ws", orgId);
    }

    return workspace;
  }

  async listWorkspaces(orgId: string, userId: string, isOrgAdmin: boolean) {
    if (isOrgAdmin) {
      // Org admins see all workspaces in the org
      return this.db
        .select()
        .from(schema.workspaces)
        .where(eq(schema.workspaces.orgId, orgId));
    }

    // For regular users, get effective workspace IDs then fetch details
    const effectiveRoles = await resolveWorkspaceRoles(this.db, userId);
    const wsIds = Object.keys(effectiveRoles);

    if (wsIds.length === 0) return [];

    return this.db
      .select()
      .from(schema.workspaces)
      .where(
        and(
          eq(schema.workspaces.orgId, orgId),
          inArray(schema.workspaces.id, wsIds),
        ),
      );
  }

  async getWorkspace(wsId: string, orgId: string) {
    if (this.redis) {
      const cached = await cacheGet<any>(this.redis, "ws", orgId, wsId);
      if (cached) return cached;
    }

    const [workspace] = await this.db
      .select()
      .from(schema.workspaces)
      .where(and(eq(schema.workspaces.id, wsId), eq(schema.workspaces.orgId, orgId)));

    if (!workspace) {
      throw new AppError(404, "Workspace not found", "WORKSPACE_NOT_FOUND");
    }

    if (this.redis) {
      await cacheSet(this.redis, "ws", orgId, workspace, wsId, TTL_LONG);
    }

    return workspace;
  }

  async updateWorkspace(wsId: string, orgId: string, input: UpdateWorkspaceInput) {
    const workspace = await this.getWorkspace(wsId, orgId);

    const [updated] = await this.db
      .update(schema.workspaces)
      .set({
        ...(input.name !== undefined && { name: input.name }),
        updatedAt: new Date(),
      })
      .where(eq(schema.workspaces.id, workspace.id))
      .returning();

    if (this.redis) {
      await cacheInvalidateEntity(this.redis, "ws", orgId, wsId);
    }

    return updated;
  }

  async deleteWorkspace(wsId: string, orgId: string) {
    const workspace = await this.getWorkspace(wsId, orgId);

    // Delete members and API keys first
    await this.db
      .delete(schema.workspaceMembers)
      .where(eq(schema.workspaceMembers.workspaceId, workspace.id));
    await this.db
      .delete(schema.apiKeys)
      .where(eq(schema.apiKeys.workspaceId, workspace.id));
    await this.db
      .delete(schema.workspaces)
      .where(eq(schema.workspaces.id, workspace.id));

    if (this.redis) {
      await cacheInvalidateEntity(this.redis, "ws", orgId, wsId);
    }
  }

  // ── Member management ───────────────────────────────────────

  async listMembers(workspaceId: string) {
    return this.db
      .select({
        userId: schema.workspaceMembers.userId,
        role: schema.workspaceMembers.role,
        createdAt: schema.workspaceMembers.createdAt,
        userName: schema.users.name,
        userEmail: schema.users.email,
      })
      .from(schema.workspaceMembers)
      .innerJoin(schema.users, eq(schema.workspaceMembers.userId, schema.users.id))
      .where(eq(schema.workspaceMembers.workspaceId, workspaceId));
  }

  async addMember(
    workspaceId: string,
    userId: string,
    role: string,
    auth: AuthContext,
  ) {
    // Check workspace exists and belongs to auth's org
    const [workspace] = await this.db
      .select()
      .from(schema.workspaces)
      .where(and(eq(schema.workspaces.id, workspaceId), eq(schema.workspaces.orgId, auth.orgId)));

    if (!workspace) {
      throw new AppError(404, "Workspace not found", "WORKSPACE_NOT_FOUND");
    }

    // Check user exists in same org
    const [user] = await this.db
      .select()
      .from(schema.users)
      .where(and(eq(schema.users.id, userId), eq(schema.users.orgId, auth.orgId)));

    if (!user) {
      throw new AppError(404, "User not found in organization", "USER_NOT_FOUND");
    }

    // Check not already a member
    const [existing] = await this.db
      .select()
      .from(schema.workspaceMembers)
      .where(
        and(
          eq(schema.workspaceMembers.workspaceId, workspaceId),
          eq(schema.workspaceMembers.userId, userId),
        ),
      );

    if (existing) {
      throw new AppError(409, "User is already a member of this workspace", "ALREADY_MEMBER");
    }

    // Prevent privilege escalation
    const actorWsRole = auth.workspaceMemberships[workspaceId] ?? "admin";
    if (!checkRoleHierarchy(actorWsRole, role)) {
      throw new AppError(403, "Cannot assign a role higher than your own", "PRIVILEGE_ESCALATION");
    }

    const [member] = await this.db
      .insert(schema.workspaceMembers)
      .values({ workspaceId, userId, role })
      .returning();

    if (this.redis) {
      await cacheInvalidateEntity(this.redis, "wsmem", workspaceId);
    }

    return member;
  }

  async updateMemberRole(
    workspaceId: string,
    userId: string,
    newRole: string,
    auth: AuthContext,
  ) {
    const [member] = await this.db
      .select()
      .from(schema.workspaceMembers)
      .where(
        and(
          eq(schema.workspaceMembers.workspaceId, workspaceId),
          eq(schema.workspaceMembers.userId, userId),
        ),
      );

    if (!member) {
      throw new AppError(404, "Member not found", "MEMBER_NOT_FOUND");
    }

    // Prevent privilege escalation
    const actorWsRole = auth.workspaceMemberships[workspaceId] ?? "admin";
    if (!checkRoleHierarchy(actorWsRole, newRole)) {
      throw new AppError(403, "Cannot assign a role higher than your own", "PRIVILEGE_ESCALATION");
    }

    const [updated] = await this.db
      .update(schema.workspaceMembers)
      .set({ role: newRole })
      .where(eq(schema.workspaceMembers.id, member.id))
      .returning();

    if (this.redis) {
      await cacheInvalidateEntity(this.redis, "wsmem", workspaceId);
    }

    return updated;
  }

  async removeMember(workspaceId: string, userId: string) {
    const [member] = await this.db
      .select()
      .from(schema.workspaceMembers)
      .where(
        and(
          eq(schema.workspaceMembers.workspaceId, workspaceId),
          eq(schema.workspaceMembers.userId, userId),
        ),
      );

    if (!member) {
      throw new AppError(404, "Member not found", "MEMBER_NOT_FOUND");
    }

    await this.db
      .delete(schema.workspaceMembers)
      .where(eq(schema.workspaceMembers.id, member.id));

    if (this.redis) {
      await cacheInvalidateEntity(this.redis, "wsmem", workspaceId);
    }
  }
}
