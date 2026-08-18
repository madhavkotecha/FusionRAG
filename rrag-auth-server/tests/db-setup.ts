/**
 * Shared DB initialization with top-level await.
 *
 * Because Vitest evaluates `it.skipIf(condition)` at test **collection** time
 * (before `beforeAll` runs), we need the DB to be resolved synchronously at
 * import time. ESM top-level await makes this possible: the DB connection
 * is established when this module is first imported, and every subsequent
 * import reuses the cached result.
 */

import { getTestDb, getTestRedis, createTestApp } from "./helpers.js";
import type { DrizzleDB } from "../src/db/index.js";
import type { RedisClient } from "../src/db/redis.js";
import type { Hono } from "hono";
import type { AppEnv } from "../src/types.js";

let db: DrizzleDB | undefined;
let redis: RedisClient;
let app: Hono<AppEnv>;

try {
  db = await getTestDb();
  redis = getTestRedis();
  app = createTestApp(db, redis);
} catch {
  // DB not available — tests using `it.skipIf(!db)` will be skipped
  redis = getTestRedis();
}

export { db, redis, app };
