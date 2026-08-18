import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { queryPipelineApi, type QueryPipeline, type CreateQueryPipelineRequest } from '../api/chat';
import { ingestionApi, type DataStore } from '../api/ingestion';
import {
  Plus,
  Trash2,
  Search,
  MessageSquare,
  Loader2,
  GitBranch,
  Database,
  Pencil,
  X,
  Zap,
  Network,
  Layers,
  BookOpen,
  Sparkles,
  Globe,
  Check,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';

/* ------------------------------------------------------------------ */
/*  Query Pipeline Templates (counterparts of ingestion templates)     */
/* ------------------------------------------------------------------ */

interface QPTemplate {
  id: string;
  name: string;
  description: string;
  badge?: string;
  icon: React.ElementType;
  features: string[];
  config: Omit<CreateQueryPipelineRequest, 'name' | 'description' | 'datastore_id'>;
}

const QP_TEMPLATES: QPTemplate[] = [
  {
    id: 'simple_vector',
    name: 'Simple Vector Search',
    description: 'Fast dense retrieval with embedding similarity. Best for straightforward Q&A over ingested documents.',
    badge: 'Recommended',
    icon: Zap,
    features: ['Dense retrieval', 'Top-20 results', 'GPT-4o-mini', 'Inline citations'],
    config: {
      retrieval_strategy: 'vector',
      retriever: { strategy: 'dense', top_k: 20, score_threshold: 0.0 },
      reranker: { enabled: false, model: 'cross-encoder/ms-marco-MiniLM-L-6-v2', top_k: 10 },
      generator: {
        model: 'gpt-4o-mini',
        temperature: 0.2,
        max_tokens: 2048,
        system_prompt:
          'You are a helpful research assistant. Answer questions accurately based on the provided context. If you don\'t have enough context, say so clearly. Cite document numbers when referencing sources.',
      },
    },
  },
  {
    id: 'lightrag_search',
    name: 'LightRAG Search',
    description: 'Hybrid vector + knowledge graph retrieval. Ideal for data ingested with the LightRAG pipeline.',
    icon: Network,
    features: ['Hybrid retrieval', 'Graph depth 2', 'Cross-encoder reranker', 'Inline citations'],
    config: {
      retrieval_strategy: 'hybrid',
      retriever: {
        strategy: 'hybrid',
        top_k: 30,
        score_threshold: 0.0,
        alpha: 0.6,
        fusion_method: 'rrf',
        use_mmr: true,
      },
      reranker: {
        enabled: true,
        model: 'cross-encoder/ms-marco-MiniLM-L-6-v2',
        top_k: 10,
      },
      generator: {
        model: 'gpt-4o-mini',
        temperature: 0.2,
        max_tokens: 2048,
        system_prompt:
          'You are a research assistant with access to a knowledge graph and document store. Synthesize information from both vector search and graph relationships. Provide comprehensive answers with inline citations.',
      },
    },
  },
  {
    id: 'kag_search',
    name: 'KAG Search',
    description: 'Knowledge-augmented generation with graph reasoning and multi-hop planning. For KAG-ingested data.',
    badge: 'Advanced',
    icon: Layers,
    features: ['Graph retrieval', 'CoRAG planner', 'Chain-of-thought', 'Cross-encoder reranker'],
    config: {
      retrieval_strategy: 'hybrid',
      retriever: {
        strategy: 'hybrid',
        top_k: 30,
        score_threshold: 0.0,
        alpha: 0.5,
        fusion_method: 'rrf',
      },
      reranker: {
        enabled: true,
        model: 'cross-encoder/ms-marco-MiniLM-L-6-v2',
        top_k: 10,
      },
      generator: {
        model: 'gpt-4o-mini',
        temperature: 0.1,
        max_tokens: 4096,
        system_prompt:
          'You are an expert knowledge assistant. Use the structured knowledge graph and retrieved documents to answer questions with precise reasoning. Think step by step before answering. Always cite your sources.',
        enable_cot: true,
      },
      planner: { enabled: true, strategy: 'corag' },
    },
  },
  {
    id: 'corag_search',
    name: 'CoRAG Search',
    description: 'Chain-of-Retrieval augmented generation with iterative multi-hop retrieval for complex queries.',
    icon: BookOpen,
    features: ['Dense retrieval', 'CoRAG planner', '3-hop max', 'Chain-of-thought'],
    config: {
      retrieval_strategy: 'vector',
      retriever: { strategy: 'dense', top_k: 20, score_threshold: 0.0 },
      reranker: {
        enabled: true,
        model: 'cross-encoder/ms-marco-MiniLM-L-6-v2',
        top_k: 8,
      },
      generator: {
        model: 'gpt-4o-mini',
        temperature: 0.2,
        max_tokens: 4096,
        system_prompt:
          'You are a research assistant that answers complex questions by iteratively gathering evidence. Reason through each retrieval step before synthesizing your final answer. Cite all sources used.',
        enable_cot: true,
      },
      planner: { enabled: true, strategy: 'corag' },
    },
  },
  {
    id: 'ultrarag_search',
    name: 'UltraRAG Search',
    description: 'Multi-strategy retrieval with MMR diversity and reranking. Best for UltraRAG-ingested data.',
    icon: Sparkles,
    features: ['Hybrid retrieval', 'MMR diversity', 'Cross-encoder reranker', 'Structured citations'],
    config: {
      retrieval_strategy: 'hybrid',
      retriever: {
        strategy: 'hybrid',
        top_k: 30,
        score_threshold: 0.0,
        alpha: 0.7,
        fusion_method: 'rrf',
        use_mmr: true,
      },
      reranker: {
        enabled: true,
        model: 'cross-encoder/ms-marco-MiniLM-L-6-v2',
        top_k: 10,
      },
      generator: {
        model: 'gpt-4o-mini',
        temperature: 0.2,
        max_tokens: 2048,
        system_prompt:
          'You are a helpful assistant. Answer questions using the provided context. Use diverse sources when available and cite them clearly.',
      },
    },
  },
  {
    id: 'hybrid_fulltext',
    name: 'Hybrid Full-Text',
    description: 'BM25 + vector fusion via OpenSearch. Ideal for data ingested with the OpenSearch Full-Text pipeline.',
    icon: Globe,
    features: ['Sparse + dense fusion', 'RRF fusion', 'Reranker', 'Full-text BM25'],
    config: {
      retrieval_strategy: 'hybrid',
      retriever: {
        strategy: 'hybrid',
        top_k: 25,
        score_threshold: 0.0,
        alpha: 0.4,
        fusion_method: 'rrf',
      },
      reranker: {
        enabled: true,
        model: 'cross-encoder/ms-marco-MiniLM-L-6-v2',
        top_k: 10,
      },
      generator: {
        model: 'gpt-4o-mini',
        temperature: 0.2,
        max_tokens: 2048,
        system_prompt:
          'You are a helpful research assistant. Answer questions accurately based on the provided context. If you don\'t have enough context, say so clearly. Cite document numbers when referencing sources.',
      },
    },
  },
];

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function QueryPipelinesPage() {
  const navigate = useNavigate();
  const [pipelines, setPipelines] = useState<QueryPipeline[]>([]);
  const [datastores, setDatastores] = useState<DataStore[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState('');

  // Form state
  const [activeTab, setActiveTab] = useState<'templates' | 'custom'>('templates');
  const [selectedTemplate, setSelectedTemplate] = useState<string | null>(null);
  const [formName, setFormName] = useState('');
  const [formDesc, setFormDesc] = useState('');
  const [formDatastoreId, setFormDatastoreId] = useState('');
  const [expandedTemplate, setExpandedTemplate] = useState<string | null>(null);

  const readyDatastores = datastores.filter((d) => d.status === 'ready' || d.status === 'completed');

  const loadData = async () => {
    setLoading(true);
    try {
      const [pRes, dRes] = await Promise.all([
        queryPipelineApi.list(),
        ingestionApi.listDataStores(),
      ]);
      setPipelines(pRes.data.query_pipelines);
      setDatastores(dRes.data.datastores);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const selectTemplate = (tplId: string) => {
    const tpl = QP_TEMPLATES.find((t) => t.id === tplId);
    if (!tpl) return;
    setSelectedTemplate(tplId);
    if (!formName) setFormName(tpl.name);
    if (!formDesc) setFormDesc(tpl.description);
  };

  const handleCreate = async () => {
    if (!formName || !formDatastoreId) return;
    setCreating(true);
    setError('');
    try {
      const tpl = activeTab === 'templates' ? QP_TEMPLATES.find((t) => t.id === selectedTemplate) : null;
      const payload: CreateQueryPipelineRequest = {
        name: formName,
        description: formDesc || undefined,
        datastore_id: formDatastoreId,
        ...(tpl ? tpl.config : {}),
      };
      await queryPipelineApi.create(payload);
      setShowCreate(false);
      setFormName('');
      setFormDesc('');
      setFormDatastoreId('');
      setSelectedTemplate(null);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Create failed');
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await queryPipelineApi.delete(id);
      setPipelines((prev) => prev.filter((p) => p.id !== id));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Delete failed');
    }
  };

  const openChat = (pipelineId: string) => {
    const params = new URLSearchParams();
    params.append('qp', pipelineId);
    navigate(`/chat?${params.toString()}`);
  };

  return (
    <div className="animate-fade-in space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-text-primary flex items-center gap-2">
            <Search className="w-5 h-5 text-accent-400" />
            Query Pipelines
          </h1>
          <p className="text-sm text-text-muted mt-1">
            Design retrieval pipelines visually. Each pipeline becomes a tool the chat LLM can use.
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-1.5 px-4 py-2 bg-gradient-to-r from-accent-500 to-accent-600 text-white text-sm font-medium rounded-lg hover:from-accent-400 hover:to-accent-500 transition-all"
        >
          <Plus className="w-4 h-4" />
          New Query Pipeline
        </button>
      </div>

      {error && (
        <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-400 text-sm rounded-xl flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError('')}><X className="w-3.5 h-3.5" /></button>
        </div>
      )}

      {/* Create panel */}
      {showCreate && (
        <div className="bg-surface-800 border border-border-primary rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-text-primary">Create Query Pipeline</h2>
            <button onClick={() => setShowCreate(false)} className="text-text-muted hover:text-text-primary">
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Tabs */}
          <div className="flex gap-1 bg-surface-900 rounded-lg p-0.5">
            <button
              onClick={() => setActiveTab('templates')}
              className={`flex-1 text-xs py-1.5 rounded-md transition-all ${
                activeTab === 'templates'
                  ? 'bg-accent-500/20 text-accent-400 font-medium'
                  : 'text-text-muted hover:text-text-secondary'
              }`}
            >
              From Template
            </button>
            <button
              onClick={() => setActiveTab('custom')}
              className={`flex-1 text-xs py-1.5 rounded-md transition-all ${
                activeTab === 'custom'
                  ? 'bg-accent-500/20 text-accent-400 font-medium'
                  : 'text-text-muted hover:text-text-secondary'
              }`}
            >
              Custom
            </button>
          </div>

          {/* Template cards */}
          {activeTab === 'templates' && (
            <div className="grid grid-cols-3 gap-3">
              {QP_TEMPLATES.map((tpl) => {
                const Icon = tpl.icon;
                const selected = selectedTemplate === tpl.id;
                return (
                  <button
                    key={tpl.id}
                    onClick={() => selectTemplate(tpl.id)}
                    className={`relative text-left p-3 rounded-xl border transition-all ${
                      selected
                        ? 'border-accent-500 bg-accent-500/10 ring-1 ring-accent-500/30'
                        : 'border-border-primary bg-surface-900 hover:border-accent-500/30'
                    }`}
                  >
                    {selected && (
                      <div className="absolute top-2 right-2 w-5 h-5 bg-accent-500 rounded-full flex items-center justify-center">
                        <Check className="w-3 h-3 text-white" />
                      </div>
                    )}
                    {tpl.badge && (
                      <span className="absolute top-2 right-2 text-[9px] px-1.5 py-0.5 rounded bg-accent-500/20 text-accent-400 font-medium">
                        {selected ? '' : tpl.badge}
                      </span>
                    )}
                    <div className="flex items-center gap-2 mb-2">
                      <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-accent-500/20 to-highlight-500/20 flex items-center justify-center">
                        <Icon className="w-4 h-4 text-accent-400" />
                      </div>
                      <span className="text-xs font-medium text-text-primary">{tpl.name}</span>
                    </div>
                    <p className="text-[10px] text-text-muted leading-relaxed mb-2 line-clamp-2">
                      {tpl.description}
                    </p>
                    <div className="flex flex-wrap gap-1">
                      {tpl.features.map((f) => (
                        <span key={f} className="text-[9px] px-1.5 py-0.5 rounded bg-surface-700 text-text-muted">
                          {f}
                        </span>
                      ))}
                    </div>
                    {/* Expand/collapse config details */}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setExpandedTemplate(expandedTemplate === tpl.id ? null : tpl.id);
                      }}
                      className="mt-2 flex items-center gap-1 text-[9px] text-accent-400 hover:text-accent-300"
                    >
                      Config details
                      {expandedTemplate === tpl.id ? <ChevronUp className="w-2.5 h-2.5" /> : <ChevronDown className="w-2.5 h-2.5" />}
                    </button>
                    {expandedTemplate === tpl.id && (
                      <div className="mt-1.5 p-2 bg-surface-800 rounded-lg text-[9px] text-text-muted space-y-0.5 font-mono">
                        <div>strategy: {tpl.config.retrieval_strategy}</div>
                        <div>retriever.top_k: {tpl.config.retriever?.top_k}</div>
                        {tpl.config.retriever?.alpha !== undefined && <div>retriever.alpha: {tpl.config.retriever.alpha}</div>}
                        {tpl.config.retriever?.use_mmr && <div>retriever.mmr: enabled</div>}
                        <div>reranker: {tpl.config.reranker?.enabled ? 'enabled' : 'disabled'}</div>
                        {tpl.config.reranker?.enabled && <div>reranker.top_k: {tpl.config.reranker.top_k}</div>}
                        <div>generator: {tpl.config.generator?.model}</div>
                        <div>temperature: {tpl.config.generator?.temperature}</div>
                        {tpl.config.generator?.enable_cot && <div>chain-of-thought: enabled</div>}
                        {tpl.config.planner?.enabled && <div>planner: {tpl.config.planner.strategy}</div>}
                      </div>
                    )}
                  </button>
                );
              })}
            </div>
          )}

          {/* Name / DataStore / Description */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs text-text-muted block mb-1">Name</label>
              <input
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                className="w-full bg-surface-900 border border-border-primary rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent-500"
                placeholder="My Query Pipeline"
              />
            </div>
            <div>
              <label className="text-xs text-text-muted block mb-1">DataStore</label>
              <select
                value={formDatastoreId}
                onChange={(e) => setFormDatastoreId(e.target.value)}
                className="w-full bg-surface-900 border border-border-primary rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent-500"
              >
                <option value="">Select a datastore...</option>
                {readyDatastores.map((d) => (
                  <option key={d.id} value={d.id}>{d.name}</option>
                ))}
              </select>
              {readyDatastores.length === 0 && (
                <p className="text-[10px] text-yellow-400 mt-1">
                  No ready datastores. Ingest documents first via DataStores page.
                </p>
              )}
            </div>
            <div className="col-span-2">
              <label className="text-xs text-text-muted block mb-1">Description</label>
              <input
                value={formDesc}
                onChange={(e) => setFormDesc(e.target.value)}
                className="w-full bg-surface-900 border border-border-primary rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent-500"
                placeholder="Describe what this pipeline queries..."
              />
            </div>
          </div>

          {activeTab === 'templates' && selectedTemplate && (
            <p className="text-[10px] text-text-muted">
              Template <span className="text-accent-400 font-medium">{QP_TEMPLATES.find((t) => t.id === selectedTemplate)?.name}</span> will
              pre-configure the retriever, reranker, and generator. You can edit all settings in the visual editor after creation.
            </p>
          )}
          {activeTab === 'custom' && (
            <p className="text-[10px] text-text-muted">
              Creates a pipeline with default settings. You'll be taken to the visual editor to configure retriever, reranker, generator, planner, and agent components.
            </p>
          )}

          <div className="flex gap-2 justify-end">
            <button
              onClick={() => { setShowCreate(false); setSelectedTemplate(null); }}
              className="px-3 py-1.5 text-sm text-text-muted hover:text-text-primary"
            >
              Cancel
            </button>
            <button
              onClick={handleCreate}
              disabled={creating || !formName || !formDatastoreId || (activeTab === 'templates' && !selectedTemplate)}
              className="flex items-center gap-1.5 px-4 py-1.5 bg-accent-500 text-white text-sm rounded-lg hover:bg-accent-400 disabled:opacity-40 transition-all"
            >
              {creating && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              Create Pipeline
            </button>
          </div>
        </div>
      )}

      {/* Pipeline list */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-6 h-6 animate-spin text-accent-400" />
        </div>
      ) : pipelines.length === 0 ? (
        <div className="text-center py-12">
          <GitBranch className="w-10 h-10 text-text-muted mx-auto mb-3" />
          <p className="text-sm text-text-muted mb-3">No query pipelines yet.</p>
          <button
            onClick={() => setShowCreate(true)}
            className="px-4 py-2 bg-accent-500/10 text-accent-400 text-sm rounded-lg hover:bg-accent-500/20 transition-all"
          >
            Get Started
          </button>
        </div>
      ) : (
        <div className="grid gap-3">
          {pipelines.map((p) => {
            const ds = datastores.find((d) => d.id === p.datastore_id);
            const strategy = p.retriever?.strategy ?? p.retrieval_strategy ?? 'vector';
            return (
              <div
                key={p.id}
                className="bg-surface-800 border border-border-primary rounded-xl p-4 flex items-center gap-4 hover:border-accent-500/30 transition-all"
              >
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-accent-500/20 to-highlight-500/20 flex items-center justify-center shrink-0">
                  <Search className="w-5 h-5 text-accent-400" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-medium text-text-primary">{p.name}</h3>
                    <span className="px-1.5 py-0.5 text-[10px] rounded bg-accent-500/10 text-accent-400">
                      {strategy}
                    </span>
                    <span className="px-1.5 py-0.5 text-[10px] rounded bg-surface-700 text-text-muted">
                      {p.generator?.model ?? 'gpt-4o-mini'}
                    </span>
                  </div>
                  {p.description && (
                    <p className="text-xs text-text-muted mt-0.5 truncate">{p.description}</p>
                  )}
                  <div className="flex items-center gap-3 mt-1.5 text-[10px] text-text-muted">
                    <span className="flex items-center gap-1">
                      <Database className="w-3 h-3" />
                      {ds?.name || (p.datastore_id ? p.datastore_id.slice(0, 8) : 'none')}
                    </span>
                    <span>top_k: {p.retriever?.top_k ?? 5}</span>
                    {p.reranker?.enabled && <span>reranker</span>}
                    {p.planner?.enabled && <span>planner</span>}
                    {p.agent?.enabled && <span>agent</span>}
                    <span>Created {new Date(p.created_at).toLocaleDateString()}</span>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => navigate(`/query-pipelines/${p.id}/edit`)}
                    className="flex items-center gap-1 px-3 py-1.5 bg-surface-700 text-text-secondary text-xs rounded-lg hover:bg-surface-600 hover:text-text-primary transition-all"
                  >
                    <Pencil className="w-3 h-3" />
                    Edit
                  </button>
                  <button
                    onClick={() => openChat(p.id)}
                    className="flex items-center gap-1 px-3 py-1.5 bg-accent-500/10 text-accent-400 text-xs rounded-lg hover:bg-accent-500/20 transition-all"
                  >
                    <MessageSquare className="w-3 h-3" />
                    Chat
                  </button>
                  <button
                    onClick={() => handleDelete(p.id)}
                    className="p-1.5 text-text-muted hover:text-red-400 transition-colors"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
