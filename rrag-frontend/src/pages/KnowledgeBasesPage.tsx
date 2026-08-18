import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { knowledgeApi } from '../api/knowledge';
import type { KnowledgeBase } from '../api/knowledge';
import { useWorkspaceStore } from '../stores/workspace.store';
import { StatusBadge } from '../components/ui/StatusBadge';
import {
  BookOpen,
  Plus,
  Settings,
  FolderOpen,
  X,
  FileText,
  Layers,
  Cpu,
  SplitSquareHorizontal,
} from 'lucide-react';

const EMBEDDING_MODELS = [
  'text-embedding-3-small',
  'text-embedding-3-large',
  'text-embedding-ada-002',
  'all-MiniLM-L6-v2',
  'bge-large-en-v1.5',
];

const CHUNK_STRATEGIES = [
  'recursive',
  'fixed',
  'sentence',
  'paragraph',
  'semantic',
];

function formatCount(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return String(n);
}

export function KnowledgeBasesPage() {
  const navigate = useNavigate();
  const workspaceId = useWorkspaceStore((s) => s.activeWorkspaceId) ?? '';
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Create dialog state
  const [showCreate, setShowCreate] = useState(false);
  const [createForm, setCreateForm] = useState({
    name: '',
    description: '',
    embedding_model: 'text-embedding-3-small',
    chunk_strategy: 'recursive',
    chunk_size: 512,
    chunk_overlap: 50,
  });
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    if (!workspaceId) return;
    try {
      const { data } = await knowledgeApi.list(workspaceId);
      setKnowledgeBases(Array.isArray(data) ? data : []);
      setError('');
    } catch {
      setError('Failed to load knowledge bases');
    } finally {
      setLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => {
    load();
  }, [load]);

  const handleCreate = async () => {
    if (!createForm.name.trim()) return;
    setCreating(true);
    try {
      await knowledgeApi.create(
        {
          name: createForm.name.trim(),
          description: createForm.description.trim() || undefined,
          embedding_model: createForm.embedding_model,
          chunk_strategy: createForm.chunk_strategy,
          chunk_size: createForm.chunk_size,
          chunk_overlap: createForm.chunk_overlap,
        },
        workspaceId,
      );
      setShowCreate(false);
      setCreateForm({
        name: '',
        description: '',
        embedding_model: 'text-embedding-3-small',
        chunk_strategy: 'recursive',
        chunk_size: 512,
        chunk_overlap: 50,
      });
      await load();
    } catch {
      setError('Failed to create knowledge base');
    } finally {
      setCreating(false);
    }
  };

  const closeCreate = () => {
    setShowCreate(false);
  };

  return (
    <div className="animate-fade-in">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-text-primary">Knowledge Bases</h1>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-1.5 px-4 py-2 bg-gradient-to-r from-accent-500 to-accent-600 text-white text-sm font-medium rounded-lg hover:from-accent-400 hover:to-accent-500 transition-all"
        >
          <Plus className="w-4 h-4" />
          Create KB
        </button>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 text-red-400 text-sm rounded-xl flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError('')} className="text-red-500 hover:text-red-300">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Create KB Modal */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 animate-fade-in">
          <div className="bg-surface-800 rounded-2xl border border-border-primary shadow-2xl max-w-lg w-full mx-4 animate-scale-in">
            <div className="flex items-center justify-between px-6 py-4 border-b border-border-primary">
              <h3 className="font-medium text-text-primary">Create Knowledge Base</h3>
              <button onClick={closeCreate} className="text-text-muted hover:text-text-primary transition-colors">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-6 space-y-4">
              {/* Name */}
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-1.5">Name *</label>
                <input
                  type="text"
                  value={createForm.name}
                  onChange={(e) => setCreateForm((f) => ({ ...f, name: e.target.value }))}
                  placeholder="e.g. Product Documentation"
                  className="w-full px-3 py-2 bg-surface-900 border border-border-primary rounded-lg text-sm text-text-primary placeholder-text-muted focus:outline-none focus:ring-1 focus:ring-accent-500 focus:border-accent-500"
                />
              </div>

              {/* Description */}
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-1.5">Description</label>
                <textarea
                  value={createForm.description}
                  onChange={(e) => setCreateForm((f) => ({ ...f, description: e.target.value }))}
                  placeholder="Optional description..."
                  rows={2}
                  className="w-full px-3 py-2 bg-surface-900 border border-border-primary rounded-lg text-sm text-text-primary placeholder-text-muted focus:outline-none focus:ring-1 focus:ring-accent-500 focus:border-accent-500 resize-none"
                />
              </div>

              {/* Embedding Model */}
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-1.5">Embedding Model</label>
                <select
                  value={createForm.embedding_model}
                  onChange={(e) => setCreateForm((f) => ({ ...f, embedding_model: e.target.value }))}
                  className="w-full px-3 py-2 bg-surface-900 border border-border-primary rounded-lg text-sm text-text-primary focus:outline-none focus:ring-1 focus:ring-accent-500 focus:border-accent-500"
                >
                  {EMBEDDING_MODELS.map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
              </div>

              {/* Chunk Strategy */}
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-1.5">Chunk Strategy</label>
                <select
                  value={createForm.chunk_strategy}
                  onChange={(e) => setCreateForm((f) => ({ ...f, chunk_strategy: e.target.value }))}
                  className="w-full px-3 py-2 bg-surface-900 border border-border-primary rounded-lg text-sm text-text-primary focus:outline-none focus:ring-1 focus:ring-accent-500 focus:border-accent-500"
                >
                  {CHUNK_STRATEGIES.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </div>

              {/* Chunk Size */}
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-1.5">
                  Chunk Size: {createForm.chunk_size}
                </label>
                <input
                  type="range"
                  min={128}
                  max={4096}
                  step={64}
                  value={createForm.chunk_size}
                  onChange={(e) => setCreateForm((f) => ({ ...f, chunk_size: Number(e.target.value) }))}
                  className="w-full accent-accent-500"
                />
                <div className="flex justify-between text-xs text-text-muted mt-1">
                  <span>128</span>
                  <span>4096</span>
                </div>
              </div>

              {/* Chunk Overlap */}
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-1.5">Chunk Overlap</label>
                <input
                  type="number"
                  min={0}
                  max={createForm.chunk_size}
                  value={createForm.chunk_overlap}
                  onChange={(e) => setCreateForm((f) => ({ ...f, chunk_overlap: Number(e.target.value) }))}
                  className="w-full px-3 py-2 bg-surface-900 border border-border-primary rounded-lg text-sm text-text-primary focus:outline-none focus:ring-1 focus:ring-accent-500 focus:border-accent-500"
                />
              </div>

              {/* Actions */}
              <div className="flex gap-2 pt-2">
                <button
                  onClick={handleCreate}
                  disabled={!createForm.name.trim() || creating}
                  className="flex-1 px-4 py-2.5 bg-gradient-to-r from-accent-500 to-accent-600 text-white text-sm font-medium rounded-lg hover:from-accent-400 hover:to-accent-500 disabled:opacity-40 transition-all"
                >
                  {creating ? 'Creating...' : 'Create Knowledge Base'}
                </button>
                <button
                  onClick={closeCreate}
                  className="px-4 py-2.5 border border-border-primary text-text-secondary text-sm rounded-lg hover:bg-surface-700 transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {loading ? (
        <div className="text-text-muted text-center py-12">Loading knowledge bases...</div>
      ) : knowledgeBases.length === 0 ? (
        <div className="text-center py-16 animate-slide-up">
          <BookOpen className="w-12 h-12 mx-auto text-text-muted mb-4 opacity-40" />
          <p className="text-text-muted mb-2">No knowledge bases yet.</p>
          <p className="text-text-muted text-sm mb-5">Create one to organize your documents and embeddings.</p>
          <button
            onClick={() => setShowCreate(true)}
            className="inline-flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-accent-500 to-accent-600 text-white text-sm font-medium rounded-lg hover:from-accent-400 hover:to-accent-500 transition-all"
          >
            <Plus className="w-4 h-4" />
            Create Knowledge Base
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {knowledgeBases.map((kb, i) => (
            <div
              key={kb.id}
              className="bg-surface-800 rounded-xl border border-border-primary p-5 animate-slide-up hover:border-border-secondary transition-colors"
              style={{ animationDelay: `${i * 40}ms` }}
            >
              {/* Title */}
              <div className="flex items-start gap-3 mb-3">
                <div className="w-9 h-9 rounded-lg bg-accent-500/10 flex items-center justify-center shrink-0">
                  <BookOpen className="w-4.5 h-4.5 text-accent-400" />
                </div>
                <div className="min-w-0 flex-1">
                  <h3 className="text-sm font-semibold text-text-primary truncate">{kb.name}</h3>
                  {kb.description && (
                    <p className="text-xs text-text-muted mt-0.5 line-clamp-1">{kb.description}</p>
                  )}
                </div>
              </div>

              {/* Stats */}
              <div className="flex items-center gap-3 text-xs text-text-muted mb-3">
                <span className="flex items-center gap-1">
                  <FileText className="w-3 h-3" />
                  {kb.document_count} documents
                </span>
                <span className="flex items-center gap-1">
                  <Layers className="w-3 h-3" />
                  {formatCount(kb.segment_count)} segments
                </span>
              </div>

              {/* Config details */}
              <div className="space-y-1.5 text-xs text-text-muted mb-3">
                <div className="flex items-center gap-1.5">
                  <Cpu className="w-3 h-3 shrink-0" />
                  <span className="truncate">Embedding: {kb.embedding_model}</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <SplitSquareHorizontal className="w-3 h-3 shrink-0" />
                  <span>Strategy: {kb.chunk_strategy} &middot; {kb.chunk_size}</span>
                </div>
              </div>

              {/* Status */}
              <div className="mb-4">
                <StatusBadge status={kb.status === 'ready' ? 'completed' : kb.status} />
              </div>

              {/* Actions */}
              <div className="flex items-center gap-2">
                <button
                  onClick={() => navigate(`/knowledge-bases/${kb.id}`)}
                  className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 bg-gradient-to-r from-accent-500 to-accent-600 text-white text-xs font-medium rounded-lg hover:from-accent-400 hover:to-accent-500 transition-all"
                >
                  <FolderOpen className="w-3.5 h-3.5" />
                  Manage
                </button>
                <button
                  onClick={() => navigate(`/knowledge-bases/${kb.id}?tab=settings`)}
                  className="flex items-center justify-center gap-1.5 px-3 py-1.5 border border-border-primary text-text-secondary text-xs rounded-lg hover:bg-surface-700 transition-colors"
                >
                  <Settings className="w-3.5 h-3.5" />
                  Settings
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
