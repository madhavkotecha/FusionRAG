/**
 * Shared TypeScript types for the auth server.
 */

import type { DrizzleDB } from "./db/index.js";
import type { RedisClient } from "./db/redis.js";

/** Authentication context injected by auth middleware. */
export interface AuthContext {
  userId: string;
  orgId: string;
  orgRole: string; // "org_admin" | "member"
  email: string;
  name: string;
  workspaceMemberships: Record<string, string>; // { wsId: role }
  isPlatformAdmin: boolean;
}

/** Hono app environment bindings. */
export type AppEnv = {
  Variables: {
    requestId: string;
    auth: AuthContext | undefined;
    db: DrizzleDB;
    redis: RedisClient;
  };
};
