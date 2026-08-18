// ── Admin Types ──────────────────────────────────────────────

export interface Workspace {
  id: string;
  orgId: string;
  name: string;
  slug: string;
  scope: 'personal' | 'team' | 'organization';
  ownerUserId: string | null;
  ownerTeamId: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface Team {
  id: string;
  orgId: string;
  name: string;
  slug: string;
  description: string | null;
  createdBy: string;
  createdAt: string;
  updatedAt: string;
}

export interface TeamMember {
  userId: string;
  name: string;
  email: string;
  role: 'member' | 'lead';
  createdAt: string;
}

export interface AdminUser {
  id: string;
  email: string;
  name: string;
  orgRole: 'member' | 'org_admin';
  status: 'active' | 'suspended';
  lastLoginAt: string | null;
  createdAt: string;
}

export interface UserInvitation {
  id: string;
  email: string;
  role: string;
  expiresAt: string;
  inviteToken: string;
}

export interface WorkspaceMember {
  userId: string;
  name: string;
  email: string;
  role: string;
  createdAt: string;
}

export interface ApiKey {
  id: string;
  name: string;
  key?: string; // Only on create
  keyPrefix: string;
  role: string;
  rateLimitRpm: number;
  status: 'active' | 'revoked';
  lastUsedAt: string | null;
  expiresAt: string | null;
  createdAt: string;
}

export interface AuditLogEntry {
  id: string;
  orgId: string;
  userId: string | null;
  action: string;
  resourceType: string;
  resourceId: string | null;
  workspaceId: string | null;
  details: Record<string, unknown> | null;
  ipAddress: string | null;
  userAgent: string | null;
  status: string;
  timestamp: string;
}

export interface AuditLogResponse {
  logs: AuditLogEntry[];
  total: number;
  page: number;
  pageSize: number;
}

export interface SystemStats {
  totalUsers: number;
  activeUsers: number;
  suspendedUsers: number;
  totalWorkspaces: number;
  totalPipelines: number;
  totalJobs: number;
  jobsByStatus: Record<string, number>;
  totalDocuments: number;
  totalDataStores: number;
  recentActivity: AuditLogEntry[];
}

export interface QueueStats {
  totalJobs: number;
  queued: number;
  running: number;
  completed: number;
  failed: number;
  cancelled?: number;
  avgDurationMs: number | null;
  recentThroughput?: number | null;
  oldestQueuedAge?: number | null;
}

export interface ServiceHealth {
  name: string;
  status: 'healthy' | 'degraded' | 'down';
  url: string;
  responseTimeMs: number | null;
  version: string | null;
  details: Record<string, unknown> | null;
}

export interface HealthCheckResponse {
  overall: 'healthy' | 'degraded' | 'down';
  services: ServiceHealth[];
  checkedAt: string;
}

export interface SystemConfig {
  llm: {
    defaultModel: string;
    hasApiKey: boolean;
  };
  embedding: {
    defaultModel: string;
  };
  queue: {
    name: string;
    jobTimeout: number;
    redisUrl: string;
  };
  storage: {
    storageDir: string;
    configsDir: string;
    maxUploadSizeMb: number;
  };
}

export interface QueueActionResult {
  action: string;
  affected: number;
  message: string;
}

export interface QueueTimelineEntry {
  hour: string;
  completed: number;
  failed: number;
  created: number;
}
