/**
 * Zod schemas for workspace endpoints.
 */

import { z } from "zod";

export const createWorkspaceSchema = z.object({
  name: z.string().min(1).max(255),
  slug: z.string().min(1).max(255).regex(/^[a-z0-9-]+$/),
  scope: z.enum(["personal", "team", "organization"]).default("organization"),
  teamId: z.string().uuid().optional(),
});

export const updateWorkspaceSchema = z.object({
  name: z.string().min(1).max(255).optional(),
});

export const addMemberSchema = z.object({
  userId: z.string().uuid(),
  role: z.enum(["viewer", "developer", "admin"]).default("developer"),
});

export const updateMemberRoleSchema = z.object({
  role: z.enum(["viewer", "developer", "admin"]),
});

export type CreateWorkspaceInput = z.infer<typeof createWorkspaceSchema>;
export type UpdateWorkspaceInput = z.infer<typeof updateWorkspaceSchema>;
export type AddMemberInput = z.infer<typeof addMemberSchema>;
export type UpdateMemberRoleInput = z.infer<typeof updateMemberRoleSchema>;
