/**
 * Adds X-Request-ID header to every request/response.
 */

import { createMiddleware } from "hono/factory";
import { v4 as uuidv4 } from "uuid";
import type { AppEnv } from "../types.js";

export const requestIdMiddleware = createMiddleware<AppEnv>(async (c, next) => {
  const requestId = c.req.header("X-Request-ID") ?? uuidv4();
  c.set("requestId", requestId);
  await next();
  c.header("X-Request-ID", requestId);
});
