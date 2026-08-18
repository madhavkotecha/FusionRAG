/**
 * Redis-based sliding window rate limiter.
 */

import { createMiddleware } from "hono/factory";
import type { AppEnv } from "../types.js";
import type { RedisClient } from "../db/redis.js";
import { config } from "../config.js";
import { AppError } from "./error-handler.js";

/**
 * Check rate limit using Redis sorted sets (sliding window).
 */
async function checkRateLimit(
  redis: RedisClient,
  key: string,
  limit: number,
  windowSeconds: number = 60,
): Promise<{ allowed: boolean; remaining: number }> {
  const now = Date.now();
  const windowStart = now - windowSeconds * 1000;

  const pipeline = redis.pipeline();
  pipeline.zremrangebyscore(key, 0, windowStart);
  pipeline.zadd(key, now, `${now}:${Math.random()}`);
  pipeline.zcard(key);
  pipeline.expire(key, windowSeconds);
  const results = await pipeline.exec();

  const count = (results?.[2]?.[1] as number) ?? 0;
  return { allowed: count <= limit, remaining: Math.max(0, limit - count) };
}

export const rateLimiterMiddleware = createMiddleware<AppEnv>(async (c, next) => {
  const redis = c.get("redis");
  const auth = c.get("auth");

  let key: string;
  let limit: number;

  if (auth) {
    // Authenticated user
    key = `ratelimit:user:${auth.userId}`;
    limit = config.rateLimitAuthenticated;
  } else {
    // Check for API key header (will be resolved later in auth middleware)
    const apiKey = c.req.header("X-API-Key");
    if (apiKey) {
      key = `ratelimit:apikey:${apiKey.slice(0, 16)}`;
      limit = config.rateLimitApiKey;
    } else {
      // Unauthenticated — rate limit by IP
      const ip =
        c.req.header("X-Forwarded-For")?.split(",")[0]?.trim() ??
        c.req.header("X-Real-IP") ??
        "unknown";
      key = `ratelimit:ip:${ip}`;
      limit = config.rateLimitUnauthenticated;
    }
  }

  const { allowed, remaining } = await checkRateLimit(redis, key, limit);
  c.header("X-RateLimit-Limit", String(limit));
  c.header("X-RateLimit-Remaining", String(remaining));

  if (!allowed) {
    c.header("Retry-After", "60");
    throw new AppError(429, "Too many requests", "RATE_LIMIT_EXCEEDED");
  }

  await next();
});
