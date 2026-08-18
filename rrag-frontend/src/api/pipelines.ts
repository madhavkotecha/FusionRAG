import client from './client';
import type { Pipeline, PipelineRun, PipelineVersion, PipelineType, ComponentDefinition } from '../types/pipeline';
import { useAuthStore } from '../stores/auth.store';

export interface PipelineTemplate {
  id: string;
  name: string;
  description: string;
  category: 'ingestion' | 'query' | 'full';
  definition: {
    nodes: Array<Record<string, unknown>>;
    edges: Array<Record<string, unknown>>;
  };
}

function getWorkspaceId(): string {
  const user = useAuthStore.getState().user;
  return user?.workspaces?.[0]?.workspaceId ?? 'default';
}

export const pipelineApi = {
  list: (workspaceId: string, pipelineType?: PipelineType) =>
    client.get<Pipeline[]>('/api/v1/pipelines', {
      params: {
        workspace_id: workspaceId,
        ...(pipelineType ? { pipeline_type: pipelineType } : {}),
      },
    }),
  get: (id: string, workspaceId?: string) =>
    client.get<Pipeline>(`/api/v1/pipelines/${id}`, {
      params: { workspace_id: workspaceId ?? getWorkspaceId() },
    }),
  create: (data: {
    name: string;
    description?: string;
    workspace_id: string;
    definition?: Record<string, unknown>;
    pipeline_type?: PipelineType;
    datastore_id?: string;
  }) =>
    client.post<Pipeline>('/api/v1/pipelines', data),
  update: (id: string, data: Partial<Pipeline>, workspaceId?: string) =>
    client.put<Pipeline>(`/api/v1/pipelines/${id}`, data, {
      params: { workspace_id: workspaceId ?? getWorkspaceId() },
    }),
  delete: (id: string, workspaceId?: string) =>
    client.delete(`/api/v1/pipelines/${id}`, {
      params: { workspace_id: workspaceId ?? getWorkspaceId() },
    }),

  createVersion: (id: string, message?: string, workspaceId?: string) =>
    client.post<PipelineVersion>(`/api/v1/pipelines/${id}/versions`, { change_message: message }, {
      params: { workspace_id: workspaceId ?? getWorkspaceId() },
    }),
  listVersions: (id: string, workspaceId?: string) =>
    client.get<PipelineVersion[]>(`/api/v1/pipelines/${id}/versions`, {
      params: { workspace_id: workspaceId ?? getWorkspaceId() },
    }),

  run: (id: string, params?: Record<string, unknown>, workspaceId?: string) =>
    client.post<PipelineRun>(`/api/v1/pipelines/${id}/run`, { input_params: params }, {
      params: { workspace_id: workspaceId ?? getWorkspaceId() },
    }),
  getRun: (runId: string) => client.get<PipelineRun>(`/api/v1/runs/${runId}`),
  listRuns: (id: string, workspaceId?: string) =>
    client.get<PipelineRun[]>(`/api/v1/pipelines/${id}/runs`, {
      params: { workspace_id: workspaceId ?? getWorkspaceId() },
    }),

  getComponents: () => client.get<ComponentDefinition[]>('/api/v1/components'),
  getTemplates: () => client.get<PipelineTemplate[]>('/api/v1/templates'),
};
