/**
 * Application configuration with Zod validation.
 */

import path from "path";
import { fileURLToPath } from "url";
import { z } from "zod";
import dotenv from "dotenv";

// Load root .env (project root is two levels up from src/)
const __dirname = path.dirname(fileURLToPath(import.meta.url));
dotenv.config({ path: path.resolve(__dirname, "../../.env") });

const configSchema = z.object({
  // Server
  port: z.coerce.number().default(3000),
  environment: z.enum(["development", "production", "test"]).default("development"),

  // Database
  databaseUrl: z.string().min(1),

  // Redis
  redisUrl: z.string().min(1),

  // Rate Limiting (requests per minute)
  rateLimitUnauthenticated: z.coerce.number().default(20),
  rateLimitAuthenticated: z.coerce.number().default(300),
  rateLimitApiKey: z.coerce.number().default(600),

  // Password Policy (kept for invitation acceptance validation)
  passwordMinLength: z.coerce.number().default(12),

  // Invitations
  invitationExpireHours: z.coerce.number().default(72),

  // Keycloak OIDC (required — Keycloak is the sole identity provider)
  kcRealmUrl: z.string().min(1),
  kcPublicRealmUrl: z.string().optional(),
  kcClientId: z.string().min(1),
  kcClientSecret: z.string().min(1),
});

export type Config = z.infer<typeof configSchema>;

function loadConfig(): Config {
  const raw = {
    port: process.env.PORT,
    environment: process.env.ENVIRONMENT,
    databaseUrl: process.env.DATABASE_URL,
    redisUrl: process.env.REDIS_URL,
    rateLimitUnauthenticated: process.env.RATE_LIMIT_UNAUTHENTICATED,
    rateLimitAuthenticated: process.env.RATE_LIMIT_AUTHENTICATED,
    rateLimitApiKey: process.env.RATE_LIMIT_API_KEY,
    passwordMinLength: process.env.PASSWORD_MIN_LENGTH,
    invitationExpireHours: process.env.INVITATION_EXPIRE_HOURS,
    kcRealmUrl: process.env.KC_REALM_URL,
    kcPublicRealmUrl: process.env.KC_PUBLIC_REALM_URL,
    kcClientId: process.env.KC_CLIENT_ID,
    kcClientSecret: process.env.KC_CLIENT_SECRET,
  };

  return configSchema.parse(raw);
}

export const config = loadConfig();
