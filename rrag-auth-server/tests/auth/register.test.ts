/**
 * Registration endpoint tests.
 * Requires PostgreSQL to be running (docker-compose up postgres).
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

describe("POST /auth/register", () => {
  it.skipIf(!db)("registers a new user with org and workspace", async () => {
    const res = await app.request("/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: "admin@neworg.com",
        password: "ValidPass123!",
        name: "Admin User",
        orgName: "New Organization",
        orgSlug: "new-org",
      }),
    });

    expect(res.status).toBe(201);
    const body = await res.json();
    expect(body.user.email).toBe("admin@neworg.com");
    expect(body.user.orgRole).toBe("org_admin");
    expect(body.accessToken).toBeDefined();
    expect(body.refreshToken).toBeDefined();
    expect(body.tokenType).toBe("Bearer");
    expect(body.expiresIn).toBe(900); // 15 min
  });

  it.skipIf(!db)("rejects weak password", async () => {
    const res = await app.request("/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: "admin@neworg.com",
        password: "weak",
        name: "Admin User",
        orgName: "New Organization",
        orgSlug: "new-org-2",
      }),
    });

    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.code).toBe("INVALID_PASSWORD");
  });

  it.skipIf(!db)("rejects duplicate org slug", async () => {
    // Register first
    await app.request("/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: "admin1@org.com",
        password: "ValidPass123!",
        name: "Admin",
        orgName: "Org",
        orgSlug: "duplicate-slug",
      }),
    });

    // Try duplicate
    const res = await app.request("/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: "admin2@org.com",
        password: "ValidPass123!",
        name: "Admin 2",
        orgName: "Org 2",
        orgSlug: "duplicate-slug",
      }),
    });

    expect(res.status).toBe(409);
    const body = await res.json();
    expect(body.code).toBe("SLUG_TAKEN");
  });

  it.skipIf(!db)("rejects invalid email format", async () => {
    const res = await app.request("/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: "not-an-email",
        password: "ValidPass123!",
        name: "Admin",
        orgName: "Org",
        orgSlug: "valid-slug",
      }),
    });

    expect(res.status).toBe(400);
  });
});
