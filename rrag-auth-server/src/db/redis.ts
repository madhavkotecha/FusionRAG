/**
 * ioredis client singleton.
 */

import { Redis } from "ioredis";

export type RedisClient = Redis;

let _redis: RedisClient | null = null;

export function getRedis(redisUrl?: string): RedisClient {
  if (_redis) return _redis;

  const url = redisUrl ?? process.env.REDIS_URL;
  if (!url) throw new Error("REDIS_URL is not set. Check your .env file.");
  _redis = new Redis(url, { maxRetriesPerRequest: 3 });
  return _redis;
}

/** Override the Redis instance (used in tests with ioredis-mock). */
export function setRedis(redis: RedisClient): void {
  _redis = redis;
}

/** Close the Redis connection. */
export async function closeRedis(): Promise<void> {
  if (_redis) {
    await _redis.quit();
    _redis = null;
  }
}
