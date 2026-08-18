import { Hono } from "hono";
import { zValidator } from "@hono/zod-validator";
import type { AppEnv } from "../types.js";
import { TeamsService } from "./teams.service.js";
import {
  createTeamSchema,
  updateTeamSchema,
  addTeamMemberSchema,
  updateTeamMemberRoleSchema,
} from "./teams.schemas.js";
import { requireOrgAdmin } from "../rbac/rbac.middleware.js";
import { logAuditEvent } from "../audit/audit.logger.js";
import { AppError } from "../middleware/error-handler.js";

export const teamsRoutes = new Hono<AppEnv>();

/** Require org_admin or team lead for the given :teamId */
async function requireLeadOrAdmin(
  service: TeamsService,
  teamId: string,
  auth: { userId: string; orgRole: string },
) {
  if (auth.orgRole === "org_admin") return;
  const isLead = await service.isTeamLead(teamId, auth.userId);
  if (!isLead) {
    throw new AppError(403, "Requires org admin or team lead", "FORBIDDEN");
  }
}

// POST /teams — create team (org_admin only)
teamsRoutes.post(
  "/",
  requireOrgAdmin(),
  zValidator("json", createTeamSchema),
  async (c) => {
    const auth = c.get("auth")!;
    const db = c.get("db");
    const body = c.req.valid("json");

    const service = new TeamsService(db, c.get("redis"));
    const team = await service.createTeam(auth.orgId, body, auth.userId);

    logAuditEvent(db, {
      orgId: auth.orgId,
      userId: auth.userId,
      action: "team_create",
      resourceType: "team",
      resourceId: team.id,
      status: "success",
      details: { name: body.name, slug: body.slug },
      requestId: c.get("requestId"),
    });

    return c.json(team, 201);
  },
);

// GET /teams — list teams in org
teamsRoutes.get("/", async (c) => {
  const auth = c.get("auth");
  if (!auth) throw new AppError(401, "Authentication required", "AUTH_REQUIRED");

  const db = c.get("db");
  const service = new TeamsService(db, c.get("redis"));
  const teams = await service.listTeams(auth.orgId);

  return c.json(teams);
});

// GET /teams/:teamId — get team
teamsRoutes.get("/:teamId", async (c) => {
  const auth = c.get("auth");
  if (!auth) throw new AppError(401, "Authentication required", "AUTH_REQUIRED");

  const db = c.get("db");
  const teamId = c.req.param("teamId");
  const service = new TeamsService(db, c.get("redis"));
  const team = await service.getTeam(teamId, auth.orgId);

  return c.json(team);
});

// PUT /teams/:teamId — update team (org_admin or team lead)
teamsRoutes.put(
  "/:teamId",
  zValidator("json", updateTeamSchema),
  async (c) => {
    const auth = c.get("auth");
    if (!auth) throw new AppError(401, "Authentication required", "AUTH_REQUIRED");

    const db = c.get("db");
    const teamId = c.req.param("teamId");
    const body = c.req.valid("json");

    const service = new TeamsService(db, c.get("redis"));
    await requireLeadOrAdmin(service, teamId, auth);

    const updated = await service.updateTeam(teamId, auth.orgId, body);

    logAuditEvent(db, {
      orgId: auth.orgId,
      userId: auth.userId,
      action: "team_update",
      resourceType: "team",
      resourceId: teamId,
      status: "success",
      details: body,
      requestId: c.get("requestId"),
    });

    return c.json(updated);
  },
);

// DELETE /teams/:teamId — delete team (org_admin only)
teamsRoutes.delete("/:teamId", requireOrgAdmin(), async (c) => {
  const auth = c.get("auth")!;
  const db = c.get("db");
  const teamId = c.req.param("teamId");

  const service = new TeamsService(db, c.get("redis"));
  await service.deleteTeam(teamId, auth.orgId);

  logAuditEvent(db, {
    orgId: auth.orgId,
    userId: auth.userId,
    action: "team_delete",
    resourceType: "team",
    resourceId: teamId,
    status: "success",
    requestId: c.get("requestId"),
  });

  return c.json({ message: "Team deleted" });
});

