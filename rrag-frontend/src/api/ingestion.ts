import client from './client';

export interface IngestionDocument {
  id: string;
  filename: string;
  content_type: string;
  file_path: string;
  metadata: Record<string, unknown>;
}

export interface IngestionComponent {
  name: string;
  type: string;
  version: string;
  description: string;
  config_schema: Record<string, unknown>;
}

export interface IngestionPipeline {
  name: string;
  description: string;
  steps: number;
}

export interface IngestionPipelineDetail {
  name: string;
  description: string;
  steps: { component: string; config: Record<string, unknown>; condition?: string | null }[];
}

export interface StepResult {
  step_index: number;
  component: string;
  status: 'ok' | 'error';
  duration_ms: number;
  error: string | null;
  output_summary: Record<string, unknown>;
}

export interface SubProgress {
  message: string;
  items_done: number;
  items_total: number;
}

export interface IngestionJob {
  id: string;
  pipeline_name: string;
  document_ids: string[];
  status: string;
  progress: number;
  current_step: string | null;
  total_steps: number;
  sub_progress: SubProgress | null;
  errors: string[];
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  step_results: StepResult[];
  total_duration_ms: number | null;
  datastore_id: string | null;
  pipeline_steps: string[];
}

export interface DataStoreTarget {
  type: 'vector' | 'graph' | 'metadata';
  backend: string;
  config: Record<string, unknown>;
  stats: Record<string, unknown>;
}

export interface DataStore {
  id: string;
  name: string;
  description: string;
  pipeline_name: string;
  source_document_ids: string[];
  created_by_job_id: string;
  status: 'empty' | 'building' | 'ready' | 'completed' | 'failed';
  targets: DataStoreTarget[];
  created_at: string;
  updated_at: string | null;
}

const BASE = '/api/v1/ingestion';

export function streamJobs(
  onData: (jobs: IngestionJob[]) => void,
  onError?: (err: Error) => void,
): () => void {
  const controller = new AbortController();

  (async () => {
    try {
      const { useAuthStore } = await import('../stores/auth.store');
      const { useWorkspaceStore } = await import('../stores/workspace.store');
      const token = useAuthStore.getState().accessToken;
      const wsId = useWorkspaceStore.getState().activeWorkspaceId;
      const baseURL = import.meta.env.VITE_API_URL || '';
      const params = wsId ? `?workspace_id=${encodeURIComponent(wsId)}` : '';
      const res = await fetch(`${baseURL}${BASE}/jobs/stream${params}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        signal: controller.signal,
      });
      if (!res.ok || !res.body) {
        onError?.(new Error(`SSE connect failed: ${res.status}`));
        return;
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const evt = JSON.parse(line.slice(6));
            if (evt.type === 'jobs') onData(evt.jobs);
          } catch { /* skip malformed */ }
        }
      }
    } catch (err) {
      if ((err as DOMException)?.name !== 'AbortError') {
        onError?.(err instanceof Error ? err : new Error(String(err)));
      }
    }
  })();

  return () => controller.abort();
}

export function streamJob(
  jobId: string,
  onData: (job: IngestionJob) => void,
  onDone?: () => void,
  onError?: (err: Error) => void,
): () => void {
  const controller = new AbortController();

  (async () => {
    try {
      const { useAuthStore } = await import('../stores/auth.store');
      const { useWorkspaceStore } = await import('../stores/workspace.store');
      const token = useAuthStore.getState().accessToken;
      const wsId = useWorkspaceStore.getState().activeWorkspaceId;
      const baseURL = import.meta.env.VITE_API_URL || '';
      const params = wsId ? `?workspace_id=${encodeURIComponent(wsId)}` : '';
      const res = await fetch(`${baseURL}${BASE}/jobs/${jobId}/stream${params}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        signal: controller.signal,
      });
      if (!res.ok || !res.body) {
        onError?.(new Error(`SSE connect failed: ${res.status}`));
        return;
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const evt = JSON.parse(line.slice(6));
            if (evt.type === 'job') onData(evt.job);
            if (evt.type === 'done') onDone?.();
          } catch { /* skip malformed */ }
        }
      }
      onDone?.();
    } catch (err) {
      if ((err as DOMException)?.name !== 'AbortError') {
        onError?.(err instanceof Error ? err : new Error(String(err)));
      }
    }
  })();

  return () => controller.abort();
}

export const ingestionApi = {
  // Documents
  uploadDocuments: (files: File[]) => {
    const form = new FormData();
    files.forEach((f) => form.append('files', f));
    return client.post<{ uploaded: { id: string; filename: string }[] }>(`${BASE}/documents/upload`, form);
  },
  listDocuments: () => client.get<{ documents: IngestionDocument[] }>(`${BASE}/documents`),
  getDocument: (id: string) => client.get<IngestionDocument>(`${BASE}/documents/${id}`),
  deleteDocument: (id: string) => client.delete(`${BASE}/documents/${id}`),
  getDocumentDownloadUrl: (id: string) =>
    client.get<{ download_url: string; filename: string }>(`${BASE}/documents/${id}/download-url`),

  // Components
  listComponents: () => client.get<{ components: IngestionComponent[] }>(`${BASE}/components`),
  getComponentsByType: (type: string) => client.get<{ components: IngestionComponent[] }>(`${BASE}/components/types/${type}`),
  getComponent: (name: string) => client.get<IngestionComponent>(`${BASE}/components/${name}`),

  // Pipelines
  listPipelines: () => client.get<{ pipelines: IngestionPipeline[] }>(`${BASE}/pipelines`),
  getPipeline: (name: string) => client.get<IngestionPipelineDetail>(`${BASE}/pipelines/${name}`),
  createPipeline: (data: { name: string; description?: string; steps: { component: string; config?: Record<string, unknown> }[] }) =>
    client.post(`${BASE}/pipelines`, data),
  updatePipeline: (name: string, data: { name: string; description?: string; steps: { component: string; config?: Record<string, unknown> }[] }) =>
    client.put(`${BASE}/pipelines/${name}`, data),
  deletePipeline: (name: string) => client.delete(`${BASE}/pipelines/${name}`),
  validatePipeline: (name: string) => client.post<{ valid: boolean; errors: string[] }>(`${BASE}/pipelines/${name}/validate`),

  // Jobs
  createJob: (data: { pipeline_name: string; document_ids: string[]; config_overrides?: Record<string, unknown>; datastore_id?: string | null }) =>
    client.post<{ job_id: string; status: string }>(`${BASE}/jobs`, data),
  listJobs: (status?: string) => client.get<{ jobs: IngestionJob[] }>(`${BASE}/jobs`, { params: status ? { status } : {} }),
  getJob: (id: string) => client.get<IngestionJob>(`${BASE}/jobs/${id}`),
  cancelJob: (id: string) => client.delete(`${BASE}/jobs/${id}`),
  resumeJob: (id: string) => client.post(`${BASE}/jobs/${id}/resume`),

  // DataStores
  createDataStore: (data: { name: string; description?: string }) =>
    client.post<DataStore>(`${BASE}/datastores`, data),
  listDataStores: () => client.get<{ datastores: DataStore[] }>(`${BASE}/datastores`),
  getDataStore: (id: string) => client.get<DataStore>(`${BASE}/datastores/${id}`),
  getDataStoreStrategies: (id: string) =>
    client.get<{ strategies: { id: string; label: string; backend?: string; description?: string; available: boolean }[] }>(
      `${BASE}/datastores/${id}/strategies`,
    ),
  deleteDataStore: (id: string) => client.delete(`${BASE}/datastores/${id}`),
};
