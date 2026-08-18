import client from './client';
import type {
  AdminUser,
  UserInvitation,
  Workspace,
  WorkspaceMember,
  ApiKey,
  AuditLogResponse,
  SystemStats,
  QueueStats,
} from '../types/admin';
import type { IngestionJob } from './ingestion';

// ── User Management (org_admin only) ────────────────────────

export const adminUsersApi = {
  list: () => client.get<AdminUser[]>('/users'),

  invite: (data: { email: string; role?: string; workspaceId?: string }) =>
    client.post<UserInvitation>('/users/invite', data),

  updateRole: (userId: string, orgRole: string) =>
    client.put<AdminUser>(`/users/${userId}/role`, { orgRole }),

  updateStatus: (userId: string, status: 'active' | 'suspended') =>
    client.put<AdminUser>(`/users/${userId}/status`, { status }),
};

// ── Workspace Management ────────────────────────────────────

export const adminWorkspacesApi = {
  list: () => client.get<Workspace[]>('/workspaces'),

  create: (data: { name: string; slug: string; scope: string; teamId?: string }) =>
    client.post<Workspace>('/workspaces', data),

  delete: (wsId: string) => client.delete(`/workspaces/${wsId}`),

  listMembers: (wsId: string) =>
    client.get<WorkspaceMember[]>(`/workspaces/${wsId}/members`),

  addMember: (wsId: string, userId: string, role: string) =>
    client.post(`/workspaces/${wsId}/members`, { userId, role }),

  updateMemberRole: (wsId: string, userId: string, role: string) =>
    client.put(`/workspaces/${wsId}/members/${userId}`, { role }),

  removeMember: (wsId: string, userId: string) =>
    client.delete(`/workspaces/${wsId}/members/${userId}`),
};

// ── API Key Management ──────────────────────────────────────

export const adminApiKeysApi = {
  list: (wsId: string) =>
    client.get<ApiKey[]>(`/workspaces/${wsId}/api-keys`),

  create: (wsId: string, data: { name: string; role?: string; expiresInDays?: number }) =>
    client.post<ApiKey>(`/workspaces/${wsId}/api-keys`, data),

  revoke: (wsId: string, keyId: string) =>
    client.delete(`/workspaces/${wsId}/api-keys/${keyId}`),
};

// ── Audit Logs ──────────────────────────────────────────────

export const adminAuditApi = {
  query: (params?: {
    action?: string;
    userId?: string;
    resourceType?: string;
    from?: string;
    to?: string;
    page?: number;
    pageSize?: number;
  }) => client.get<AuditLogResponse>('/audit-logs', { params }),
};

// ── System Stats (aggregated from multiple services) ────────

