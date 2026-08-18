import { eq, and } from "drizzle-orm";
import type { DrizzleDB } from "../db/index.js";
import type { RedisClient } from "../db/redis.js";
import * as schema from "../db/schema.js";
import { AppError } from "../middleware/error-handler.js";
import { cacheGet, cacheSet, cacheInvalidateEntity, TTL_LONG, TTL_MEDIUM } from "../cache/cache.js";

export class TeamsService {
  private redis?: RedisClient;
  constructor(private db: DrizzleDB, redis?: RedisClient) {
    this.redis = redis;
  }

  async createTeam(
    orgId: string,
    input: { name: string; slug: string; description?: string },
    createdBy: string,
  ) {
    const [existing] = await this.db
      .select()
      .from(schema.teams)
      .where(and(eq(schema.teams.orgId, orgId), eq(schema.teams.slug, input.slug)));

    if (existing) {
      throw new AppError(409, "Team slug already exists", "TEAM_SLUG_EXISTS");
    }

    const team = await this.db.transaction(async (tx) => {
      const [t] = await tx
        .insert(schema.teams)
        .values({
          orgId,
          name: input.name,
          slug: input.slug,
          description: input.description ?? null,
          createdBy,
        })
        .returning();

      // Creator auto-added as lead
      await tx.insert(schema.teamMembers).values({
        teamId: t.id,
        userId: createdBy,
        role: "lead",
      });

      return t;
    });

    if (this.redis) {
      await cacheInvalidateEntity(this.redis, "team", orgId);
    }

    return team;
  }

  async listTeams(orgId: string) {
    if (this.redis) {
      const cached = await cacheGet<any[]>(this.redis, "team", orgId, "list");
      if (cached) return cached;
    }

    const rows = await this.db
      .select()
      .from(schema.teams)
      .where(eq(schema.teams.orgId, orgId));

    if (this.redis) {
      await cacheSet(this.redis, "team", orgId, rows, "list", TTL_MEDIUM);
    }

    return rows;
  }

  async getTeam(teamId: string, orgId: string) {
    if (this.redis) {
      const cached = await cacheGet<any>(this.redis, "team", orgId, teamId);
      if (cached) return cached;
    }

    const [team] = await this.db
      .select()
      .from(schema.teams)
      .where(and(eq(schema.teams.id, teamId), eq(schema.teams.orgId, orgId)));

    if (!team) {
      throw new AppError(404, "Team not found", "TEAM_NOT_FOUND");
    }

    if (this.redis) {
      await cacheSet(this.redis, "team", orgId, team, teamId, TTL_LONG);
    }

    return team;
  }

  async updateTeam(
    teamId: string,
    orgId: string,
    input: { name?: string; description?: string | null },
  ) {
    const team = await this.getTeam(teamId, orgId);

    const [updated] = await this.db
      .update(schema.teams)
      .set({
        ...(input.name !== undefined && { name: input.name }),
        ...(input.description !== undefined && { description: input.description }),
        updatedAt: new Date(),
      })
      .where(eq(schema.teams.id, team.id))
      .returning();

    if (this.redis) {
      await cacheInvalidateEntity(this.redis, "team", orgId, teamId);
    }

    return updated;
  }

  async deleteTeam(teamId: string, orgId: string) {
    const team = await this.getTeam(teamId, orgId);

    // Block if team has workspaces
    const [ws] = await this.db
      .select({ id: schema.workspaces.id })
      .from(schema.workspaces)
      .where(eq(schema.workspaces.ownerTeamId, team.id));

    if (ws) {
      throw new AppError(
        409,
        "Team has workspaces. Delete or reassign them first.",
        "TEAM_HAS_WORKSPACES",
      );
    }

    await this.db.delete(schema.teams).where(eq(schema.teams.id, team.id));

    if (this.redis) {
      await cacheInvalidateEntity(this.redis, "team", orgId, teamId);
    }
  }

  async listMembers(teamId: string) {
    return this.db
      .select({
        userId: schema.teamMembers.userId,
        role: schema.teamMembers.role,
        createdAt: schema.teamMembers.createdAt,
        userName: schema.users.name,
        userEmail: schema.users.email,
      })
      .from(schema.teamMembers)
      .innerJoin(schema.users, eq(schema.teamMembers.userId, schema.users.id))
      .where(eq(schema.teamMembers.teamId, teamId));
  }

  async addMember(teamId: string, userId: string, role: string, orgId: string) {
    // Check user is in same org
    const [user] = await this.db
      .select()
      .from(schema.users)
      .where(and(eq(schema.users.id, userId), eq(schema.users.orgId, orgId)));

    if (!user) {
      throw new AppError(404, "User not found in organization", "USER_NOT_FOUND");
    }

    const [existing] = await this.db
      .select()
      .from(schema.teamMembers)
      .where(
        and(
          eq(schema.teamMembers.teamId, teamId),
          eq(schema.teamMembers.userId, userId),
        ),
      );

    if (existing) {
      throw new AppError(409, "User is already a team member", "ALREADY_MEMBER");
    }

    const [member] = await this.db
      .insert(schema.teamMembers)
      .values({ teamId, userId, role })
      .returning();

    return member;
  }

  async updateMemberRole(teamId: string, userId: string, role: string) {
    const [member] = await this.db
      .select()
      .from(schema.teamMembers)
      .where(
        and(
          eq(schema.teamMembers.teamId, teamId),
          eq(schema.teamMembers.userId, userId),
        ),
      );

    if (!member) {
      throw new AppError(404, "Team member not found", "MEMBER_NOT_FOUND");
    }

    const [updated] = await this.db
      .update(schema.teamMembers)
      .set({ role })
      .where(eq(schema.teamMembers.id, member.id))
      .returning();

    return updated;
  }

  async removeMember(teamId: string, userId: string) {
    const [member] = await this.db
      .select()
      .from(schema.teamMembers)
      .where(
        and(
          eq(schema.teamMembers.teamId, teamId),
          eq(schema.teamMembers.userId, userId),
        ),
      );

    if (!member) {
      throw new AppError(404, "Team member not found", "MEMBER_NOT_FOUND");
    }

    await this.db
      .delete(schema.teamMembers)
      .where(eq(schema.teamMembers.id, member.id));
  }

  /** Check if userId is a lead of teamId */
  async isTeamLead(teamId: string, userId: string): Promise<boolean> {
    const [member] = await this.db
      .select()
      .from(schema.teamMembers)
      .where(
        and(
          eq(schema.teamMembers.teamId, teamId),
          eq(schema.teamMembers.userId, userId),
          eq(schema.teamMembers.role, "lead"),
        ),
      );
    return !!member;
  }

  /** Check if userId is any member of teamId */
  async isTeamMember(teamId: string, userId: string): Promise<boolean> {
    const [member] = await this.db
      .select()
      .from(schema.teamMembers)
      .where(
        and(
          eq(schema.teamMembers.teamId, teamId),
          eq(schema.teamMembers.userId, userId),
        ),
      );
    return !!member;
  }
}
