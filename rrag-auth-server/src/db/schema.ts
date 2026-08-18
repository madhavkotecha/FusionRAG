/**
 * Drizzle ORM schema definitions for all auth system tables.
 *
 * 12 entities: organizations, users, teams, team_members, workspaces,
 * workspace_members, api_keys, sessions, audit_logs, sso_configs,
 * user_invitations, workspace_access_grants
 */

import {
  pgTable,
  uuid,
  varchar,
  text,
  integer,
  boolean,
  timestamp,
  jsonb,
  uniqueIndex,
  index,
  customType,
} from "drizzle-orm/pg-core";
import { relations } from "drizzle-orm";

// Custom type for bytea (used in sso_configs.clientSecretEncrypted)
const bytea = customType<{ data: Buffer; dpiType: string }>({
  dataType() {
    return "bytea";
  },
});

// ──────────────────────────────────────────────────────────────
// 1. Organizations
// ──────────────────────────────────────────────────────────────

export const organizations = pgTable("organizations", {
  id: uuid("id").primaryKey().defaultRandom(),
  name: varchar("name", { length: 255 }).notNull(),
  slug: varchar("slug", { length: 255 }).notNull().unique(),
  plan: varchar("plan", { length: 50 }).notNull().default("free"),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
});

export const organizationsRelations = relations(organizations, ({ many, one }) => ({
  users: many(users),
  teams: many(teams),
  workspaces: many(workspaces),
  ssoConfig: one(ssoConfigs),
}));

// ──────────────────────────────────────────────────────────────
// 2. Users
// ──────────────────────────────────────────────────────────────

export const users = pgTable(
  "users",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    orgId: uuid("org_id")
      .notNull()
      .references(() => organizations.id),
    email: varchar("email", { length: 320 }).notNull(),
    name: varchar("name", { length: 255 }).notNull(),
    passwordHash: varchar("password_hash", { length: 255 }),
    status: varchar("status", { length: 20 }).notNull().default("active"),
    orgRole: varchar("org_role", { length: 20 }).notNull().default("member"),
    isPlatformAdmin: boolean("is_platform_admin").notNull().default(false),
    failedLoginAttempts: integer("failed_login_attempts").notNull().default(0),
    lockedUntil: timestamp("locked_until", { withTimezone: true }),
    lastLoginAt: timestamp("last_login_at", { withTimezone: true }),
    createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
    updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
  },
  (table) => [
    uniqueIndex("ix_users_org_email").on(table.orgId, table.email),
  ],
);

export const usersRelations = relations(users, ({ one, many }) => ({
  organization: one(organizations, {
    fields: [users.orgId],
    references: [organizations.id],
  }),
  workspaceMemberships: many(workspaceMembers),
  teamMemberships: many(teamMembers),
  sessions: many(sessions),
}));

// ──────────────────────────────────────────────────────────────
// 3. Teams
// ──────────────────────────────────────────────────────────────

export const teams = pgTable(
  "teams",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    orgId: uuid("org_id")
      .notNull()
      .references(() => organizations.id),
    name: varchar("name", { length: 255 }).notNull(),
    slug: varchar("slug", { length: 255 }).notNull(),
    description: text("description"),
    createdBy: uuid("created_by")
      .notNull()
      .references(() => users.id),
    createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
    updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
  },
  (table) => [
    uniqueIndex("ix_teams_org_slug").on(table.orgId, table.slug),
  ],
);

export const teamsRelations = relations(teams, ({ one, many }) => ({
  organization: one(organizations, {
    fields: [teams.orgId],
    references: [organizations.id],
  }),
  members: many(teamMembers),
  workspaces: many(workspaces),
  createdByUser: one(users, {
    fields: [teams.createdBy],
    references: [users.id],
  }),
}));

// ──────────────────────────────────────────────────────────────
// 4. Team Members
// ──────────────────────────────────────────────────────────────

export const teamMembers = pgTable(
  "team_members",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    teamId: uuid("team_id")
      .notNull()
      .references(() => teams.id, { onDelete: "cascade" }),
    userId: uuid("user_id")
      .notNull()
      .references(() => users.id),
    role: varchar("role", { length: 20 }).notNull().default("member"),
    createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  },
  (table) => [
    uniqueIndex("ix_team_members_unique").on(table.teamId, table.userId),
  ],
);

