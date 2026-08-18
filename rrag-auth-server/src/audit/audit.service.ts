/**
 * Audit log query service.
 */

import { eq, and, gte, lte, desc, sql } from "drizzle-orm";
import type { DrizzleDB } from "../db/index.js";
import * as schema from "../db/schema.js";
import type { AuditLogQuery } from "./audit.schemas.js";

export class AuditService {
  constructor(private db: DrizzleDB) {}

  async queryLogs(orgId: string, query: AuditLogQuery) {
    const conditions = [eq(schema.auditLogs.orgId, orgId)];

    if (query.action) {
      conditions.push(eq(schema.auditLogs.action, query.action));
    }
    if (query.userId) {
      conditions.push(eq(schema.auditLogs.userId, query.userId));
    }
    if (query.resourceType) {
      conditions.push(eq(schema.auditLogs.resourceType, query.resourceType));
    }
    if (query.workspaceId) {
      conditions.push(eq(schema.auditLogs.workspaceId, query.workspaceId));
    }
    if (query.startDate) {
      conditions.push(gte(schema.auditLogs.timestamp, new Date(query.startDate)));
    }
    if (query.endDate) {
      conditions.push(lte(schema.auditLogs.timestamp, new Date(query.endDate)));
    }

    const whereClause = and(...conditions);
    const offset = (query.page - 1) * query.limit;

    const [logs, countResult] = await Promise.all([
      this.db
        .select()
        .from(schema.auditLogs)
        .where(whereClause)
        .orderBy(desc(schema.auditLogs.timestamp))
        .limit(query.limit)
        .offset(offset),
      this.db
        .select({ count: sql<number>`count(*)` })
        .from(schema.auditLogs)
        .where(whereClause),
    ]);

    const total = Number(countResult[0]?.count ?? 0);

    return {
      items: logs.map((log) => ({
        id: log.id,
        userId: log.userId,
        action: log.action,
        resourceType: log.resourceType,
        resourceId: log.resourceId,
        workspaceId: log.workspaceId,
        details: log.details,
        ipAddress: log.ipAddress,
        status: log.status,
        timestamp: log.timestamp.toISOString(),
      })),
      total,
      page: query.page,
      limit: query.limit,
      totalPages: Math.ceil(total / query.limit),
    };
  }
}
