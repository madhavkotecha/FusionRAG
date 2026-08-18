/**
 * Adds X-Process-Time header showing request duration.
 */

import { createMiddleware } from "hono/factory";
import type { AppEnv } from "../types.js";

export const timingMiddleware = createMiddleware<AppEnv>(async (c, next) => {
  const start = performance.now();
  await next();
  const durationMs = performance.now() - start;
  c.header("X-Process-Time", `${durationMs.toFixed(1)}ms`);
});
