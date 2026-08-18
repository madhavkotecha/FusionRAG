import client from './client';

export interface AdminComponent {
  id: string;
  type: string;
  category: string;
  name: string;
  description: string;
  config_schema: Record<string, unknown>;
  input_ports: Array<{ name: string; type: string }>;
  output_ports: Array<{ name: string; type: string }>;
  source: 'seed' | 'custom';
  is_composite: boolean;
  steps: Record<string, unknown> | null;
  workspace_id: string | null;
  current_version: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface ComponentCode {
  type: string;
  workspace_id: string | null;
  code: string;
  current_version: number;
  can_edit: boolean;
}

export interface ComponentVersion {
  id: string;
  component_type: string;
  workspace_id: string;
  version: number;
  file_hash: string;
  changed_by: string;
  change_reason: string | null;
  created_at: string;
}

export interface VersionDetail extends ComponentVersion {
  code: string;
}

export interface VersionListResponse {
  items: ComponentVersion[];
  total: number;
  page: number;
  page_size: number;
}

export const adminComponentsApi = {
  list: (params?: { source?: string; category?: string; search?: string }) =>
    client.get<AdminComponent[]>('/api/v1/admin/components', { params }),

  getCode: (type: string, workspaceId?: string) =>
    client.get<ComponentCode>(`/api/v1/admin/components/${type}/code`, {
      params: { workspace_id: workspaceId || '_global' },
    }),

  updateCode: (type: string, code: string, changeReason?: string, workspaceId?: string) =>
    client.put(`/api/v1/admin/components/${type}/code`, {
      code,
      change_reason: changeReason || null,
    }, {
      params: { workspace_id: workspaceId || '_global' },
    }),

  listVersions: (type: string, workspaceId?: string, page = 1, pageSize = 20) =>
    client.get<VersionListResponse>(`/api/v1/admin/components/${type}/versions`, {
      params: { workspace_id: workspaceId || '_global', page, page_size: pageSize },
    }),

  getVersion: (type: string, version: number, workspaceId?: string) =>
    client.get<VersionDetail>(`/api/v1/admin/components/${type}/versions/${version}`, {
      params: { workspace_id: workspaceId || '_global' },
    }),

  revert: (type: string, version: number, workspaceId?: string) =>
    client.post(`/api/v1/admin/components/${type}/revert`, {
      version,
    }, {
      params: { workspace_id: workspaceId || '_global' },
    }),
};