export const teamMembersRelations = relations(teamMembers, ({ one }) => ({
  team: one(teams, {
    fields: [teamMembers.teamId],
    references: [teams.id],
  }),
  user: one(users, {
    fields: [teamMembers.userId],
    references: [users.id],
  }),
}));

// ──────────────────────────────────────────────────────────────
// 5. Workspaces
// ──────────────────────────────────────────────────────────────

export const workspaces = pgTable(
  "workspaces",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    orgId: uuid("org_id")
      .notNull()
      .references(() => organizations.id),
    name: varchar("name", { length: 255 }).notNull(),
    slug: varchar("slug", { length: 255 }).notNull(),
    scope: varchar("scope", { length: 20 }).notNull().default("organization"),
    ownerUserId: uuid("owner_user_id").references(() => users.id),
    ownerTeamId: uuid("owner_team_id").references(() => teams.id),
    createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
    updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
  },
  (table) => [
    uniqueIndex("ix_workspaces_org_slug").on(table.orgId, table.slug),
    index("idx_workspaces_owner_user").on(table.ownerUserId),
    index("idx_workspaces_owner_team").on(table.ownerTeamId),
  ],
);

export const workspacesRelations = relations(workspaces, ({ one, many }) => ({
  organization: one(organizations, {
    fields: [workspaces.orgId],
    references: [organizations.id],
  }),
  members: many(workspaceMembers),
  apiKeys: many(apiKeys),
  ownerUser: one(users, {
    fields: [workspaces.ownerUserId],
    references: [users.id],
  }),
  ownerTeam: one(teams, {
    fields: [workspaces.ownerTeamId],
    references: [teams.id],
  }),
}));

// ──────────────────────────────────────────────────────────────
// 6. Workspace Members
// ──────────────────────────────────────────────────────────────

export const workspaceMembers = pgTable(
  "workspace_members",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    workspaceId: uuid("workspace_id")
      .notNull()
      .references(() => workspaces.id),
    userId: uuid("user_id")
      .notNull()
      .references(() => users.id),
    role: varchar("role", { length: 20 }).notNull().default("developer"),
    createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  },
  (table) => [
    uniqueIndex("ix_ws_members_unique").on(table.workspaceId, table.userId),
  ],
);

export const workspaceMembersRelations = relations(workspaceMembers, ({ one }) => ({
  workspace: one(workspaces, {
    fields: [workspaceMembers.workspaceId],
    references: [workspaces.id],
  }),
  user: one(users, {
    fields: [workspaceMembers.userId],
    references: [users.id],
  }),
}));

// ──────────────────────────────────────────────────────────────
// 7. API Keys
// ──────────────────────────────────────────────────────────────

export const apiKeys = pgTable(
  "api_keys",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    workspaceId: uuid("workspace_id")
      .notNull()
      .references(() => workspaces.id),
    name: varchar("name", { length: 255 }).notNull(),
    keyPrefix: varchar("key_prefix", { length: 16 }).notNull(),
    keyHash: varchar("key_hash", { length: 128 }).notNull().unique(),
    role: varchar("role", { length: 20 }).notNull().default("developer"),
    rateLimitRpm: integer("rate_limit_rpm").notNull().default(600),
    lastUsedAt: timestamp("last_used_at", { withTimezone: true }),
    expiresAt: timestamp("expires_at", { withTimezone: true }),
    status: varchar("status", { length: 20 }).notNull().default("active"),
    createdBy: uuid("created_by").notNull(),
    createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
    revokedAt: timestamp("revoked_at", { withTimezone: true }),
  },
  (table) => [
    index("idx_api_keys_workspace").on(table.workspaceId),
  ],
);

export const apiKeysRelations = relations(apiKeys, ({ one }) => ({
  workspace: one(workspaces, {
    fields: [apiKeys.workspaceId],
    references: [workspaces.id],
  }),
}));

// ──────────────────────────────────────────────────────────────
// 8. Sessions
// ──────────────────────────────────────────────────────────────

export const sessions = pgTable(
  "sessions",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    userId: uuid("user_id")
      .notNull()
      .references(() => users.id),
    refreshTokenHash: varchar("refresh_token_hash", { length: 128 }).notNull().unique(),
    deviceInfo: jsonb("device_info"),
    lastActiveAt: timestamp("last_active_at", { withTimezone: true }).notNull().defaultNow(),
    expiresAt: timestamp("expires_at", { withTimezone: true }).notNull(),
    createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
    revokedAt: timestamp("revoked_at", { withTimezone: true }),
  },
  (table) => [
    index("idx_sessions_user").on(table.userId),
  ],
);

