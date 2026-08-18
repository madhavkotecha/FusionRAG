/**
 * Server entry point.
 */

import { serve } from "@hono/node-server";
import { config } from "./config.js";
import { getDb } from "./db/index.js";
import { getRedis } from "./db/redis.js";
import { createApp } from "./app.js";

const db = getDb(config.databaseUrl);
const redis = getRedis(config.redisUrl);
const app = createApp(db, redis);

console.log(`Starting rrag-auth-server on port ${config.port} (${config.environment})`);

serve({
  fetch: app.fetch,
  port: config.port,
});
