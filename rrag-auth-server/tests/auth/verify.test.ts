/**
 * Tests for GET /auth/verify (Traefik ForwardAuth endpoint).
 * JWT tests use ioredis-mock (no DB needed).
 * API key tests require PostgreSQL (skipped if unavailable).
 */

import { describe, it, expect, beforeEach, afterAll } from "vitest";
import { Hono } from "hono";
import type { AppEnv } from "../../src/types.js";
import { createApp } from "../../src/app.js";
import { TokenService } from "../../src/token/token.service.js";
import { getTestRedis } from "../helpers.js";
import { db, redis as dbRedis, app as dbApp } from "../db-setup.js";
import { closeTestDb, cleanDatabase, createTestOrg, createTestUser, createTestWorkspace, createTestMembership } from "../helpers.js";
import * as schema from "../../src/db/schema.js";

// ── JWT-based tests (no DB required) ───────────────────────

describe("GET /auth/verify (JWT)", () => {
  let redis: any;
  let app: Hono<AppEnv>;

  beforeEach(() => {
    redis = getTestRedis();
    app = createApp({} as any, redis);
  });

  it("returns 200 with auth headers for valid JWT", async () => {
    const tokenService = new TokenService(redis);
    const [token] = tokenService.createAccessToken({
      userId: "user-123",
      orgId: "org-456",
      orgRole: "org_admin",
      email: "test@example.com",
      name: "Test User",
      workspaceRoles: { "ws-1": "admin", "ws-2": "developer" },
    });

    const res = await app.request("/auth/verify", {
      headers: { Authorization: `Bearer ${token}` },
    });

    expect(res.status).toBe(200);
    expect(res.headers.get("X-Auth-User-Id")).toBe("user-123");
    expect(res.headers.get("X-Auth-Org-Id")).toBe("org-456");
    expect(res.headers.get("X-Auth-Org-Role")).toBe("org_admin");
    expect(res.headers.get("X-Auth-Email")).toBe("test@example.com");

    const wsRoles = JSON.parse(res.headers.get("X-Auth-Workspace-Roles")!);
    expect(wsRoles).toEqual({ "ws-1": "admin", "ws-2": "developer" });
  });

  it("returns 401 for missing authentication", async () => {
    const res = await app.request("/auth/verify");

    expect(res.status).toBe(401);
    const body = await res.json();
    expect(body.code).toBe("AUTH_REQUIRED");
  });

  it("returns 401 for invalid JWT", async () => {
    const res = await app.request("/auth/verify", {
      headers: { Authorization: "Bearer invalid-token-here" },
    });

    expect(res.status).toBe(401);
    const body = await res.json();
    expect(body.code).toBe("INVALID_TOKEN");
  });

  it("returns 401 for blacklisted JWT", async () => {
    const tokenService = new TokenService(redis);
    const [token, jti] = tokenService.createAccessToken({
      userId: "user-123",
      orgId: "org-456",
      orgRole: "member",
      email: "test@example.com",
      name: "Test User",
      workspaceRoles: {},
    });

    await tokenService.blacklistAccessToken(jti, 900);

    const res = await app.request("/auth/verify", {
      headers: { Authorization: `Bearer ${token}` },
    });

    expect(res.status).toBe(401);
    const body = await res.json();
    expect(body.code).toBe("TOKEN_REVOKED");
  });
});

// ── API key tests (requires DB) ────────────────────────────

beforeEach(async () => {
  if (!db) return;
  await cleanDatabase(db);
  await dbRedis.flushall();
});

afterAll(async () => {
  await closeTestDb();
});

describe("GET /auth/verify (API Key)", () => {
  it.skipIf(!db)("returns 200 with auth headers for valid API key", async () => {
    const org = await createTestOrg(db!);
    const user = await createTestUser(db!, org.id);
    const ws = await createTestWorkspace(db!, org.id);
    await createTestMembership(db!, ws.id, user.id, "admin");

    // Create API key
    const rawKey = "test-api-key-for-verify";
    const keyHash = TokenService.hashToken(rawKey);
    await db!.insert(schema.apiKeys).values({
      workspaceId: ws.id,
      name: "Test Key",
      keyPrefix: "test",
      keyHash,
      role: "developer",
      createdBy: user.id,
      status: "active",
    });

    const res = await dbApp.request("/auth/verify", {
      headers: { "X-API-Key": rawKey },
    });

    expect(res.status).toBe(200);
    expect(res.headers.get("X-Auth-User-Id")).toBe(user.id);
    expect(res.headers.get("X-Auth-Org-Id")).toBe(org.id);
    expect(res.headers.get("X-Auth-Org-Role")).toBe("member");

    const wsRoles = JSON.parse(res.headers.get("X-Auth-Workspace-Roles")!);
    expect(wsRoles).toEqual({ [ws.id]: "developer" });
  });

  it.skipIf(!db)("returns 401 for invalid API key", async () => {
    const res = await dbApp.request("/auth/verify", {
      headers: { "X-API-Key": "nonexistent-key" },
    });

    expect(res.status).toBe(401);
    const body = await res.json();
    expect(body.code).toBe("INVALID_API_KEY");
  });
});
