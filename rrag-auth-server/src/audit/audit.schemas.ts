/**
 * Zod schemas for audit log endpoints.
 */

import { z } from "zod";

export const auditLogQuerySchema = z.object({
  action: z.string().optional(),
  userId: z.string().uuid().optional(),
  resourceType: z.string().optional(),
  workspaceId: z.string().uuid().optional(),
  startDate: z.string().datetime().optional(),
  endDate: z.string().datetime().optional(),
  page: z.coerce.number().int().min(1).default(1),
  limit: z.coerce.number().int().min(1).max(100).default(50),
});

export type AuditLogQuery = z.infer<typeof auditLogQuerySchema>;
