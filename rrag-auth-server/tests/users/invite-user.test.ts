/**
 * User invitation endpoint tests.
 */

import { describe, it, expect, beforeEach, afterAll } from "vitest";
import { db, redis, app } from "../db-setup.js";
import {
  closeTestDb,
  cleanDatabase,
  createTestOrg,
  createTestUser,
  getTestToken,
} from "../helpers.js";

beforeEach(async () => {
  if (!db) return;
  await cleanDatabase(db);
  await redis.flushall();
});

afterAll(async () => { await closeTestDb(); });

describe("POST /users/invite", () => {
  it.skipIf(!db)("creates invitation for org_admin", async () => {
    const org = await createTestOrg(db!);
    const admin = await createTestUser(db!, org.id, { orgRole: "org_admin" });

    const token = getTestToken(redis, { userId: admin.id, orgId: org.id, orgRole: "org_admin" });

    const res = await app.request("/users/invite", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({
        email: "newuser@test.com",
        role: "developer",
      }),
    });

    expect(res.status).toBe(201);
    const body = await res.json();
    expect(body.email).toBe("newuser@test.com");
    expect(body.role).toBe("developer");
    expect(body.inviteToken).toBeDefined();
  });

  it.skipIf(!db)("rejects duplicate invitation", async () => {
    const org = await createTestOrg(db!);
    const admin = await createTestUser(db!, org.id, { orgRole: "org_admin" });
    const token = getTestToken(redis, { userId: admin.id, orgId: org.id, orgRole: "org_admin" });

    // First invite
    await app.request("/users/invite", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ email: "dup@test.com", role: "developer" }),
    });

    // Duplicate
    const res = await app.request("/users/invite", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ email: "dup@test.com", role: "developer" }),
    });

    expect(res.status).toBe(409);
  });
});
