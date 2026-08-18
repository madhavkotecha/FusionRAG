import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { pipelineApi, type PipelineTemplate } from '../api/pipelines';
import { useAuthStore } from '../stores/auth.store';
import type { Pipeline } from '../types/pipeline';
import { StatusBadge } from '../components/ui/StatusBadge';
import { CardSkeleton } from '../components/ui/Skeleton';
import { Plus, Pencil, Play, Trash2, GitBranch, X, Layers, Sparkles, Database, Search, Copy, Workflow, AlertTriangle, RefreshCw } from 'lucide-react';

function getErrorMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  return String(err);
}

const TEMPLATE_ICONS: Record<string, typeof Database> = {
  ingestion: Database,
  query: Search,
  full: Workflow,
};

export function DashboardPage() {
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [templates, setTemplates] = useState<PipelineTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [templateError, setTemplateError] = useState<string | null>(null);
  const [pipelineError, setPipelineError] = useState<string | null>(null);
  const [showTemplates, setShowTemplates] = useState(true);
  const [templateFilter, setTemplateFilter] = useState<string | null>(null);
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const workspaceId = user?.workspaces?.[0]?.workspaceId ?? 'default';

  const fetchData = async () => {
    setLoading(true);
    setPipelineError(null);
    setTemplateError(null);

    const [pipeRes, templateRes] = await Promise.allSettled([
      pipelineApi.list(workspaceId),
      pipelineApi.getTemplates(),
    ]);

    if (pipeRes.status === 'fulfilled') {
      setPipelines(Array.isArray(pipeRes.value.data) ? pipeRes.value.data : []);
    } else {
      setPipelineError(`Failed to load pipelines: ${getErrorMessage(pipeRes.reason)}`);
    }

    if (templateRes.status === 'fulfilled') {
      const remote = templateRes.value.data;
      setTemplates(Array.isArray(remote) ? (remote as PipelineTemplate[]) : []);
    } else {
      setTemplateError(`Failed to load templates: ${getErrorMessage(templateRes.reason)}`);
      setTemplates([]);
    }

    setLoading(false);
  };

  useEffect(() => {
    fetchData();
  }, [workspaceId]);

  const handleCreate = async () => {
    setCreating(true);
    setError(null);
    try {
      const suffix = new Date().toISOString().slice(5, 16).replace('T', ' ');
      const { data } = await pipelineApi.create({
        name: `Untitled Pipeline (${suffix})`,
        workspace_id: workspaceId,
      });
      navigate(`/pipelines/${data.id}/edit`);
    } catch (err) {
      setError(`Failed to create pipeline: ${getErrorMessage(err)}`);
    } finally {
      setCreating(false);
    }
  };

  const handleCreateFromTemplate = async (template: PipelineTemplate) => {
    setCreating(true);
    setError(null);
    try {
      const suffix = new Date().toISOString().slice(5, 16).replace('T', ' ');
      const pipelineType = template.category === 'query' ? 'query' : 'ingestion';
      const { data } = await pipelineApi.create({
        name: `${template.name} (${suffix})`,
        description: template.description,
        workspace_id: workspaceId,
        definition: template.definition,
        pipeline_type: pipelineType,
      });
      navigate(`/pipelines/${data.id}/edit`);
    } catch (err) {
      setError(`Failed to create from template: ${getErrorMessage(err)}`);
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm('Are you sure you want to delete this pipeline?')) return;
    setError(null);
    try {
      await pipelineApi.delete(id);
      setPipelines((prev) => prev.filter((p) => p.id !== id));
    } catch (err) {
      setError(`Failed to delete pipeline: ${getErrorMessage(err)}`);
    }
  };

  const handleDuplicate = async (pipeline: Pipeline) => {
    setCreating(true);
    setError(null);
    try {
      // Fetch full pipeline with definition
      const { data: full } = await pipelineApi.get(pipeline.id, workspaceId);
      const definition = full.definition ?? { nodes: [], edges: [] };

      // Remap node IDs so the copy is independent
      const idMap = new Map<string, string>();
      const newNodes = (definition.nodes || []).map((node: Record<string, unknown>) => {
        const oldId = node.id as string;
        const newId = crypto.randomUUID();
        idMap.set(oldId, newId);
        return { ...node, id: newId };
      });
      const newEdges = (definition.edges || []).map((edge: Record<string, unknown>) => ({
        ...edge,
        id: `e-${idMap.get(edge.source as string) ?? edge.source}-${idMap.get(edge.target as string) ?? edge.target}-0`,
        source: idMap.get(edge.source as string) ?? edge.source,
        target: idMap.get(edge.target as string) ?? edge.target,
      }));

      const { data: created } = await pipelineApi.create({
        name: `Copy of ${pipeline.name}`,
        description: pipeline.description ?? undefined,
        workspace_id: workspaceId,
        definition: { nodes: newNodes, edges: newEdges },
      });
      navigate(`/pipelines/${created.id}/edit`);
    } catch (err) {
      setError(`Failed to duplicate pipeline: ${getErrorMessage(err)}`);
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="animate-fade-in">
      {error && (
        <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-sm text-red-400 flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="text-red-500 hover:text-red-300 ml-2">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Templates Section */}
      {templateError && (
        <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-sm text-red-400 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{templateError}</span>
          </div>
          <button onClick={fetchData} className="flex items-center gap-1 text-red-400 hover:text-red-300 ml-2 text-xs font-medium">
            <RefreshCw className="w-3 h-3" /> Retry
          </button>
        </div>
      )}
      {pipelineError && (
        <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-sm text-red-400 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{pipelineError}</span>
          </div>
          <button onClick={fetchData} className="flex items-center gap-1 text-red-400 hover:text-red-300 ml-2 text-xs font-medium">
            <RefreshCw className="w-3 h-3" /> Retry
          </button>
        </div>
      )}
      {templates.length > 0 && (
        <div className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <button
              onClick={() => setShowTemplates(!showTemplates)}
              className="flex items-center gap-2 text-text-secondary hover:text-text-primary transition-colors"
            >
              <Sparkles className="w-4 h-4 text-highlight-500" />
              <span className="text-base font-bold text-text-primary">Pipeline Templates</span>
              <span className="text-xs text-text-muted">({templates.length})</span>
              <span className="text-xs text-text-muted ml-1">{showTemplates ? '▾' : '▸'}</span>
            </button>
            {showTemplates && (
              <div className="flex gap-1.5">
                {[
                  { key: null, label: 'All' },
                  { key: 'full', label: 'End-to-End' },
                  { key: 'ingestion', label: 'Ingestion' },
                  { key: 'query', label: 'Query' },
                ].map((f) => (
                  <button
                    key={f.key ?? 'all'}
                    onClick={() => setTemplateFilter(f.key)}
                    className={`text-xs px-2.5 py-1 rounded-lg font-medium transition-colors ${
                      templateFilter === f.key
                        ? 'bg-accent-500/20 text-accent-400 border border-accent-500/30'
                        : 'bg-surface-800 text-text-muted border border-border-primary hover:text-text-secondary hover:bg-surface-700'
                    }`}
                  >
                    {f.label}
                  </button>
                ))}
              </div>
            )}
          </div>
          {showTemplates && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 animate-slide-up">
              {templates
                .filter((t) => !templateFilter || t.category === templateFilter)
                .map((t, i) => {
                  const Icon = TEMPLATE_ICONS[t.category] || Layers;
                  const categoryColors: Record<string, string> = {
                    full: 'from-violet-500/20 to-fuchsia-500/20 group-hover:from-violet-500/30 group-hover:to-fuchsia-500/30',
                    ingestion: 'from-accent-500/20 to-highlight-500/20 group-hover:from-accent-500/30 group-hover:to-highlight-500/30',
                    query: 'from-emerald-500/20 to-cyan-500/20 group-hover:from-emerald-500/30 group-hover:to-cyan-500/30',
                  };
                  const categoryBadgeColors: Record<string, string> = {
                    full: 'bg-violet-500/10 text-violet-400 border-violet-500/20',
                    ingestion: 'bg-accent-500/10 text-accent-400 border-accent-500/20',
                    query: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
                  };
                  const categoryLabels: Record<string, string> = {
                    full: 'end-to-end',
                    ingestion: 'ingestion',
                    query: 'query',
                  };
                  const iconColors: Record<string, string> = {
                    full: 'text-violet-400',
                    ingestion: 'text-accent-400',
                    query: 'text-emerald-400',
                  };
                  return (
                    <button
                      key={t.id}
                      onClick={() => handleCreateFromTemplate(t)}
                      disabled={creating}
                      className="text-left p-4 bg-surface-800/50 border border-border-primary rounded-xl hover:border-accent-500/30 hover:bg-surface-800 transition-all group animate-slide-up"
                      style={{ animationDelay: `${i * 40}ms` }}
                    >
                      <div className="flex items-start gap-3">
                        <div className={`w-8 h-8 rounded-lg bg-gradient-to-br ${categoryColors[t.category] || categoryColors.ingestion} flex items-center justify-center shrink-0 transition-all`}>
                          <Icon className={`w-4 h-4 ${iconColors[t.category] || 'text-accent-400'}`} />
                        </div>
                        <div className="min-w-0">
                          <h4 className="text-sm font-medium text-text-primary group-hover:text-accent-400 transition-colors">
                            {t.name}
                          </h4>
                          <p className="text-xs text-text-muted mt-0.5 line-clamp-2">
                            {t.description}
                          </p>
                          <span className={`inline-block mt-1.5 text-[10px] px-1.5 py-0.5 rounded border ${categoryBadgeColors[t.category] || 'bg-surface-700 text-text-muted'} uppercase tracking-wider`}>
                            {categoryLabels[t.category] || t.category}
                          </span>
                        </div>
                      </div>
                    </button>
                  );
                })}
            </div>
          )}
        </div>
      )}

      {/* Pipelines Section */}
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-bold text-text-primary">Pipelines</h2>
        <button
          onClick={handleCreate}
          disabled={creating}
          className="flex items-center gap-1.5 bg-gradient-to-r from-accent-500 to-accent-600 text-white text-sm py-2 px-4 rounded-lg hover:from-accent-400 hover:to-accent-500 disabled:opacity-50 transition-all"
        >
          <Plus className="w-4 h-4" />
          {creating ? 'Creating...' : 'New Pipeline'}
        </button>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => <CardSkeleton key={i} />)}
        </div>
      ) : pipelines.length === 0 ? (
        <div className="text-center py-16 animate-slide-up">
          <GitBranch className="w-12 h-12 mx-auto text-text-muted mb-4 opacity-40" />
          <p className="text-text-muted mb-4">No pipelines yet.</p>
          <button
            onClick={handleCreate}
            className="inline-flex items-center gap-1.5 bg-gradient-to-r from-accent-500 to-accent-600 text-white text-sm py-2 px-4 rounded-lg hover:from-accent-400 hover:to-accent-500 transition-all"
          >
            <Plus className="w-4 h-4" />
            Create your first pipeline
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {pipelines.map((pipeline, i) => (
            <div
              key={pipeline.id}
              className="bg-surface-800 rounded-xl border border-border-primary p-5 hover:border-border-hover transition-all duration-200 animate-slide-up group"
              style={{ animationDelay: `${i * 50}ms` }}
            >
              <div className="flex items-start justify-between mb-2">
                <h3 className="font-medium text-text-primary truncate">
                  {pipeline.name}
                </h3>
                <StatusBadge status={pipeline.status} />
              </div>
              {pipeline.description && (
                <p className="text-sm text-text-muted mb-3 line-clamp-2">
                  {pipeline.description}
                </p>
              )}
              <div className="text-xs text-text-muted mb-4">
                Updated {new Date(pipeline.updatedAt).toLocaleDateString()}
              </div>
              <div className="flex gap-2">
                <Link
                  to={`/pipelines/${pipeline.id}/edit`}
                  className="flex-1 flex items-center justify-center gap-1 bg-accent-500/10 text-accent-400 text-xs py-1.5 rounded-lg hover:bg-accent-500/20 font-medium transition-colors"
                >
                  <Pencil className="w-3 h-3" />
                  Edit
                </Link>
                <button
                  onClick={() => handleDuplicate(pipeline)}
                  disabled={creating}
                  className="flex-1 flex items-center justify-center gap-1 bg-highlight-500/10 text-highlight-400 text-xs py-1.5 rounded-lg hover:bg-highlight-500/20 font-medium transition-colors disabled:opacity-40"
                  title="Duplicate pipeline"
                >
                  <Copy className="w-3 h-3" />
                  Copy
                </button>
                <Link
                  to={`/pipelines/${pipeline.id}/runs`}
                  className="flex items-center justify-center gap-1 bg-surface-700 text-text-secondary text-xs py-1.5 px-3 rounded-lg hover:bg-surface-600 font-medium transition-colors"
                >
                  <Play className="w-3 h-3" />
                </Link>
                <button
                  onClick={() => handleDelete(pipeline.id)}
                  className="flex items-center justify-center bg-red-500/10 text-red-400 text-xs py-1.5 px-3 rounded-lg hover:bg-red-500/20 transition-colors"
                >
                  <Trash2 className="w-3 h-3" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
