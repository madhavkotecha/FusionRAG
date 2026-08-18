import { useEffect, useState, useCallback, useRef } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { knowledgeApi } from '../api/knowledge';
import type { KnowledgeBase, KBDocument, KBSegment } from '../api/knowledge';
import { useWorkspaceStore } from '../stores/workspace.store';
import { StatusBadge } from '../components/ui/StatusBadge';
import {
  ArrowLeft,
  FileText,
  Layers,
  Settings,
  Trash2,
  X,
  CloudUpload,
  Search,
  ChevronLeft,
  ChevronRight,
  ToggleLeft,
  ToggleRight,
  Save,
  BookOpen,
} from 'lucide-react';

type TabId = 'documents' | 'segments' | 'settings';

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

const ALLOWED_EXTENSIONS = new Set([
  '.pdf', '.txt', '.md', '.csv', '.json', '.jsonl',
  '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
  '.html', '.htm', '.xml', '.yaml', '.yml',
]);

const MAX_FILE_SIZE = 100 * 1024 * 1024;

function validateFiles(files: File[]): string | null {
  for (const file of files) {
    const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
    if (!ALLOWED_EXTENSIONS.has(ext)) {
      return `Unsupported file type: ${ext} (${file.name})`;
    }
    if (file.size > MAX_FILE_SIZE) {
      return `File too large: ${file.name} (${Math.round(file.size / 1024 / 1024)} MB, max 100 MB)`;
    }
  }
  return null;
}

function formatCount(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return String(n);
}

