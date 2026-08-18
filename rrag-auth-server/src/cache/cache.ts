/**
 * Redis cache-aside layer for auth server.
 *
 * All DB reads go through cache first. Mutations invalidate relevant keys.
 * Cache keys: rrag:auth:{entity}:{scope}:{id}
 */

import type { RedisClient } from "../db/redis.js";

// TTL defaults (seconds)
export const TTL_SHORT = 60;      // Frequently changing data
export const TTL_MEDIUM = 180;    // Lists
export const TTL_LONG = 300;      // Individual entities
export const TTL_STATIC = 1800;   // Near-static data

const PREFIX = "rrag:auth";

function buildKey(entity: string, scope: string, suffix = ""): string {
  return suffix ? `${PREFIX}:${entity}:${scope}:${suffix}` : `${PREFIX}:${entity}:${scope}`;
}

export async function cacheGet<T>(redis: RedisClient, entity: string, scope: string, suffix = ""): Promise<T | null> {
  try {
    const raw = await redis.get(buildKey(entity, scope, suffix));
    if (raw !== null) {
      return JSON.parse(raw) as T;
    }
  } catch {
    // Cache miss or error — fall through to DB
  }
  return null;
}

export async function cacheSet(
  redis: RedisClient,
  entity: string,
  scope: string,
  value: unknown,
  suffix = "",
  ttl = TTL_LONG,
): Promise<void> {
  try {
    await redis.set(buildKey(entity, scope, suffix), JSON.stringify(value), "EX", ttl);
  } catch {
    // Non-fatal — cache write failures don't block the request
  }
}

export async function cacheDelete(redis: RedisClient, entity: string, scope: string, suffix = ""): Promise<void> {
  try {
    await redis.del(buildKey(entity, scope, suffix));
  } catch {
    // Non-fatal
  }
}

export async function cacheInvalidateEntity(
  redis: RedisClient,
  entity: string,
  scope: string,
  entityId = "",
): Promise<void> {
  try {
    const promises: Promise<number>[] = [];
    if (entityId) {
      promises.push(redis.del(buildKey(entity, scope, entityId)));
    }
    // Always invalidate list cache
    promises.push(redis.del(buildKey(entity, scope, "list")));
    await Promise.all(promises);
  } catch {
    // Non-fatal
  }
}
