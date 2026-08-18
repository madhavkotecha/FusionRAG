import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { ingestionApi, type DataStore, type IngestionPipeline, type IngestionDocument } from '../api/ingestion';
import { StatusBadge } from '../components/ui/StatusBadge';
import {
  Database,
  HardDrive,
  Share2,
  Archive,
  Trash2,
  MessageSquare,
  Eye,
  X,
  Plus,
  PlayCircle,
  ChevronDown,
  ChevronUp,
  FileText,
  GitBranch,
  AlertCircle,
  Rocket,
} from 'lucide-react';

const TARGET_ICONS: Record<string, typeof Database> = {
  vector: HardDrive,
  graph: Share2,
  metadata: Archive,
};

const TARGET_COLORS: Record<string, string> = {
  vector: 'text-blue-400 bg-blue-500/10',
  graph: 'text-purple-400 bg-purple-500/10',
  metadata: 'text-amber-400 bg-amber-500/10',
};

function statusLabel(status: string) {
  if (status === 'ready') return 'completed';
  if (status === 'empty') return 'draft';
  return status;
}

export function DataStoresPage() {
  const navigate = useNavigate();
  const [datastores, setDatastores] = useState<DataStore[]>([]);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  // Run job modal state
  const [runningDsId, setRunningDsId] = useState<string | null>(null);
  const [pipelines, setPipelines] = useState<IngestionPipeline[]>([]);
  const [documents, setDocuments] = useState<IngestionDocument[]>([]);
  const [selectedPipeline, setSelectedPipeline] = useState('');
  const [selectedDocs, setSelectedDocs] = useState<string[]>([]);
  const [runLoading, setRunLoading] = useState(false);

  const loadDataStores = useCallback(async () => {
    try {
      const { data } = await ingestionApi.listDataStores();
      setDatastores(Array.isArray(data?.datastores) ? data.datastores : []);
      setError('');
    } catch {
      setError('Failed to load datastores');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDataStores();
  }, [loadDataStores]);

  const handleDelete = async (id: string) => {
    try {
      await ingestionApi.deleteDataStore(id);
      setDatastores((prev) => prev.filter((d) => d.id !== id));
    } catch {
      setError('Failed to delete datastore');
    }
  };

  const openRunJob = async (dsId: string) => {
    setRunningDsId(dsId);
    setRunLoading(true);
    try {
      const [pipeRes, docsRes] = await Promise.all([
        ingestionApi.listPipelines(),
        ingestionApi.listDocuments(),
      ]);
      setPipelines(Array.isArray(pipeRes.data?.pipelines) ? pipeRes.data.pipelines : []);
      setDocuments(Array.isArray(docsRes.data?.documents) ? docsRes.data.documents : []);
    } catch {
      setError('Failed to load pipelines/documents');
    } finally {
      setRunLoading(false);
    }
  };

  const closeRunJob = () => {
    setRunningDsId(null);
    setSelectedPipeline('');
    setSelectedDocs([]);
  };

  const handleRunJob = async () => {
    if (!runningDsId || !selectedPipeline || selectedDocs.length === 0) return;
    try {
      const { data } = await ingestionApi.createJob({
        pipeline_name: selectedPipeline,
        document_ids: selectedDocs,
        datastore_id: runningDsId,
      });
      closeRunJob();
      navigate(`/ingestion/jobs/${data.job_id}`);
    } catch {
      setError('Failed to create job');
    }
  };

  const toggleDoc = (id: string) => {
    setSelectedDocs((prev) => (prev.includes(id) ? prev.filter((d) => d !== id) : [...prev, id]));
  };

  const toggleAllDocs = () => {
    if (selectedDocs.length === documents.length) {
      setSelectedDocs([]);
    } else {
      setSelectedDocs(documents.map((d) => d.id));
    }
  };

  const runningDs = runningDsId ? datastores.find((d) => d.id === runningDsId) : null;

  return (
    <div className="animate-fade-in">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-text-primary">Knowledge Stores</h1>
        <button
          onClick={() => navigate('/ingestion/datastores/new')}
          className="flex items-center gap-1.5 px-4 py-2 bg-gradient-to-r from-accent-500 to-accent-600 text-white text-sm font-medium rounded-lg hover:from-accent-400 hover:to-accent-500 transition-all"
        >
          <Plus className="w-4 h-4" />
          New DataStore
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

      {/* Run Job Modal */}
      {runningDsId && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 animate-fade-in">
          <div className="bg-surface-800 rounded-2xl border border-border-primary shadow-2xl max-w-xl w-full mx-4 animate-scale-in">
            <div className="flex items-center justify-between px-6 py-4 border-b border-border-primary">
              <div>
                <h3 className="font-medium text-text-primary">Run Ingestion</h3>
                <p className="text-xs text-text-muted mt-0.5">Into datastore: <span className="text-text-secondary font-medium">{runningDs?.name}</span></p>
              </div>
              <button onClick={closeRunJob} className="text-text-muted hover:text-text-primary transition-colors">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-6 space-y-5">
              {runLoading ? (
                <div className="text-center py-8 text-text-muted text-sm">Loading pipelines and documents...</div>
              ) : (
                <>
                  {/* Pipeline selection */}
                  <div>
                    <label className="flex items-center gap-1.5 text-sm font-medium text-text-secondary mb-2">
                      <GitBranch className="w-3.5 h-3.5" />
                      Pipeline
                    </label>
                    {pipelines.length === 0 ? (
                      <div className="p-3 bg-amber-500/10 border border-amber-500/20 rounded-lg flex items-center gap-2">
                        <AlertCircle className="w-4 h-4 text-amber-400 shrink-0" />
                        <div className="text-sm">
                          <span className="text-amber-400">No pipelines available.</span>
                          <button
                            onClick={() => { closeRunJob(); navigate('/ingestion/pipelines'); }}
                            className="text-accent-400 hover:text-accent-300 ml-1 underline"
                          >
                            Create one first
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="space-y-1.5 max-h-36 overflow-y-auto">
                        {pipelines.map((p) => (
                          <button
                            key={p.name}
                            onClick={() => setSelectedPipeline(p.name)}
                            className={`w-full text-left p-3 rounded-lg border transition-all ${
                              selectedPipeline === p.name
                                ? 'border-accent-500/50 bg-accent-500/5'
                                : 'border-border-primary bg-surface-900 hover:bg-surface-700/50'
                            }`}
                          >
                            <div className="text-sm font-medium text-text-primary">{p.name}</div>
                            <div className="text-xs text-text-muted">{p.steps} steps{p.description ? ` \u2014 ${p.description}` : ''}</div>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Document selection */}
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <label className="flex items-center gap-1.5 text-sm font-medium text-text-secondary">
                        <FileText className="w-3.5 h-3.5" />
                        Documents
                      </label>
                      {documents.length > 0 && (
                        <button onClick={toggleAllDocs} className="text-xs text-accent-400 hover:text-accent-300">
                          {selectedDocs.length === documents.length ? 'Deselect All' : 'Select All'}
                        </button>
                      )}
                    </div>
                    {documents.length === 0 ? (
                      <div className="p-3 bg-amber-500/10 border border-amber-500/20 rounded-lg flex items-center gap-2">
                        <AlertCircle className="w-4 h-4 text-amber-400 shrink-0" />
                        <div className="text-sm">
                          <span className="text-amber-400">No documents uploaded.</span>
                          <button
                            onClick={() => { closeRunJob(); navigate('/ingestion/documents'); }}
                            className="text-accent-400 hover:text-accent-300 ml-1 underline"
                          >
                            Upload documents
                          </button>
                        </div>
                      </div>
                    ) : (
                      <>
                        <div className="text-xs text-text-muted mb-1.5">{selectedDocs.length} of {documents.length} selected</div>
                        <div className="border border-border-primary rounded-lg overflow-hidden max-h-40 overflow-y-auto">
                          {documents.map((doc) => (
                            <label
                              key={doc.id}
                              className={`flex items-center gap-2 text-sm cursor-pointer py-2 px-3 border-b border-border-primary last:border-0 transition-colors ${
                                selectedDocs.includes(doc.id) ? 'bg-accent-500/5' : 'hover:bg-surface-700/50'
                              }`}
                            >
                              <input
                                type="checkbox"
                                checked={selectedDocs.includes(doc.id)}
                                onChange={() => toggleDoc(doc.id)}
                                className="accent-accent-500 w-4 h-4"
                              />
                              <FileText className="w-3.5 h-3.5 text-text-muted shrink-0" />
                              <span className="text-text-primary truncate flex-1">{doc.filename}</span>
                            </label>
                          ))}
                        </div>
                      </>
                    )}
                  </div>

                  {/* Actions */}
                  <div className="flex gap-2 pt-1">
                    <button
                      onClick={handleRunJob}
                      disabled={!selectedPipeline || selectedDocs.length === 0}
                      className="flex-1 flex items-center justify-center gap-1.5 px-4 py-2.5 bg-gradient-to-r from-emerald-600 to-emerald-500 text-white text-sm font-medium rounded-lg hover:from-emerald-500 hover:to-emerald-400 disabled:opacity-40 transition-all"
                    >
                      <PlayCircle className="w-4 h-4" />
                      Start Ingestion
                    </button>
                    <button
                      onClick={closeRunJob}
                      className="px-4 py-2.5 border border-border-primary text-text-secondary text-sm rounded-lg hover:bg-surface-700 transition-colors"
                    >
                      Cancel
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {loading ? (
        <div className="text-text-muted text-center py-12">Loading datastores...</div>
      ) : datastores.length === 0 ? (
        <div className="text-center py-16 animate-slide-up">
          <Database className="w-12 h-12 mx-auto text-text-muted mb-4 opacity-40" />
          <p className="text-text-muted mb-2">No datastores yet.</p>
          <p className="text-text-muted text-sm mb-5">Create one to get started with the guided setup wizard.</p>
          <button
            onClick={() => navigate('/ingestion/datastores/new')}
            className="inline-flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-accent-500 to-accent-600 text-white text-sm font-medium rounded-lg hover:from-accent-400 hover:to-accent-500 transition-all"
          >
            <Rocket className="w-4 h-4" />
            Get Started
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {datastores.map((ds, i) => (
            <div
              key={ds.id}
              className="bg-surface-800 rounded-xl border border-border-primary overflow-hidden animate-slide-up"
              style={{ animationDelay: `${i * 40}ms` }}
            >
              {/* Row header */}
              <div
                className="flex items-center gap-4 px-5 py-4 cursor-pointer hover:bg-surface-700/50 transition-colors"
                onClick={() => setExpandedId(expandedId === ds.id ? null : ds.id)}
              >
                <Database className="w-5 h-5 text-accent-400 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-text-primary truncate">{ds.name}</span>
                    <StatusBadge status={statusLabel(ds.status)} />
                  </div>
                  <div className="text-xs text-text-muted mt-0.5">
                    {ds.pipeline_name ? `Pipeline: ${ds.pipeline_name} \u00b7 ` : ''}
                    {ds.source_document_ids.length > 0 ? `${ds.source_document_ids.length} doc(s) \u00b7 ` : ''}
                    {new Date(ds.created_at).toLocaleDateString()}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {ds.targets.map((t, ti) => {
                    const Icon = TARGET_ICONS[t.type] || Database;
                    const color = TARGET_COLORS[t.type] || 'text-text-muted bg-surface-700';
                    return (
                      <span key={ti} className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs ${color}`}>
                        <Icon className="w-3 h-3" />
                        {t.backend}
                      </span>
                    );
                  })}
                </div>
                {expandedId === ds.id ? (
                  <ChevronUp className="w-4 h-4 text-text-muted flex-shrink-0" />
                ) : (
                  <ChevronDown className="w-4 h-4 text-text-muted flex-shrink-0" />
                )}
              </div>

              {/* Expanded detail */}
              {expandedId === ds.id && (
                <div className="border-t border-border-primary bg-surface-900 px-5 py-4 animate-fade-in">
                  {ds.description && (
                    <p className="text-sm text-text-secondary mb-4">{ds.description}</p>
                  )}

                  {/* Targets grid */}
                  {ds.targets.length > 0 && (
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
                      {ds.targets.map((target, ti) => {
                        const Icon = TARGET_ICONS[target.type] || Database;
                        return (
                          <div key={ti} className="bg-surface-800 rounded-lg border border-border-primary p-3">
                            <div className="flex items-center gap-2 mb-2">
                              <Icon className="w-4 h-4 text-highlight-500" />
                              <span className="text-xs font-medium text-text-primary uppercase tracking-wider">{target.type}</span>
                              <span className="text-xs text-text-muted">({target.backend})</span>
                            </div>
                            {Object.keys(target.config).length > 0 && (
                              <div className="mb-2">
                                <div className="text-xs text-text-muted mb-1">Config</div>
                                {Object.entries(target.config).map(([k, v]) => (
                                  <div key={k} className="flex items-center justify-between text-xs">
                                    <span className="text-text-muted">{k}</span>
                                    <span className="text-text-secondary font-mono truncate ml-2">{String(v)}</span>
                                  </div>
                                ))}
                              </div>
                            )}
                            <div>
                              <div className="text-xs text-text-muted mb-1">Stats</div>
                              {Object.entries(target.stats).map(([k, v]) => (
                                <div key={k} className="flex items-center justify-between text-xs">
                                  <span className="text-text-muted">{k}</span>
                                  <span className="text-text-secondary font-mono">{String(v)}</span>
                                </div>
                              ))}
                              {Object.keys(target.stats).length === 0 && (
                                <span className="text-xs text-text-muted">No stats</span>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}

                  {/* Empty state for unpopulated datastores */}
                  {ds.status === 'empty' && ds.targets.length === 0 && (
                    <div className="mb-4 p-4 bg-surface-800 rounded-lg border border-border-primary text-center">
                      <p className="text-sm text-text-muted mb-2">This datastore is empty. Run an ingestion job to populate it.</p>
                    </div>
                  )}

                  {/* Metadata */}
                  <div className="flex items-center gap-4 text-xs text-text-muted mb-4">
                    {ds.created_by_job_id && (
                      <span>Job: <span className="font-mono">{ds.created_by_job_id.slice(0, 8)}...</span></span>
                    )}
                    <span>Created: {new Date(ds.created_at).toLocaleString()}</span>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-2">
                    {(ds.status === 'empty' || ds.status === 'ready') && (
                      <button
                        onClick={(e) => { e.stopPropagation(); openRunJob(ds.id); }}
                        className="flex items-center gap-1.5 px-3 py-1.5 bg-gradient-to-r from-emerald-600 to-emerald-500 text-white text-xs font-medium rounded-lg hover:from-emerald-500 hover:to-emerald-400 transition-all"
                      >
                        <PlayCircle className="w-3.5 h-3.5" />
                        Run Ingestion
                      </button>
                    )}
                    {ds.status === 'ready' && (
                      <button
                        onClick={() => navigate(`/chat?datastore_id=${ds.id}&datastore_name=${encodeURIComponent(ds.name)}`)}
                        className="flex items-center gap-1.5 px-3 py-1.5 bg-gradient-to-r from-accent-500 to-accent-600 text-white text-xs font-medium rounded-lg hover:from-accent-400 hover:to-accent-500 transition-all"
                      >
                        <MessageSquare className="w-3.5 h-3.5" />
                        Query
                      </button>
                    )}
                    {ds.created_by_job_id && (
                      <button
                        onClick={() => navigate(`/ingestion/jobs/${ds.created_by_job_id}`)}
                        className="flex items-center gap-1.5 px-3 py-1.5 border border-border-primary text-text-secondary text-xs rounded-lg hover:bg-surface-700 transition-colors"
                      >
                        <Eye className="w-3.5 h-3.5" />
                        View Job
                      </button>
                    )}
                    <button
                      onClick={(e) => { e.stopPropagation(); handleDelete(ds.id); }}
                      className="flex items-center gap-1.5 px-3 py-1.5 border border-red-500/20 text-red-400 text-xs rounded-lg hover:bg-red-500/10 transition-colors ml-auto"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                      Delete
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
