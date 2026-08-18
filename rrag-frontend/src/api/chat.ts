import client from './client';

export interface ChatRequest {
  message: string;
  query_pipeline_ids: string[];
  model?: string;
  temperature?: number;
  max_tokens?: number;
  conversation_id?: string | null;
}

export interface ChatSource {
  id: string;
  content: string;
  score: number;
  metadata: Record<string, unknown>;
}

export interface ChatTraceStep {
  step: string;
  status: string;
  duration_ms: number;
  input_summary: Record<string, unknown>;
  output_summary: Record<string, unknown>;
  error: string | null;
}

export interface ChatTrace {
  id: string;
  pipeline_id: string;
  pipeline_name: string;
  query: string;
  datastore_id: string;
  datastore_name: string;
  steps: ChatTraceStep[];
  total_duration_ms: number;
}

export interface ChatResponse {
  id: string;
  conversation_id: string;
  message: string;
  answer: string;
  sources: ChatSource[];
  traces: ChatTrace[];
  model: string;
  tokens_used: number;
  duration_ms: number;
}

export interface QueryPipeline {
  id: string;
  name: string;
  description: string;
  datastore_id: string;
  retrieval_strategy: string;
  retriever: {
    strategy?: string;
    top_k: number;
    score_threshold: number;
    alpha?: number;
    fusion_method?: string;
    use_mmr?: boolean;
    [key: string]: unknown;
  };
  reranker: {
    enabled: boolean;
    strategy?: string;
    model: string;
    top_k: number;
    score_threshold?: number;
    [key: string]: unknown;
  };
  generator: {
    model: string;
    temperature: number;
    max_tokens: number;
    system_prompt: string;
    citation_mode?: string;
    context_ordering?: string;
    enable_cot?: boolean;
    [key: string]: unknown;
  };
  planner?: {
    enabled: boolean;
    strategy?: string;
    [key: string]: unknown;
  };
  agent?: {
    enabled: boolean;
    agent_type?: string;
    [key: string]: unknown;
  };
  definition?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string | null;
}

export interface CreateQueryPipelineRequest {
  name: string;
  description?: string;
  datastore_id: string;
  retrieval_strategy?: string;
  retriever?: Partial<QueryPipeline['retriever']>;
  reranker?: Partial<QueryPipeline['reranker']>;
  generator?: Partial<QueryPipeline['generator']>;
  planner?: Partial<NonNullable<QueryPipeline['planner']>>;
  agent?: Partial<NonNullable<QueryPipeline['agent']>>;
  definition?: Record<string, unknown> | null;
}

const CHAT_BASE = '/api/v1/ingestion/chat';
const QP_BASE = '/api/v1/ingestion/query-pipelines';

export const chatApi = {
  chat: (data: ChatRequest) => client.post<ChatResponse>(CHAT_BASE, data),

  getConversation: (id: string) =>
    client.get<{ conversation_id: string; messages: { role: string; content: string }[] }>(
      `${CHAT_BASE}/conversations/${id}`,
    ),

  deleteConversation: (id: string) => client.delete(`${CHAT_BASE}/conversations/${id}`),
};

export const queryPipelineApi = {
  create: (data: CreateQueryPipelineRequest) => client.post<QueryPipeline>(QP_BASE, data),

  list: () => client.get<{ query_pipelines: QueryPipeline[] }>(QP_BASE),

  get: (id: string) => client.get<QueryPipeline>(`${QP_BASE}/${id}`),

  getToolSchema: (id: string) => client.get(`${QP_BASE}/${id}/tool-schema`),

  update: (id: string, data: Partial<CreateQueryPipelineRequest>) =>
    client.put<QueryPipeline>(`${QP_BASE}/${id}`, data),

  delete: (id: string) => client.delete(`${QP_BASE}/${id}`),
};

export type SSEEvent =
  | { type: 'start'; id: string; conversation_id: string }
  | { type: 'tool_call'; tool_name: string; tool_args: Record<string, string> }
  | { type: 'sources'; sources: ChatSource[] }
  | { type: 'trace'; trace: ChatTrace }
  | { type: 'token'; content: string }
  | { type: 'done'; answer: string; sources: ChatSource[]; traces: ChatTrace[] }
  | { type: 'error'; message: string };

export function streamChat(
  data: ChatRequest,
  onEvent: (evt: SSEEvent) => void,
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
      const url = new URL(`${baseURL}${CHAT_BASE}/stream`, window.location.origin);
      if (wsId) url.searchParams.set('workspace_id', wsId);
      const res = await fetch(url.toString(), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(data),
        signal: controller.signal,
      });

      if (!res.ok || !res.body) {
        onError?.(new Error(`Chat stream failed: ${res.status}`));
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
            const evt = JSON.parse(line.slice(6)) as SSEEvent;
            onEvent(evt);
          } catch {
            /* skip malformed */
          }
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
