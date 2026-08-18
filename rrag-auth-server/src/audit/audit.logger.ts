/**
 * Audit logging helper.
 */

import type { DrizzleDB } from "../db/index.js";
import { auditLogs } from "../db/schema.js";

export interface AuditEvent {
  orgId: string;
  userId?: string;
  action: string;
  resourceType: string;
  resourceId?: string;
  workspaceId?: string;
  details?: Record<string, unknown>;
  ipAddress?: string;
  userAgent?: string;
  requestId?: string;
  status: "success" | "denied" | "error";
}

/**
 * Log an audit event to the database. Fire-and-forget style.
 */
export async function logAuditEvent(
  db: DrizzleDB,
  event: AuditEvent,
): Promise<void> {
  try {
    await db.insert(auditLogs).values({
      orgId: event.orgId,
      userId: event.userId,
      action: event.action,
      resourceType: event.resourceType,
      resourceId: event.resourceId,
      workspaceId: event.workspaceId,
      details: event.details ?? null,
      ipAddress: event.ipAddress,
      userAgent: event.userAgent,
      requestId: event.requestId,
      status: event.status,
    });
  } catch (err) {
    // Audit logging should never break the request
    console.error("Failed to write audit log:", err);
  }
}
