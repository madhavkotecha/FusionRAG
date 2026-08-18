/**
 * User listing endpoint tests.
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

describe("GET /users", () => {
  it.skipIf(!db)("lists users for org_admin", async () => {
    const org = await createTestOrg(db!);
    const admin = await createTestUser(db!, org.id, { orgRole: "org_admin" });
    await createTestUser(db!, org.id, { email: "user2@test.com", orgRole: "member" });

    const token = getTestToken(redis, { userId: admin.id, orgId: org.id, orgRole: "org_admin" });

    const res = await app.request("/users", {
      headers: { Authorization: `Bearer ${token}` },
    });

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.length).toBe(2);
  });

  it.skipIf(!db)("rejects non-org_admin", async () => {
    const org = await createTestOrg(db!);
    const member = await createTestUser(db!, org.id, { orgRole: "member" });

    const token = getTestToken(redis, { userId: member.id, orgId: org.id, orgRole: "member" });

    const res = await app.request("/users", {
      headers: { Authorization: `Bearer ${token}` },
    });

    expect(res.status).toBe(403);
  });
});
