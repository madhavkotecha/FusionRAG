/**
 * Zod schemas for user management endpoints.
 */

import { z } from "zod";

export const inviteUserSchema = z.object({
  email: z.string().email(),
  workspaceId: z.string().uuid().optional(),
  role: z.enum(["viewer", "developer", "admin"]).default("developer"),
});

export const updateUserRoleSchema = z.object({
  orgRole: z.enum(["member", "org_admin"]),
});

export const updateUserStatusSchema = z.object({
  status: z.enum(["active", "suspended"]),
});

export type InviteUserInput = z.infer<typeof inviteUserSchema>;
export type UpdateUserRoleInput = z.infer<typeof updateUserRoleSchema>;
export type UpdateUserStatusInput = z.infer<typeof updateUserStatusSchema>;
