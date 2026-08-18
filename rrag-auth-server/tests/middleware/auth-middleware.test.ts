/**
 * Tests for auth middleware (JWT verification, public paths).
 * Uses ioredis-mock and a minimal Hono app.
 */

import { describe, it, expect, beforeEach } from "vitest";
import { Hono } from "hono";
import type { AppEnv } from "../../src/types.js";
import { authMiddleware } from "../../src/middleware/auth.js";
import { errorHandler } from "../../src/middleware/error-handler.js";
import { TokenService } from "../../src/token/token.service.js";
import { getTestRedis } from "../helpers.js";

function createMinimalApp(redis: any) {
  const app = new Hono<AppEnv>();

  // Error handler must be registered to convert AppError to proper status codes
  app.onError(errorHandler);

  // Inject mock db and redis
  app.use("*", async (c, next) => {
    c.set("db", {} as any);
    c.set("redis", redis);
    await next();
  });

  app.use("*", authMiddleware);

  // Public routes
  app.post("/auth/login", (c) => c.json({ public: true }));
  app.post("/auth/register", (c) => c.json({ public: true }));
  app.post("/auth/token/refresh", (c) => c.json({ public: true }));
  app.get("/health", (c) => c.json({ status: "ok" }));

  // Protected route
  app.get("/protected", (c) => {
    const auth = c.get("auth");
    return c.json({ userId: auth?.userId ?? null });
  });

  return app;
}

describe("Auth Middleware", () => {
  let redis: any;
  let app: Hono<AppEnv>;

  beforeEach(() => {
    redis = getTestRedis();
    app = createMinimalApp(redis);
  });

  it("allows public paths without authentication", async () => {
    const res = await app.request("/auth/login", { method: "POST", body: "{}" });
    expect(res.status).not.toBe(401);
  });

  it("allows health check without authentication", async () => {
    const res = await app.request("/health");
    expect(res.status).toBe(200);
  });

  it("rejects protected routes without token", async () => {
    const res = await app.request("/protected");
    expect(res.status).toBe(401);
    const body = await res.json();
    expect(body.code).toBe("AUTH_REQUIRED");
  });

  it("accepts valid JWT Bearer token", async () => {
    const tokenService = new TokenService(redis);
    const [token] = tokenService.createAccessToken({
      userId: "user-1",
      orgId: "org-1",
      orgRole: "org_admin",
      email: "test@test.com",
      name: "Test",
      workspaceRoles: {},
    });

    const res = await app.request("/protected", {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.userId).toBe("user-1");
  });

  it("rejects invalid JWT token", async () => {
    const res = await app.request("/protected", {
      headers: { Authorization: "Bearer invalid-token" },
    });
    expect(res.status).toBe(401);
    const body = await res.json();
    expect(body.code).toBe("INVALID_TOKEN");
  });

  it("rejects blacklisted JWT token", async () => {
    const tokenService = new TokenService(redis);
    const [token, jti] = tokenService.createAccessToken({
      userId: "user-1",
      orgId: "org-1",
      orgRole: "org_admin",
      email: "test@test.com",
      name: "Test",
      workspaceRoles: {},
    });

    // Blacklist the token
    await tokenService.blacklistAccessToken(jti, 900);

    const res = await app.request("/protected", {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(res.status).toBe(401);
    const body = await res.json();
    expect(body.code).toBe("TOKEN_REVOKED");
  });
});
