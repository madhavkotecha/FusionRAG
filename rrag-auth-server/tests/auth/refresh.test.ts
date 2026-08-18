/**
 * Token refresh endpoint tests.
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

describe("POST /auth/token/refresh", () => {
  it.skipIf(!db)("refreshes tokens with valid refresh token", async () => {
    // Register first to get tokens
    const regRes = await app.request("/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: "refresh@test.com",
        password: "ValidPass123!",
        name: "Test",
        orgName: "Refresh Org",
        orgSlug: "refresh-org",
      }),
    });

    const regBody = await regRes.json();
    const oldRefreshToken = regBody.refreshToken;

    // Refresh
    const res = await app.request("/auth/token/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refreshToken: oldRefreshToken }),
    });

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.accessToken).toBeDefined();
    expect(body.refreshToken).toBeDefined();
    // New refresh token should be different (rotation)
    expect(body.refreshToken).not.toBe(oldRefreshToken);
  });

  it.skipIf(!db)("rejects invalid refresh token", async () => {
    const res = await app.request("/auth/token/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refreshToken: "invalid-token" }),
    });

    expect(res.status).toBe(401);
    const body = await res.json();
    expect(body.code).toBe("INVALID_REFRESH_TOKEN");
  });

  it.skipIf(!db)("rejects reused refresh token (rotation)", async () => {
    // Register
    const regRes = await app.request("/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: "reuse@test.com",
        password: "ValidPass123!",
        name: "Test",
        orgName: "Reuse Org",
        orgSlug: "reuse-org",
      }),
    });

    const regBody = await regRes.json();
    const refreshToken = regBody.refreshToken;

    // First refresh succeeds
    const res1 = await app.request("/auth/token/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refreshToken }),
    });
    expect(res1.status).toBe(200);

    // Second refresh with same token should fail (it was revoked during rotation)
    const res2 = await app.request("/auth/token/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refreshToken }),
    });
    expect(res2.status).toBe(401);
  });
});
