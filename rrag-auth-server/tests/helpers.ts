/**
 * Test helper utilities and factories.
 */

import { drizzle } from "drizzle-orm/node-postgres";
import pg from "pg";
import * as schema from "../src/db/schema.js";
import type { DrizzleDB } from "../src/db/index.js";
import { TokenService } from "../src/token/token.service.js";
import { createApp } from "../src/app.js";
import type { RedisClient } from "../src/db/redis.js";

// We use ioredis-mock for tests
// @ts-ignore - ioredis-mock types may not perfectly match
import RedisMock from "ioredis-mock";

let _testDb: DrizzleDB | null = null;
let _testPool: pg.Pool | null = null;
let _testRedis: any | null = null;
let _counter = 0;

export function getTestRedis(): RedisClient {
  if (!_testRedis) {
    _testRedis = new RedisMock();
  }
  return _testRedis as RedisClient;
}

export async function getTestDb(): Promise<DrizzleDB> {
  if (_testDb) return _testDb;

  const url = process.env.DATABASE_URL!;
  _testPool = new pg.Pool({ connectionString: url });
  _testDb = drizzle(_testPool, { schema });
  return _testDb;
}

export async function closeTestDb(): Promise<void> {
  if (_testPool) {
    await _testPool.end();
    _testPool = null;
    _testDb = null;
  }
}

export function createTestApp(db: DrizzleDB, redis: RedisClient) {
  return createApp(db, redis);
}

/**
 * Clean all tables in FK-safe order (leaf tables first, then parents).
 */
export async function cleanDatabase(db: DrizzleDB): Promise<void> {
  await db.delete(schema.auditLogs);
  await db.delete(schema.workspaceAccessGrants);
  await db.delete(schema.userInvitations);
  await db.delete(schema.workspaceMembers);
  await db.delete(schema.apiKeys);
  await db.delete(schema.sessions);
  await db.delete(schema.ssoConfigs);
  await db.delete(schema.workspaces);
  await db.delete(schema.users);
  await db.delete(schema.organizations);
}

/**
 * Create a test organization.
 */
export async function createTestOrg(
  db: DrizzleDB,
  overrides?: Partial<typeof schema.organizations.$inferInsert>,
) {
  const id = ++_counter;
  const [org] = await db
    .insert(schema.organizations)
    .values({
      name: "Test Org",
      slug: `test-org-${Date.now()}-${id}`,
      ...overrides,
    })
    .returning();
  return org;
}

/**
 * Create a test user (with hashed password).
 */
export async function createTestUser(
  db: DrizzleDB,
  orgId: string,
  overrides?: Partial<typeof schema.users.$inferInsert>,
) {
  const id = ++_counter;
  // bcryptjs hash for "ValidPass123!"
  const defaultHash = "$2a$12$LJ3m4ys3Gz8L9aU3Xw8mOOGnQNJJAE68GKjP8CsH9HDXZ9sDCIWe";
  const [user] = await db
    .insert(schema.users)
    .values({
      orgId,
      email: `user-${Date.now()}-${id}@test.com`,
      name: "Test User",
      passwordHash: defaultHash,
      orgRole: "org_admin",
      status: "active",
      ...overrides,
    })
    .returning();
  return user;
}

/**
 * Create a test workspace.
 */
export async function createTestWorkspace(
  db: DrizzleDB,
  orgId: string,
  overrides?: Partial<typeof schema.workspaces.$inferInsert>,
) {
  const id = ++_counter;
  const [ws] = await db
    .insert(schema.workspaces)
    .values({
      orgId,
      name: "Test Workspace",
      slug: `test-ws-${Date.now()}-${id}`,
      ...overrides,
    })
    .returning();
  return ws;
}

/**
 * Create a workspace membership.
 */
export async function createTestMembership(
  db: DrizzleDB,
  workspaceId: string,
  userId: string,
  role: string = "admin",
) {
  const [member] = await db
    .insert(schema.workspaceMembers)
    .values({ workspaceId, userId, role })
    .returning();
  return member;
}

/**
 * Generate a valid JWT for testing.
 */
export function getTestToken(
  redis: RedisClient,
  params: {
    userId: string;
    orgId: string;
    orgRole?: string;
    email?: string;
    name?: string;
    workspaceRoles?: Record<string, string>;
  },
): string {
  const tokenService = new TokenService(redis);
  const [token] = tokenService.createAccessToken({
    userId: params.userId,
    orgId: params.orgId,
    orgRole: params.orgRole ?? "org_admin",
    email: params.email ?? "test@test.com",
    name: params.name ?? "Test User",
    workspaceRoles: params.workspaceRoles ?? {},
  });
  return token;
}