export function KnowledgeBaseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const workspaceId = useWorkspaceStore((s) => s.activeWorkspaceId) ?? '';

  const initialTab = (searchParams.get('tab') as TabId) || 'documents';
  const [activeTab, setActiveTab] = useState<TabId>(initialTab);
  const [kb, setKb] = useState<KnowledgeBase | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  // Documents state
  const [documents, setDocuments] = useState<KBDocument[]>([]);
  const [docsLoading, setDocsLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  // Segments state
  const [segments, setSegments] = useState<KBSegment[]>([]);
  const [segmentsTotal, setSegmentsTotal] = useState(0);
  const [segPage, setSegPage] = useState(1);
  const [segSearch, setSegSearch] = useState('');
  const [segsLoading, setSegsLoading] = useState(false);
  const segPageSize = 50;

  // Settings state
  const [settingsForm, setSettingsForm] = useState({
    embedding_model: '',
    chunk_strategy: '',
    chunk_size: 512,
    chunk_overlap: 50,
  });
  const [saving, setSaving] = useState(false);

  const loadKB = useCallback(async () => {
    if (!id || !workspaceId) return;
    try {
      const { data } = await knowledgeApi.get(id, workspaceId);
      setKb(data);
      setSettingsForm({
        embedding_model: data.embedding_model,
        chunk_strategy: data.chunk_strategy,
        chunk_size: data.chunk_size,
        chunk_overlap: data.chunk_overlap,
      });
      setError('');
    } catch {
      setError('Failed to load knowledge base');
    } finally {
      setLoading(false);
    }
  }, [id, workspaceId]);

  const loadDocuments = useCallback(async () => {
    if (!id || !workspaceId) return;
    setDocsLoading(true);
    try {
      const { data } = await knowledgeApi.listDocuments(id, workspaceId);
      setDocuments(Array.isArray(data) ? data : []);
    } catch {
      setError('Failed to load documents');
    } finally {
      setDocsLoading(false);
    }
  }, [id, workspaceId]);

  const loadSegments = useCallback(async (page: number) => {
    if (!id || !workspaceId) return;
    setSegsLoading(true);
    try {
      const { data } = await knowledgeApi.listSegments(id, workspaceId, page, segPageSize);
      setSegments(data.segments ?? []);
      setSegmentsTotal(data.total ?? 0);
    } catch {
      setError('Failed to load segments');
    } finally {
      setSegsLoading(false);
    }
  }, [id, workspaceId]);

  useEffect(() => {
    loadKB();
  }, [loadKB]);

  useEffect(() => {
    if (activeTab === 'documents') loadDocuments();
    if (activeTab === 'segments') loadSegments(segPage);
  }, [activeTab, loadDocuments, loadSegments, segPage]);

  const handleTabChange = (tab: TabId) => {
    setActiveTab(tab);
    setSearchParams({ tab });
  };

  // --- Documents tab handlers ---
  const uploadFiles = useCallback(async (fileList: File[]) => {
    if (!id) return;
    const validationError = validateFiles(fileList);
    if (validationError) {
      setError(validationError);
      return;
    }
    setUploading(true);
    setError('');
    try {
      await knowledgeApi.uploadDocuments(id, fileList, workspaceId);
      if (fileRef.current) fileRef.current.value = '';
      await loadDocuments();
      await loadKB();
    } catch {
      setError('Upload failed');
    } finally {
      setUploading(false);
    }
  }, [id, workspaceId, loadDocuments, loadKB]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) uploadFiles(files);
  }, [uploadFiles]);

  const handleDeleteDoc = async (docId: string) => {
    if (!id) return;
    try {
      await knowledgeApi.deleteDocument(id, docId, workspaceId);
      setDocuments((d) => d.filter((doc) => doc.id !== docId));
      await loadKB();
    } catch {
      setError('Failed to delete document');
    }
  };

  // --- Segments tab handlers ---
  const handleToggleSegment = async (segId: string, enabled: boolean) => {
    if (!id) return;
    try {
      await knowledgeApi.toggleSegment(id, segId, enabled, workspaceId);
      setSegments((prev) => prev.map((s) => s.id === segId ? { ...s, enabled } : s));
    } catch {
      setError('Failed to toggle segment');
    }
  };

  const filteredSegments = segSearch
    ? segments.filter((s) => s.content.toLowerCase().includes(segSearch.toLowerCase()))
    : segments;

  const totalPages = Math.ceil(segmentsTotal / segPageSize);

  // --- Settings tab handlers ---
  const handleSaveSettings = async () => {
    if (!id) return;
    setSaving(true);
    try {
      await knowledgeApi.update(id, {
        embedding_model: settingsForm.embedding_model,
        chunk_strategy: settingsForm.chunk_strategy,
        chunk_size: settingsForm.chunk_size,
        chunk_overlap: settingsForm.chunk_overlap,
      } as Partial<KnowledgeBase>, workspaceId);
      await loadKB();
    } catch {
      setError('Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div className="text-text-muted text-center py-12 animate-fade-in">Loading knowledge base...</div>;
  }

  if (!kb) {
    return (
      <div className="text-center py-16 animate-fade-in">
        <BookOpen className="w-12 h-12 mx-auto text-text-muted mb-4 opacity-40" />
        <p className="text-text-muted mb-4">Knowledge base not found.</p>
        <button
          onClick={() => navigate('/knowledge-bases')}
          className="text-accent-400 hover:text-accent-300 text-sm"
        >
          Back to Knowledge Bases
        </button>
      </div>
    );
  }

  const tabs: { id: TabId; label: string; icon: typeof FileText }[] = [
    { id: 'documents', label: 'Documents', icon: FileText },
    { id: 'segments', label: 'Segments', icon: Layers },
    { id: 'settings', label: 'Settings', icon: Settings },
  ];

  return (
    <div className="animate-fade-in">
      {/* Header */}
      <div className="flex items-center gap-3 mb-2">
        <button
          onClick={() => navigate('/knowledge-bases')}
          className="p-1.5 rounded-lg text-text-muted hover:text-text-primary hover:bg-surface-700 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
        </button>
        <div className="flex-1 min-w-0">
          <h1 className="text-xl font-bold text-text-primary truncate">{kb.name}</h1>
          {kb.description && (
            <p className="text-sm text-text-muted mt-0.5">{kb.description}</p>
          )}
        </div>
        <StatusBadge status={kb.status === 'ready' ? 'completed' : kb.status} />
      </div>

      {/* Stats bar */}
      <div className="flex items-center gap-4 text-xs text-text-muted mb-5 ml-10">
        <span>{kb.document_count} documents</span>
        <span>{formatCount(kb.segment_count)} segments</span>
        <span>{formatCount(kb.word_count)} words</span>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 text-red-400 text-sm rounded-xl flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError('')} className="text-red-500 hover:text-red-300">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Tabs */}
      <div className="flex items-center gap-1 mb-6 border-b border-border-primary">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => handleTabChange(tab.id)}
            className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab.id
                ? 'border-accent-500 text-accent-400'
                : 'border-transparent text-text-muted hover:text-text-secondary'
            }`}
          >
            <tab.icon className="w-3.5 h-3.5" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Documents Tab */}
      {activeTab === 'documents' && (
        <div>
          {/* Upload drop zone */}
          <div
            onDrop={handleDrop}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onClick={() => fileRef.current?.click()}
            className={`relative cursor-pointer rounded-xl border-2 border-dashed transition-all duration-200 py-10 px-6 text-center mb-6 ${
              dragOver
                ? 'border-accent-400 bg-accent-500/10'
                : 'border-border-secondary bg-surface-800/50 hover:border-accent-500/50 hover:bg-surface-800'
            }`}
          >
            <CloudUpload className={`w-8 h-8 mx-auto mb-2 transition-colors ${dragOver ? 'text-accent-400' : 'text-text-muted'}`} />
            <p className="text-sm text-text-muted">
              Drag and drop files here, or click to browse
            </p>
            <p className="text-xs text-text-muted/60 mt-1">PDF, TXT, Markdown, CSV, JSON, DOCX, XLSX, HTML, YAML (max 100 MB)</p>
            <input
              ref={fileRef}
              type="file"
              multiple
              accept={Array.from(ALLOWED_EXTENSIONS).join(',')}
              onChange={(e) => {
                const files = e.target.files;
                if (files?.length) uploadFiles(Array.from(files));
              }}
              className="hidden"
            />
            {uploading && (
              <div className="absolute inset-0 bg-surface-900/80 rounded-xl flex items-center justify-center">
                <div className="flex items-center gap-3 text-accent-400">
                  <div className="w-5 h-5 border-2 border-accent-400 border-t-transparent rounded-full animate-spin" />
                  <span className="text-sm font-medium">Uploading...</span>
                </div>
              </div>
            )}
          </div>

          {/* Documents list */}
          {docsLoading ? (
            <div className="text-text-muted text-center py-8 text-sm">Loading documents...</div>
          ) : documents.length === 0 ? (
            <div className="text-center py-8">
              <FileText className="w-8 h-8 mx-auto text-text-muted mb-2 opacity-40" />
              <p className="text-sm text-text-muted">No documents yet. Upload files above.</p>
            </div>
          ) : (
            <div className="bg-surface-800 rounded-xl border border-border-primary overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-surface-900 border-b border-border-primary">
                  <tr>
                    <th className="text-left px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Filename</th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Type</th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Status</th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Segments</th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Words</th>
                    <th className="text-right px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {documents.map((doc) => (
                    <tr key={doc.id} className="border-b border-border-primary last:border-0 hover:bg-surface-700/50 transition-colors">
                      <td className="px-4 py-3 font-medium text-text-primary">{doc.filename}</td>
                      <td className="px-4 py-3 text-text-muted">{doc.source_type}</td>
                      <td className="px-4 py-3">
                        <StatusBadge status={doc.status} />
                        {doc.error && (
                          <span className="ml-2 text-xs text-red-400" title={doc.error}>Error</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-text-muted">{doc.segment_count}</td>
                      <td className="px-4 py-3 text-text-muted">{formatCount(doc.word_count)}</td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => handleDeleteDoc(doc.id)}
                          className="inline-flex items-center gap-1 text-red-400 hover:text-red-300 text-sm transition-colors"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Segments Tab */}
      {activeTab === 'segments' && (
        <div>
          {/* Search bar */}
          <div className="flex items-center gap-3 mb-4">
            <div className="relative flex-1">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
              <input
                type="text"
                value={segSearch}
                onChange={(e) => setSegSearch(e.target.value)}
                placeholder="Search segments..."
                className="w-full pl-9 pr-3 py-2 bg-surface-800 border border-border-primary rounded-lg text-sm text-text-primary placeholder-text-muted focus:outline-none focus:ring-1 focus:ring-accent-500 focus:border-accent-500"
              />
            </div>
            <span className="text-xs text-text-muted shrink-0">{segmentsTotal} total segments</span>
          </div>

          {segsLoading ? (
            <div className="text-text-muted text-center py-8 text-sm">Loading segments...</div>
          ) : filteredSegments.length === 0 ? (
            <div className="text-center py-8">
              <Layers className="w-8 h-8 mx-auto text-text-muted mb-2 opacity-40" />
              <p className="text-sm text-text-muted">No segments found.</p>
            </div>
          ) : (
            <div className="space-y-2">
              {filteredSegments.map((seg) => (
                <div
                  key={seg.id}
                  className={`bg-surface-800 rounded-xl border border-border-primary p-4 transition-colors ${
                    !seg.enabled ? 'opacity-50' : ''
                  }`}
                >
                  <div className="flex items-start justify-between gap-3 mb-2">
                    <div className="flex items-center gap-2 text-xs text-text-muted">
                      <span className="font-mono">#{seg.position}</span>
                      <span>{seg.word_count} words</span>
                      <span>{seg.tokens} tokens</span>
                    </div>
                    <button
                      onClick={() => handleToggleSegment(seg.id, !seg.enabled)}
                      className={`shrink-0 transition-colors ${seg.enabled ? 'text-accent-400' : 'text-text-muted hover:text-text-secondary'}`}
                      title={seg.enabled ? 'Disable segment' : 'Enable segment'}
                    >
                      {seg.enabled ? <ToggleRight className="w-5 h-5" /> : <ToggleLeft className="w-5 h-5" />}
                    </button>
                  </div>
                  <p className="text-sm text-text-secondary whitespace-pre-wrap line-clamp-4">
                    {seg.content}
                  </p>
                </div>
              ))}
            </div>
          )}

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-3 mt-6">
              <button
                onClick={() => setSegPage((p) => Math.max(1, p - 1))}
                disabled={segPage <= 1}
                className="p-1.5 rounded-lg text-text-muted hover:text-text-primary hover:bg-surface-700 disabled:opacity-30 transition-colors"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <span className="text-sm text-text-muted">
                Page {segPage} of {totalPages}
              </span>
              <button
                onClick={() => setSegPage((p) => Math.min(totalPages, p + 1))}
                disabled={segPage >= totalPages}
                className="p-1.5 rounded-lg text-text-muted hover:text-text-primary hover:bg-surface-700 disabled:opacity-30 transition-colors"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>
      )}

      {/* Settings Tab */}
      {activeTab === 'settings' && (
        <div className="max-w-xl space-y-5">
          {/* Embedding Model */}
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-1.5">Embedding Model</label>
            <select
              value={settingsForm.embedding_model}
              onChange={(e) => setSettingsForm((f) => ({ ...f, embedding_model: e.target.value }))}
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
              value={settingsForm.chunk_strategy}
              onChange={(e) => setSettingsForm((f) => ({ ...f, chunk_strategy: e.target.value }))}
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
              Chunk Size: {settingsForm.chunk_size}
            </label>
            <input
              type="range"
              min={128}
              max={4096}
              step={64}
              value={settingsForm.chunk_size}
              onChange={(e) => setSettingsForm((f) => ({ ...f, chunk_size: Number(e.target.value) }))}
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
              max={settingsForm.chunk_size}
              value={settingsForm.chunk_overlap}
              onChange={(e) => setSettingsForm((f) => ({ ...f, chunk_overlap: Number(e.target.value) }))}
              className="w-full px-3 py-2 bg-surface-900 border border-border-primary rounded-lg text-sm text-text-primary focus:outline-none focus:ring-1 focus:ring-accent-500 focus:border-accent-500"
            />
          </div>

          <button
            onClick={handleSaveSettings}
            disabled={saving}
            className="flex items-center gap-1.5 px-5 py-2.5 bg-gradient-to-r from-accent-500 to-accent-600 text-white text-sm font-medium rounded-lg hover:from-accent-400 hover:to-accent-500 disabled:opacity-40 transition-all"
          >
            <Save className="w-4 h-4" />
            {saving ? 'Saving...' : 'Save Settings'}
          </button>
        </div>
      )}
    </div>
  );
}
