/**
 * Rate limiter middleware tests.
 */

import { describe, it, expect, beforeEach } from "vitest";
import { Hono } from "hono";
import type { AppEnv } from "../../src/types.js";
import { rateLimiterMiddleware } from "../../src/middleware/rate-limiter.js";
import { getTestRedis } from "../helpers.js";

describe("Rate Limiter Middleware", () => {
  let redis: any;

  beforeEach(async () => {
    redis = getTestRedis();
    await redis.flushall();
  });

  it("allows requests under the limit", async () => {
    const app = new Hono<AppEnv>();
    app.use("*", async (c, next) => {
      c.set("redis", redis);
      c.set("auth", undefined);
      c.set("db", {} as any);
      c.set("requestId", "test");
      await next();
    });
    app.use("*", rateLimiterMiddleware);
    app.get("/test", (c) => c.json({ ok: true }));

    const res = await app.request("/test");
    expect(res.status).toBe(200);
    expect(res.headers.get("X-RateLimit-Limit")).toBeDefined();
    expect(res.headers.get("X-RateLimit-Remaining")).toBeDefined();
  });

  it("includes rate limit headers", async () => {
    const app = new Hono<AppEnv>();
    app.use("*", async (c, next) => {
      c.set("redis", redis);
      c.set("auth", undefined);
      c.set("db", {} as any);
      c.set("requestId", "test");
      await next();
    });
    app.use("*", rateLimiterMiddleware);
    app.get("/test", (c) => c.json({ ok: true }));

    const res = await app.request("/test");
    const limit = res.headers.get("X-RateLimit-Limit");
    expect(limit).toBe("1000"); // Our test config sets high limits
  });
});
