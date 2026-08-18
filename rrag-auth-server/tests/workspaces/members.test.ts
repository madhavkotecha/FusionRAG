/**
 * Workspace member endpoint tests.
 */

import { describe, it, expect, beforeEach, afterAll } from "vitest";
import { db, redis, app } from "../db-setup.js";
import {
  closeTestDb,
  cleanDatabase,
  createTestOrg,
  createTestUser,
  createTestWorkspace,
  createTestMembership,
  getTestToken,
} from "../helpers.js";

beforeEach(async () => {
  if (!db) return;
  await cleanDatabase(db);
  await redis.flushall();
});

afterAll(async () => { await closeTestDb(); });

describe("Workspace Members", () => {
  it.skipIf(!db)("lists workspace members", async () => {
    const org = await createTestOrg(db!);
    const admin = await createTestUser(db!, org.id, { orgRole: "org_admin" });
    const ws = await createTestWorkspace(db!, org.id);
    await createTestMembership(db!, ws.id, admin.id, "admin");

    const token = getTestToken(redis, {
      userId: admin.id,
      orgId: org.id,
      orgRole: "org_admin",
      workspaceRoles: { [ws.id]: "admin" },
    });

    const res = await app.request(`/workspaces/${ws.id}/members`, {
      headers: { Authorization: `Bearer ${token}` },
    });

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.length).toBe(1);
    expect(body[0].role).toBe("admin");
  });

  it.skipIf(!db)("adds a member to workspace", async () => {
    const org = await createTestOrg(db!);
    const admin = await createTestUser(db!, org.id, { orgRole: "org_admin" });
    const user2 = await createTestUser(db!, org.id, { email: "user2@test.com", orgRole: "member" });
    const ws = await createTestWorkspace(db!, org.id);
    await createTestMembership(db!, ws.id, admin.id, "admin");

    const token = getTestToken(redis, {
      userId: admin.id,
      orgId: org.id,
      orgRole: "org_admin",
      workspaceRoles: { [ws.id]: "admin" },
    });

    const res = await app.request(`/workspaces/${ws.id}/members`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ userId: user2.id, role: "developer" }),
    });

    expect(res.status).toBe(201);
    const body = await res.json();
    expect(body.userId).toBe(user2.id);
    expect(body.role).toBe("developer");
  });

  it.skipIf(!db)("removes a member from workspace", async () => {
    const org = await createTestOrg(db!);
    const admin = await createTestUser(db!, org.id, { orgRole: "org_admin" });
    const user2 = await createTestUser(db!, org.id, { email: "remove@test.com", orgRole: "member" });
    const ws = await createTestWorkspace(db!, org.id);
    await createTestMembership(db!, ws.id, admin.id, "admin");
    await createTestMembership(db!, ws.id, user2.id, "developer");

    const token = getTestToken(redis, {
      userId: admin.id,
      orgId: org.id,
      orgRole: "org_admin",
      workspaceRoles: { [ws.id]: "admin" },
    });

    const res = await app.request(`/workspaces/${ws.id}/members/${user2.id}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });

    expect(res.status).toBe(200);
  });

  it.skipIf(!db)("rejects non-member access", async () => {
    const org = await createTestOrg(db!);
    const outsider = await createTestUser(db!, org.id, { orgRole: "member" });
    const ws = await createTestWorkspace(db!, org.id);

    // outsider has no workspace memberships
    const token = getTestToken(redis, {
      userId: outsider.id,
      orgId: org.id,
      orgRole: "member",
      workspaceRoles: {},
    });

    const res = await app.request(`/workspaces/${ws.id}/members`, {
      headers: { Authorization: `Bearer ${token}` },
    });

    expect(res.status).toBe(403);
  });
});
