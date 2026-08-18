/**
 * Logout endpoint tests.
 */

import { describe, it, expect, beforeEach, afterAll } from "vitest";
import { db, redis, app } from "../db-setup.js";
import { closeTestDb, cleanDatabase } from "../helpers.js";

beforeEach(async () => {
  if (!db) return;
  await cleanDatabase(db);
  await redis.flushall();
});

afterAll(async () => {
  await closeTestDb();
});

async function registerAndLogin() {
  const regRes = await app.request("/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email: `user-${Date.now()}@test.com`,
      password: "ValidPass123!",
      name: "Test User",
      orgName: `Org ${Date.now()}`,
      orgSlug: `org-${Date.now()}`,
    }),
  });
  return regRes.json();
}

describe("POST /auth/logout", () => {
  it.skipIf(!db)("logs out single session", async () => {
    const { accessToken, refreshToken } = await registerAndLogin();

    const res = await app.request("/auth/logout", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${accessToken}`,
      },
      body: JSON.stringify({ refreshToken }),
    });

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.message).toBe("Logged out successfully");

    // Refresh token should no longer work
    const refreshRes = await app.request("/auth/token/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refreshToken }),
    });
    expect(refreshRes.status).toBe(401);
  });
});

describe("POST /auth/logout/all", () => {
  it.skipIf(!db)("revokes all sessions", async () => {
    const { accessToken } = await registerAndLogin();

    const res = await app.request("/auth/logout/all", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
    });

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.sessionsRevoked).toBeGreaterThanOrEqual(1);
  });

  it.skipIf(!db)("requires authentication", async () => {
    const res = await app.request("/auth/logout/all", {
      method: "POST",
    });

    expect(res.status).toBe(401);
  });
});
