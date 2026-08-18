import client from './client';

export interface QueryRequest {
  query: string;
  model?: string;
  temperature?: number;
  max_tokens?: number;
  system_prompt?: string;
  top_k?: number;
  conversation_id?: string | null;
  datastore_id?: string | null;
  strategy?: string;
  stream?: boolean;
}

export interface QuerySource {
  id: string;
  content: string;
  score: number;
  metadata: Record<string, unknown>;
}

export interface QueryResponse {
  id: string;
  conversation_id: string;
  query: string;
  answer: string;
  sources: QuerySource[];
  model: string;
  tokens_used: number;
  duration_ms: number;
  strategy: string;
}

export interface ConversationMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

const BASE = '/api/v1/ingestion/query';

export const queryApi = {
  query: (data: QueryRequest) =>
    client.post<QueryResponse>(BASE, data),

  getConversation: (conversationId: string) =>
    client.get<{ conversation_id: string; messages: ConversationMessage[] }>(
      `${BASE}/conversations/${conversationId}`,
    ),

  deleteConversation: (conversationId: string) =>
    client.delete(`${BASE}/conversations/${conversationId}`),
};