export const sessionsRelations = relations(sessions, ({ one }) => ({
  user: one(users, {
    fields: [sessions.userId],
    references: [users.id],
  }),
}));

// ──────────────────────────────────────────────────────────────
// 9. Audit Logs
// ──────────────────────────────────────────────────────────────

export const auditLogs = pgTable(
  "audit_logs",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    orgId: uuid("org_id").notNull(),
    userId: uuid("user_id"),
    action: varchar("action", { length: 64 }).notNull(),
    resourceType: varchar("resource_type", { length: 64 }).notNull(),
    resourceId: uuid("resource_id"),
    workspaceId: uuid("workspace_id"),
    details: jsonb("details"),
    ipAddress: varchar("ip_address", { length: 45 }),
    userAgent: varchar("user_agent", { length: 512 }),
    requestId: uuid("request_id"),
    status: varchar("status", { length: 16 }).notNull(),
    timestamp: timestamp("timestamp", { withTimezone: true }).notNull().defaultNow(),
  },
  (table) => [
    index("idx_audit_org_time").on(table.orgId, table.timestamp),
    index("idx_audit_user_time").on(table.userId, table.timestamp),
    index("idx_audit_resource").on(table.resourceType, table.resourceId),
    index("idx_audit_action").on(table.action),
  ],
);

// ──────────────────────────────────────────────────────────────
// 10. SSO Configs
// ──────────────────────────────────────────────────────────────

export const ssoConfigs = pgTable("sso_configs", {
  id: uuid("id").primaryKey().defaultRandom(),
  orgId: uuid("org_id")
    .notNull()
    .unique()
    .references(() => organizations.id),
  protocol: varchar("protocol", { length: 10 }).notNull(),
  providerName: varchar("provider_name", { length: 50 }).notNull(),
  metadataUrl: varchar("metadata_url", { length: 1024 }),
  clientId: varchar("client_id", { length: 255 }),
  clientSecretEncrypted: bytea("client_secret_encrypted"),
  issuerUrl: varchar("issuer_url", { length: 1024 }),
  certificate: text("certificate"),
  groupMapping: jsonb("group_mapping"),
  autoProvision: boolean("auto_provision").notNull().default(true),
  enforceSso: boolean("enforce_sso").notNull().default(false),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
});

export const ssoConfigsRelations = relations(ssoConfigs, ({ one }) => ({
  organization: one(organizations, {
    fields: [ssoConfigs.orgId],
    references: [organizations.id],
  }),
}));

// ──────────────────────────────────────────────────────────────
// 11. User Invitations
// ──────────────────────────────────────────────────────────────

export const userInvitations = pgTable(
  "user_invitations",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    orgId: uuid("org_id").notNull(),
    email: varchar("email", { length: 320 }).notNull(),
    workspaceId: uuid("workspace_id"),
    role: varchar("role", { length: 20 }).notNull().default("developer"),
    tokenHash: varchar("token_hash", { length: 128 }).notNull().unique(),
    status: varchar("status", { length: 20 }).notNull().default("pending"),
    invitedBy: uuid("invited_by").notNull(),
    expiresAt: timestamp("expires_at", { withTimezone: true }).notNull(),
    createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
    acceptedAt: timestamp("accepted_at", { withTimezone: true }),
  },
  (table) => [
    index("idx_invitations_email").on(table.email),
  ],
);

// ──────────────────────────────────────────────────────────────
// 12. Workspace Access Grants
// ──────────────────────────────────────────────────────────────

export const workspaceAccessGrants = pgTable("workspace_access_grants", {
  id: uuid("id").primaryKey().defaultRandom(),
  sourceWsId: uuid("source_ws_id").notNull(),
  targetWsId: uuid("target_ws_id").notNull(),
  resourceType: varchar("resource_type", { length: 64 }).notNull(),
  resourceId: uuid("resource_id").notNull(),
  permission: varchar("permission", { length: 20 }).notNull().default("read"),
  grantedBy: uuid("granted_by").notNull(),
  expiresAt: timestamp("expires_at", { withTimezone: true }),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
});
