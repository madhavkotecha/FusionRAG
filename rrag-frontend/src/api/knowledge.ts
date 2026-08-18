import client from './client';

export interface KnowledgeBase {
  id: string;
  workspace_id: string;
  name: string;
  description: string;
  embedding_model: string;
  embedding_provider: string;
  chunk_strategy: string;
  chunk_size: number;
  chunk_overlap: number;
  retrieval_config: Record<string, unknown>;
  document_count: number;
  segment_count: number;
  word_count: number;
  status: string;
  created_at: string;
  updated_at: string | null;
}

export interface KBDocument {
  id: string;
  knowledge_base_id: string;
  filename: string;
  source_type: string;
  status: string;
  segment_count: number;
  word_count: number;
  error: string | null;
  created_at: string;
}

export interface KBSegment {
  id: string;
  document_id: string;
  position: number;
  content: string;
  word_count: number;
  tokens: number;
  enabled: boolean;
}

export const knowledgeApi = {
  list: (workspaceId: string) =>
    client.get<KnowledgeBase[]>('/api/v1/ingestion/knowledge-bases', { params: { workspace_id: workspaceId } }),
  get: (id: string, workspaceId: string) =>
    client.get<KnowledgeBase>(`/api/v1/ingestion/knowledge-bases/${id}`, { params: { workspace_id: workspaceId } }),
  create: (data: { name: string; description?: string; embedding_model?: string; chunk_strategy?: string; chunk_size?: number; chunk_overlap?: number }, workspaceId: string) =>
    client.post<KnowledgeBase>('/api/v1/ingestion/knowledge-bases', data, { params: { workspace_id: workspaceId } }),
  update: (id: string, data: Partial<KnowledgeBase>, workspaceId: string) =>
    client.put<KnowledgeBase>(`/api/v1/ingestion/knowledge-bases/${id}`, data, { params: { workspace_id: workspaceId } }),
  delete: (id: string, workspaceId: string) =>
    client.delete(`/api/v1/ingestion/knowledge-bases/${id}`, { params: { workspace_id: workspaceId } }),
  // Documents within a KB
  listDocuments: (kbId: string, workspaceId: string) =>
    client.get<KBDocument[]>(`/api/v1/ingestion/knowledge-bases/${kbId}/documents`, { params: { workspace_id: workspaceId } }),
  uploadDocuments: (kbId: string, files: File[], workspaceId: string) => {
    const form = new FormData();
    files.forEach(f => form.append('files', f));
    return client.post(`/api/v1/ingestion/knowledge-bases/${kbId}/documents`, form, {
      params: { workspace_id: workspaceId },
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  deleteDocument: (kbId: string, docId: string, workspaceId: string) =>
    client.delete(`/api/v1/ingestion/knowledge-bases/${kbId}/documents/${docId}`, { params: { workspace_id: workspaceId } }),
  // Segments
  listSegments: (kbId: string, workspaceId: string, page = 1, pageSize = 50) =>
    client.get<{ segments: KBSegment[]; total: number }>(`/api/v1/ingestion/knowledge-bases/${kbId}/segments`, {
      params: { workspace_id: workspaceId, page, page_size: pageSize },
    }),
  toggleSegment: (kbId: string, segId: string, enabled: boolean, workspaceId: string) =>
    client.patch(`/api/v1/ingestion/knowledge-bases/${kbId}/segments/${segId}`, { enabled }, { params: { workspace_id: workspaceId } }),
};
