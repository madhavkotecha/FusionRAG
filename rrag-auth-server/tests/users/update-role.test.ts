/**
 * User role/status update endpoint tests.
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

describe("PUT /users/:id/role", () => {
  it.skipIf(!db)("updates user org role", async () => {
    const org = await createTestOrg(db!);
    const admin = await createTestUser(db!, org.id, { orgRole: "org_admin" });
    const member = await createTestUser(db!, org.id, { email: "member@test.com", orgRole: "member" });

    const token = getTestToken(redis, { userId: admin.id, orgId: org.id, orgRole: "org_admin" });

    const res = await app.request(`/users/${member.id}/role`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ orgRole: "org_admin" }),
    });

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.orgRole).toBe("org_admin");
  });
});

describe("PUT /users/:id/status", () => {
  it.skipIf(!db)("suspends user", async () => {
    const org = await createTestOrg(db!);
    const admin = await createTestUser(db!, org.id, { orgRole: "org_admin" });
    const member = await createTestUser(db!, org.id, { email: "suspend@test.com", orgRole: "member" });

    const token = getTestToken(redis, { userId: admin.id, orgId: org.id, orgRole: "org_admin" });

    const res = await app.request(`/users/${member.id}/status`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ status: "suspended" }),
    });

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.status).toBe("suspended");
  });
});
