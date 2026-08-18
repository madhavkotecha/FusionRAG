/**
 * Resolve the effective workspace roles for a user by unioning three sources:
 *   1. Direct workspace_members rows
 *   2. Personal workspace ownership (scope='personal', ownerUserId=userId)
 *   3. Team-derived access (user's teams → team-owned workspaces)
 *
 * Higher role wins when multiple paths grant access to the same workspace.
 */

import { eq, and, inArray } from "drizzle-orm";
import * as schema from "../db/schema.js";

const ROLE_RANK: Record<string, number> = { viewer: 0, developer: 1, admin: 2 };

function mergeRole(existing: string | undefined, incoming: string): string {
  if (!existing) return incoming;
  return (ROLE_RANK[incoming] ?? 0) > (ROLE_RANK[existing] ?? 0)
    ? incoming
    : existing;
}

export async function resolveWorkspaceRoles(
  db: any,
  userId: string,
): Promise<Record<string, string>> {
  const wsRoles: Record<string, string> = {};

  // 1. Direct workspace_members
  const directMemberships = await db
    .select({
      workspaceId: schema.workspaceMembers.workspaceId,
      role: schema.workspaceMembers.role,
    })
    .from(schema.workspaceMembers)
    .where(eq(schema.workspaceMembers.userId, userId));

  for (const m of directMemberships) {
    wsRoles[m.workspaceId] = mergeRole(wsRoles[m.workspaceId], m.role);
  }

  // 2. Personal workspaces (scope='personal', ownerUserId=userId)
  const personalWorkspaces = await db
    .select({ id: schema.workspaces.id })
    .from(schema.workspaces)
    .where(
      and(
        eq(schema.workspaces.ownerUserId, userId),
        eq(schema.workspaces.scope, "personal"),
      ),
    );

  for (const pw of personalWorkspaces) {
    wsRoles[pw.id] = mergeRole(wsRoles[pw.id], "admin");
  }

  // 3. Team-derived workspaces
  const userTeams = await db
    .select({
      teamId: schema.teamMembers.teamId,
      teamRole: schema.teamMembers.role,
    })
    .from(schema.teamMembers)
    .where(eq(schema.teamMembers.userId, userId));

  if (userTeams.length > 0) {
    const teamIds = userTeams.map((t: { teamId: string }) => t.teamId);
    const teamRoleMap: Record<string, string> = {};
    for (const t of userTeams) {
      teamRoleMap[t.teamId] = t.teamRole;
    }

    const teamWorkspaces = await db
      .select({
        id: schema.workspaces.id,
        ownerTeamId: schema.workspaces.ownerTeamId,
      })
      .from(schema.workspaces)
      .where(
        and(
          inArray(schema.workspaces.ownerTeamId, teamIds),
          eq(schema.workspaces.scope, "team"),
        ),
      );

    for (const tw of teamWorkspaces) {
      const teamRole = teamRoleMap[tw.ownerTeamId!];
      const wsRole = teamRole === "lead" ? "admin" : "developer";
      wsRoles[tw.id] = mergeRole(wsRoles[tw.id], wsRole);
    }
  }

  return wsRoles;
}
