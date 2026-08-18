/**
 * Login endpoint tests.
 */

import { describe, it, expect, beforeEach, afterAll } from "vitest";
import bcrypt from "bcryptjs";
import { db, redis, app } from "../db-setup.js";
import { closeTestDb, cleanDatabase, createTestOrg, createTestUser } from "../helpers.js";

beforeEach(async () => {
  if (!db) return;
  await cleanDatabase(db);
  await redis.flushall();
});

afterAll(async () => {
  await closeTestDb();
});

describe("POST /auth/login", () => {
  it.skipIf(!db)("logs in with valid credentials", async () => {
    const org = await createTestOrg(db!);
    const hash = await bcrypt.hash("ValidPass123!", 12);
    const user = await createTestUser(db!, org.id, {
      email: "login@test.com",
      passwordHash: hash,
    });

    const res = await app.request("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: "login@test.com",
        password: "ValidPass123!",
      }),
    });

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.accessToken).toBeDefined();
    expect(body.refreshToken).toBeDefined();
    expect(body.tokenType).toBe("Bearer");
  });

  it.skipIf(!db)("rejects invalid password", async () => {
    const org = await createTestOrg(db!);
    const hash = await bcrypt.hash("ValidPass123!", 12);
    await createTestUser(db!, org.id, {
      email: "login@test.com",
      passwordHash: hash,
    });

    const res = await app.request("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: "login@test.com",
        password: "WrongPassword!",
      }),
    });

    expect(res.status).toBe(401);
    const body = await res.json();
    expect(body.code).toBe("INVALID_CREDENTIALS");
  });

  it.skipIf(!db)("rejects non-existent email", async () => {
    const res = await app.request("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: "nobody@test.com",
        password: "ValidPass123!",
      }),
    });

    expect(res.status).toBe(401);
  });

  it.skipIf(!db)("rejects suspended account", async () => {
    const org = await createTestOrg(db!);
    const hash = await bcrypt.hash("ValidPass123!", 12);
    await createTestUser(db!, org.id, {
      email: "suspended@test.com",
      passwordHash: hash,
      status: "suspended",
    });

    const res = await app.request("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: "suspended@test.com",
        password: "ValidPass123!",
      }),
    });

    expect(res.status).toBe(403);
    const body = await res.json();
    expect(body.code).toBe("ACCOUNT_INACTIVE");
  });

  it.skipIf(!db)("locks account after max failed attempts", async () => {
    const org = await createTestOrg(db!);
    const hash = await bcrypt.hash("ValidPass123!", 12);
    await createTestUser(db!, org.id, {
      email: "lockout@test.com",
      passwordHash: hash,
      failedLoginAttempts: 4, // One attempt away from lockout
    });

    // This 5th attempt should trigger lockout
    await app.request("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: "lockout@test.com",
        password: "WrongPassword!",
      }),
    });

    // Now the account should be locked
    const res = await app.request("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: "lockout@test.com",
        password: "ValidPass123!",
      }),
    });

    expect(res.status).toBe(423);
    const body = await res.json();
    expect(body.code).toBe("ACCOUNT_LOCKED");
  });
});
