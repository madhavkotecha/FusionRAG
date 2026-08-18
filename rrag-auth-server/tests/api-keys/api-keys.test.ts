/**
 * API key endpoint tests.
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

describe("API Keys", () => {
  it.skipIf(!db)("creates and lists API keys", async () => {
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

    // Create API key
    const createRes = await app.request(`/workspaces/${ws.id}/api-keys`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ name: "Test Key", role: "developer" }),
    });

    expect(createRes.status).toBe(201);
    const createBody = await createRes.json();
    expect(createBody.key).toMatch(/^rrag_ws_/);
    expect(createBody.name).toBe("Test Key");
    expect(createBody.role).toBe("developer");

    // List API keys
    const listRes = await app.request(`/workspaces/${ws.id}/api-keys`, {
      headers: { Authorization: `Bearer ${token}` },
    });

    expect(listRes.status).toBe(200);
    const listBody = await listRes.json();
    expect(listBody.length).toBe(1);
    expect(listBody[0].name).toBe("Test Key");
    // Raw key should NOT be in list response
    expect(listBody[0].key).toBeUndefined();
  });

  it.skipIf(!db)("revokes API key", async () => {
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

    // Create API key
    const createRes = await app.request(`/workspaces/${ws.id}/api-keys`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ name: "To Revoke" }),
    });

    const { id: keyId } = await createRes.json();

    // Revoke
    const revokeRes = await app.request(`/workspaces/${ws.id}/api-keys/${keyId}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });

    expect(revokeRes.status).toBe(200);

    // List should be empty
    const listRes = await app.request(`/workspaces/${ws.id}/api-keys`, {
      headers: { Authorization: `Bearer ${token}` },
    });

    const listBody = await listRes.json();
    expect(listBody.length).toBe(0);
  });
});