// GET /teams/:teamId/members — list members
teamsRoutes.get("/:teamId/members", async (c) => {
  const auth = c.get("auth");
  if (!auth) throw new AppError(401, "Authentication required", "AUTH_REQUIRED");

  const db = c.get("db");
  const teamId = c.req.param("teamId");

  const service = new TeamsService(db, c.get("redis"));
  // Verify team exists in org
  await service.getTeam(teamId, auth.orgId);

  // Check: org_admin or team member
  if (auth.orgRole !== "org_admin") {
    const isMember = await service.isTeamMember(teamId, auth.userId);
    if (!isMember) {
      throw new AppError(403, "Not a member of this team", "FORBIDDEN");
    }
  }

  const members = await service.listMembers(teamId);

  return c.json(
    members.map((m) => ({
      userId: m.userId,
      name: m.userName,
      email: m.userEmail,
      role: m.role,
      createdAt: m.createdAt.toISOString(),
    })),
  );
});

// POST /teams/:teamId/members — add member
teamsRoutes.post(
  "/:teamId/members",
  zValidator("json", addTeamMemberSchema),
  async (c) => {
    const auth = c.get("auth");
    if (!auth) throw new AppError(401, "Authentication required", "AUTH_REQUIRED");

    const db = c.get("db");
    const teamId = c.req.param("teamId");
    const body = c.req.valid("json");

    const service = new TeamsService(db, c.get("redis"));
    await service.getTeam(teamId, auth.orgId);
    await requireLeadOrAdmin(service, teamId, auth);

    const member = await service.addMember(teamId, body.userId, body.role, auth.orgId);

    logAuditEvent(db, {
      orgId: auth.orgId,
      userId: auth.userId,
      action: "team_member_add",
      resourceType: "team_member",
      resourceId: teamId,
      status: "success",
      details: { targetUserId: body.userId, role: body.role },
      requestId: c.get("requestId"),
    });

    return c.json(member, 201);
  },
);

// PUT /teams/:teamId/members/:userId — update member role
teamsRoutes.put(
  "/:teamId/members/:userId",
  zValidator("json", updateTeamMemberRoleSchema),
  async (c) => {
    const auth = c.get("auth");
    if (!auth) throw new AppError(401, "Authentication required", "AUTH_REQUIRED");

    const db = c.get("db");
    const teamId = c.req.param("teamId");
    const userId = c.req.param("userId");
    const { role } = c.req.valid("json");

    const service = new TeamsService(db, c.get("redis"));
    await service.getTeam(teamId, auth.orgId);
    await requireLeadOrAdmin(service, teamId, auth);

    const updated = await service.updateMemberRole(teamId, userId, role);

    logAuditEvent(db, {
      orgId: auth.orgId,
      userId: auth.userId,
      action: "team_member_role_change",
      resourceType: "team_member",
      resourceId: teamId,
      status: "success",
      details: { targetUserId: userId, newRole: role },
      requestId: c.get("requestId"),
    });

    return c.json(updated);
  },
);

// DELETE /teams/:teamId/members/:userId — remove member
teamsRoutes.delete("/:teamId/members/:userId", async (c) => {
  const auth = c.get("auth");
  if (!auth) throw new AppError(401, "Authentication required", "AUTH_REQUIRED");

  const db = c.get("db");
  const teamId = c.req.param("teamId");
  const userId = c.req.param("userId");

  const service = new TeamsService(db, c.get("redis"));
  await service.getTeam(teamId, auth.orgId);
  await requireLeadOrAdmin(service, teamId, auth);

  await service.removeMember(teamId, userId);

  logAuditEvent(db, {
    orgId: auth.orgId,
    userId: auth.userId,
    action: "team_member_remove",
    resourceType: "team_member",
    resourceId: teamId,
    status: "success",
    details: { targetUserId: userId },
    requestId: c.get("requestId"),
  });

  return c.json({ message: "Member removed" });
});
