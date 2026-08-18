import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ingestionApi, type IngestionPipeline, type IngestionPipelineDetail, type IngestionComponent } from '../api/ingestion';
import { pipelineApi } from '../api/pipelines';
import { useAuthStore } from '../stores/auth.store';
import { Plus, CheckCircle, XCircle, Trash2, ShieldCheck, GitBranch, X, ExternalLink } from 'lucide-react';

// Map ingestion component types to visual builder categories
const COMPONENT_CATEGORY_MAP: Record<string, string> = {
  loader: 'parser', file_loader: 'parser', pdf_parser: 'parser', multi_parser: 'parser',
  chunker: 'chunker', recursive_chunker: 'chunker', token_chunker: 'chunker', semantic_chunker: 'chunker',
  embedder: 'embedder', openai_embedder: 'embedder',
  indexer: 'indexer', faiss_indexer: 'indexer',
  extractor: 'extractor', entity_extractor: 'extractor', subquery_decomposer: 'extractor',
  retriever: 'retriever', dense_retriever: 'retriever',
  reranker: 'reranker', cross_encoder_reranker: 'reranker',
  generator: 'generator', llm_generator: 'generator',
  graph_builder: 'graph_builder', storage: 'storage',
  router: 'agent', reflection: 'agent', memory: 'agent', orchestrator: 'agent',
  planner: 'planner',
};

function inferCategory(componentName: string): string {
  // Exact match
  if (COMPONENT_CATEGORY_MAP[componentName]) return COMPONENT_CATEGORY_MAP[componentName];
  // Strip dotted prefix (e.g. "agent.router" → "router", "corag.dense_retriever" → "dense_retriever")
  const baseName = componentName.includes('.') ? componentName.split('.').pop()! : componentName;
  if (COMPONENT_CATEGORY_MAP[baseName]) return COMPONENT_CATEGORY_MAP[baseName];
  // Try to match suffix in the base name
  for (const [key, cat] of Object.entries(COMPONENT_CATEGORY_MAP)) {
    if (baseName.includes(key)) return cat;
  }
  return 'parser'; // default fallback
}

