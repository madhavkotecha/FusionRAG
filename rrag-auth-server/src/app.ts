/**
 * Hono app factory. Exported for testing.
 */

import { Hono } from "hono";
import { cors } from "hono/cors";
import type { AppEnv } from "./types.js";
import type { DrizzleDB } from "./db/index.js";
import type { RedisClient } from "./db/redis.js";

// Middleware
import { requestIdMiddleware } from "./middleware/request-id.js";
import { timingMiddleware } from "./middleware/timing.js";
import { rateLimiterMiddleware } from "./middleware/rate-limiter.js";
import { authMiddleware } from "./middleware/auth.js";
import { errorHandler } from "./middleware/error-handler.js";

// Routes
import { authRoutes } from "./auth/auth.routes.js";
import { usersRoutes } from "./users/users.routes.js";
import { workspacesRoutes } from "./workspaces/workspaces.routes.js";
import { apiKeysRoutes } from "./api-keys/api-keys.routes.js";
import { oidcRoutes } from "./oidc/oidc.routes.js";
import { teamsRoutes } from "./teams/teams.routes.js";
import { auditRoutes } from "./audit/audit.routes.js";

export function createApp(db: DrizzleDB, redis: RedisClient): Hono<AppEnv> {
  const app = new Hono<AppEnv>();

  // Global error handler
  app.onError(errorHandler);

  // Inject DB and Redis into context
  app.use("*", async (c, next) => {
    c.set("db", db);
    c.set("redis", redis);
    await next();
  });

  // CORS — restrict to explicit origins; empty CORS_ORIGINS blocks all cross-origin
  const corsOrigins = process.env.CORS_ORIGINS
    ? process.env.CORS_ORIGINS.split(",").map((o) => o.trim())
    : [];
  app.use(
    "*",
    cors({
      origin: corsOrigins,
      credentials: true,
      allowMethods: ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
      allowHeaders: ["Content-Type", "Authorization", "X-API-Key", "X-Request-ID"],
      exposeHeaders: ["X-Request-ID", "X-Process-Time", "X-RateLimit-Limit", "X-RateLimit-Remaining"],
    }),
  );

  // Middleware stack
  app.use("*", requestIdMiddleware);
  app.use("*", timingMiddleware);
  app.use("*", rateLimiterMiddleware);
  app.use("*", authMiddleware);

  // Health check
  app.get("/health", (c) => c.json({ status: "ok" }));

  // Mount routes
  app.route("/auth", authRoutes);
  app.route("/users", usersRoutes);
  app.route("/workspaces", workspacesRoutes);
  app.route("/workspaces", apiKeysRoutes);
  app.route("/teams", teamsRoutes);
  app.route("/auth/oidc", oidcRoutes);
  app.route("/audit-logs", auditRoutes);

  return app;
}
