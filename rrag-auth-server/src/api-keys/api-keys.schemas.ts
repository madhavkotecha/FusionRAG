/**
 * Zod schemas for API key endpoints.
 */

import { z } from "zod";

export const createApiKeySchema = z.object({
  name: z.string().min(1).max(255),
  role: z.enum(["viewer", "developer", "admin"]).default("developer"),
  expiresInDays: z.number().int().min(1).max(365).optional(),
});

export type CreateApiKeyInput = z.infer<typeof createApiKeySchema>;