export function IngestionPipelinesPage() {
  const [pipelines, setPipelines] = useState<IngestionPipeline[]>([]);
  const [components, setComponents] = useState<IngestionComponent[]>([]);
  const [selected, setSelected] = useState<IngestionPipelineDetail | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [steps, setSteps] = useState<{ component: string; config: Record<string, unknown> }[]>([]);
  const [error, setError] = useState('');
  const [validation, setValidation] = useState<{ valid: boolean; errors: string[] } | null>(null);
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const workspaceId = user?.workspaces?.[0]?.workspaceId ?? 'default';

  const load = async () => {
    try {
      const [pipeRes, compRes] = await Promise.all([
        ingestionApi.listPipelines(),
        ingestionApi.listComponents(),
      ]);
      setPipelines(Array.isArray(pipeRes.data?.pipelines) ? pipeRes.data.pipelines : []);
      setComponents(Array.isArray(compRes.data?.components) ? compRes.data.components : []);
    } catch {
      setError('Failed to load data');
    }
  };

  useEffect(() => { load(); }, []);

  const handleView = async (pName: string) => {
    try {
      const { data } = await ingestionApi.getPipeline(pName);
      setSelected(data);
      setValidation(null);
    } catch {
      setError('Failed to load pipeline');
    }
  };

  const handleDelete = async (pName: string) => {
    try {
      await ingestionApi.deletePipeline(pName);
      setSelected(null);
      await load();
    } catch {
      setError('Failed to delete pipeline');
    }
  };

  const handleValidate = async (pName: string) => {
    try {
      const { data } = await ingestionApi.validatePipeline(pName);
      setValidation(data);
    } catch {
      setError('Failed to validate pipeline');
    }
  };

  const handleOpenInVisualBuilder = async (detail: IngestionPipelineDetail) => {
    try {
      // Convert sequential steps → visual builder nodes + edges
      const nodes = detail.steps.map((step, i) => {
        const category = inferCategory(step.component);
        return {
          id: crypto.randomUUID(),
          type: category,
          position: { x: 100 + i * 250, y: 200 },
          data: {
            label: step.component.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase()),
            componentType: step.component,
            category,
            config: step.config || {},
          },
        };
      });
      const edges = nodes.slice(0, -1).map((node, i) => ({
        id: `e-${node.id}-${nodes[i + 1].id}-0`,
        source: node.id,
        target: nodes[i + 1].id,
      }));

      const timestamp = new Date().toISOString().slice(0, 19).replace('T', ' ');
      const { data: created } = await pipelineApi.create({
        name: `${detail.name} (Visual ${timestamp})`,
        description: detail.description || undefined,
        workspace_id: workspaceId,
        definition: { nodes, edges },
      });
      navigate(`/pipelines/${created.id}/edit`);
    } catch (err) {
      setError(`Failed to open in visual builder: ${err instanceof Error ? err.message : String(err)}`);
    }
  };

  const addStep = () => setSteps([...steps, { component: '', config: {} }]);
  const removeStep = (i: number) => setSteps(steps.filter((_, idx) => idx !== i));
  const updateStep = (i: number, component: string) => {
    const newSteps = [...steps];
    newSteps[i] = { ...newSteps[i], component };
    setSteps(newSteps);
  };

  const handleCreate = async () => {
    if (!name || steps.length === 0) return;
    try {
      await ingestionApi.createPipeline({ name, description, steps });
      setShowCreate(false);
      setName('');
      setDescription('');
      setSteps([]);
      await load();
    } catch {
      setError('Failed to create pipeline');
    }
  };

  return (
    <div className="animate-fade-in">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-text-primary">Ingestion Pipelines</h1>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-1.5 px-4 py-2 bg-gradient-to-r from-accent-500 to-accent-600 text-white text-sm font-medium rounded-lg hover:from-accent-400 hover:to-accent-500 transition-all"
        >
          <Plus className="w-4 h-4" />
          New Pipeline
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

      {showCreate && (
        <div className="mb-6 bg-surface-800 border border-border-primary rounded-xl p-5 animate-scale-in">
          <h2 className="font-semibold text-text-primary mb-4">Create Ingestion Pipeline</h2>
          <div className="space-y-3">
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-1">Name</label>
              <input value={name} onChange={(e) => setName(e.target.value)} className="w-full bg-surface-900 border border-border-primary rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent-500" placeholder="my_pipeline" />
            </div>
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-1">Description</label>
              <input value={description} onChange={(e) => setDescription(e.target.value)} className="w-full bg-surface-900 border border-border-primary rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent-500" />
            </div>
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="block text-sm font-medium text-text-secondary">Steps</label>
                <button onClick={addStep} className="text-accent-400 text-sm hover:text-accent-300 flex items-center gap-1">
                  <Plus className="w-3 h-3" /> Add Step
                </button>
              </div>
              {steps.map((step, i) => (
                <div key={i} className="flex items-center gap-2 mb-2">
                  <span className="text-xs text-text-muted w-6 text-center">{i + 1}.</span>
                  <select
                    value={step.component}
                    onChange={(e) => updateStep(i, e.target.value)}
                    className="flex-1 bg-surface-900 border border-border-primary rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent-500"
                  >
                    <option value="">Select component...</option>
                    {components.map((c) => (
                      <option key={c.name} value={c.name}>{c.name} ({c.type})</option>
                    ))}
                  </select>
                  <button onClick={() => removeStep(i)} className="text-red-400 text-sm hover:text-red-300">Remove</button>
                </div>
              ))}
            </div>
            <div className="flex gap-2 pt-1">
              <button onClick={handleCreate} disabled={!name || steps.length === 0 || steps.some((s) => !s.component)} className="px-4 py-2 bg-gradient-to-r from-accent-500 to-accent-600 text-white text-sm rounded-lg hover:from-accent-400 hover:to-accent-500 disabled:opacity-40 transition-all">
                Create
              </button>
              <button onClick={() => { setShowCreate(false); setSteps([]); }} className="px-4 py-2 border border-border-primary text-text-secondary text-sm rounded-lg hover:bg-surface-700 transition-colors">
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-1">
          {pipelines.length === 0 ? (
            <div className="text-center py-10">
              <GitBranch className="w-8 h-8 mx-auto text-text-muted mb-2 opacity-40" />
              <p className="text-text-muted text-sm">No pipelines defined yet.</p>
            </div>
          ) : (
            <div className="space-y-2">
              {pipelines.map((p) => (
                <button
                  key={p.name}
                  onClick={() => handleView(p.name)}
                  className={`w-full text-left p-3 rounded-xl border transition-all ${
                    selected?.name === p.name
                      ? 'border-accent-500/50 bg-accent-500/5'
                      : 'border-border-primary bg-surface-800 hover:bg-surface-700'
                  }`}
                >
                  <div className="font-medium text-sm text-text-primary">{p.name}</div>
                  <div className="text-xs text-text-muted mt-0.5">{p.steps} steps — {p.description || 'No description'}</div>
                </button>
              ))}
            </div>
          )}
        </div>
        <div className="col-span-2">
          {selected ? (
            <div className="bg-surface-800 border border-border-primary rounded-xl p-5 animate-fade-in">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="text-lg font-semibold text-text-primary">{selected.name}</h2>
                  <p className="text-sm text-text-muted">{selected.description || 'No description'}</p>
                </div>
                <div className="flex gap-2">
                  <button onClick={() => handleOpenInVisualBuilder(selected)} className="flex items-center gap-1.5 px-3 py-1.5 bg-accent-500/10 text-accent-400 text-sm rounded-lg hover:bg-accent-500/20 font-medium transition-colors">
                    <ExternalLink className="w-3.5 h-3.5" />
                    Open in Visual Builder
                  </button>
                  <button onClick={() => handleValidate(selected.name)} className="flex items-center gap-1.5 px-3 py-1.5 border border-border-primary text-text-secondary text-sm rounded-lg hover:bg-surface-700 transition-colors">
                    <ShieldCheck className="w-3.5 h-3.5" />
                    Validate
                  </button>
                  <button onClick={() => handleDelete(selected.name)} className="flex items-center gap-1.5 px-3 py-1.5 border border-red-500/20 text-red-400 text-sm rounded-lg hover:bg-red-500/10 transition-colors">
                    <Trash2 className="w-3.5 h-3.5" />
                    Delete
                  </button>
                </div>
              </div>
              {validation && (
                <div className={`mb-4 p-3 rounded-xl text-sm flex items-center gap-2 ${validation.valid ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-red-500/10 text-red-400 border border-red-500/20'}`}>
                  {validation.valid ? <CheckCircle className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
                  {validation.valid ? 'Pipeline is valid.' : `Validation errors: ${validation.errors.join(', ')}`}
                </div>
              )}
              <h3 className="text-xs font-medium text-text-muted uppercase tracking-wider mb-3">Steps</h3>
              <div className="space-y-2">
                {selected.steps.map((step, i) => (
                  <div key={i} className="flex items-center gap-3 p-3 bg-surface-900 rounded-lg border border-border-primary">
                    <div className="w-6 h-6 flex items-center justify-center bg-accent-500/10 text-accent-400 rounded-full text-xs font-bold shrink-0">
                      {i + 1}
                    </div>
                    <div className="min-w-0">
                      <div className="text-sm font-medium text-text-primary">{step.component}</div>
                      {Object.keys(step.config).length > 0 && (
                        <div className="text-xs text-text-muted font-mono mt-0.5 truncate">{JSON.stringify(step.config)}</div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="text-center py-16 text-text-muted">Select a pipeline to view details</div>
          )}
        </div>
      </div>
    </div>
  );
}