export const adminStatsApi = {
  getOverview: async (): Promise<SystemStats> => {
    const [usersRes, jobsRes, docsRes, datastoresRes, pipelinesRes, auditRes] =
      await Promise.allSettled([
        client.get<AdminUser[]>('/users'),
        client.get<{ jobs: IngestionJob[] }>('/api/v1/ingestion/jobs'),
        client.get<{ documents: unknown[] }>('/api/v1/ingestion/documents'),
        client.get<{ datastores: unknown[] }>('/api/v1/ingestion/datastores'),
        client.get<unknown[]>('/api/v1/pipelines', { params: { workspace_id: 'all' } }),
        client.get<AuditLogResponse>('/audit-logs', { params: { pageSize: 10 } }),
      ]);

    const users =
      usersRes.status === 'fulfilled' ? usersRes.value.data : [];
    const jobs =
      jobsRes.status === 'fulfilled'
        ? (jobsRes.value.data as { jobs: IngestionJob[] }).jobs ?? []
        : [];
    const docs =
      docsRes.status === 'fulfilled'
        ? (docsRes.value.data as { documents: unknown[] }).documents ?? []
        : [];
    const datastores =
      datastoresRes.status === 'fulfilled'
        ? (datastoresRes.value.data as { datastores: unknown[] }).datastores ?? []
        : [];
    const pipelines =
      pipelinesRes.status === 'fulfilled'
        ? Array.isArray(pipelinesRes.value.data) ? pipelinesRes.value.data : []
        : [];
    const audit =
      auditRes.status === 'fulfilled'
        ? (auditRes.value.data as AuditLogResponse)
        : { logs: [], total: 0, page: 1, pageSize: 10 };

    const jobsByStatus: Record<string, number> = {};
    for (const j of jobs) {
      jobsByStatus[j.status] = (jobsByStatus[j.status] || 0) + 1;
    }

    return {
      totalUsers: users.length,
      activeUsers: users.filter((u: AdminUser) => u.status === 'active').length,
      suspendedUsers: users.filter((u: AdminUser) => u.status === 'suspended').length,
      totalWorkspaces: 0, // Will be populated if workspace list endpoint is available
      totalPipelines: pipelines.length,
      totalJobs: jobs.length,
      jobsByStatus,
      totalDocuments: docs.length,
      totalDataStores: datastores.length,
      recentActivity: audit.logs ?? [],
    };
  },

  getQueueStats: async (): Promise<QueueStats> => {
    try {
      const { data } = await client.get<QueueStats>('/api/v1/ingestion/admin/queue/stats');
      return data;
    } catch {
      // Fallback: compute from job list
      try {
        const { data } = await client.get<{ jobs: IngestionJob[] }>('/api/v1/ingestion/jobs');
        const jobs = data.jobs ?? [];
        const durations = jobs
          .filter((j) => j.total_duration_ms != null)
          .map((j) => j.total_duration_ms!);

        return {
          totalJobs: jobs.length,
          queued: jobs.filter((j) => j.status === 'queued').length,
          running: jobs.filter((j) => j.status === 'running').length,
          completed: jobs.filter((j) => j.status === 'completed').length,
          failed: jobs.filter((j) => j.status === 'failed').length,
          avgDurationMs:
            durations.length > 0
              ? Math.round(durations.reduce((a, b) => a + b, 0) / durations.length)
              : null,
        };
      } catch {
        return { totalJobs: 0, queued: 0, running: 0, completed: 0, failed: 0, avgDurationMs: null };
      }
    }
  },
};

// ── Queue Actions ────────────────────────────────────────────

export const adminQueueApi = {
  getStats: () =>
    client.get<QueueStats>('/api/v1/ingestion/admin/queue/stats'),

  getTimeline: (hours = 24) =>
    client.get<{ timeline: Array<{ hour: string; completed: number; failed: number; created: number }>; hours: number }>(
      '/api/v1/ingestion/admin/queue/timeline',
      { params: { hours } },
    ),

  performAction: (action: string) =>
    client.post<{ action: string; affected: number; message: string }>(
      '/api/v1/ingestion/admin/queue/actions',
      { action },
    ),
};

// ── Service Health ────────────────────────────────────────────

export const adminHealthApi = {
  check: () =>
    client.get<{
      overall: string;
      services: Array<{
        name: string;
        status: string;
        url: string;
        responseTimeMs: number | null;
        version: string | null;
        details: Record<string, unknown> | null;
      }>;
      checkedAt: string;
    }>('/api/v1/ingestion/admin/health'),
};

// ── System Configuration ──────────────────────────────────────

export const adminConfigApi = {
  get: () =>
    client.get<{
      llm: {
        defaultModel: string;
        hasApiKey: boolean;
        provider: 'openai' | 'ollama' | 'vllm';
        openaiBaseUrl: string;
        ollamaBaseUrl: string;
        apiKeyDisplay: string;
        vllmBaseUrl: string;
        vllmApiKeyDisplay: string;
      };
      embedding: { defaultModel: string };
      queue: { name: string; jobTimeout: number; redisUrl: string };
      storage: { storageDir: string; configsDir: string; maxUploadSizeMb: number };
    }>('/api/v1/ingestion/admin/config'),

  update: (data: {
    defaultLlmModel?: string;
    defaultEmbeddingModel?: string;
    rqJobTimeout?: number;
    maxUploadSizeMb?: number;
    llmProvider?: string;
    openaiApiKey?: string;
    openaiBaseUrl?: string;
    ollamaBaseUrl?: string;
    vllmBaseUrl?: string;
    vllmApiKey?: string;
  }) => client.put('/api/v1/ingestion/admin/config', data),
};
