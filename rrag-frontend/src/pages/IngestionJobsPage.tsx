import { useEffect, useState, useCallback, useRef, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { ingestionApi, streamJobs, type IngestionJob, type IngestionPipeline, type IngestionDocument } from '../api/ingestion';
import { StatusBadge } from '../components/ui/StatusBadge';
import { Plus, PlayCircle, X, XCircle, ChevronRight } from 'lucide-react';

export function IngestionJobsPage() {
  const navigate = useNavigate();
  const [jobs, setJobs] = useState<IngestionJob[]>([]);
  const [pipelines, setPipelines] = useState<IngestionPipeline[]>([]);
  const [documents, setDocuments] = useState<IngestionDocument[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [selectedPipeline, setSelectedPipeline] = useState('');
  const [selectedDocs, setSelectedDocs] = useState<string[]>([]);
  const [error, setError] = useState('');
  const stopStreamRef = useRef<(() => void) | null>(null);

  // Load static data (pipelines, documents) once
  const loadStatic = useCallback(async () => {
    try {
      const [pipeRes, docsRes] = await Promise.all([
        ingestionApi.listPipelines(),
        ingestionApi.listDocuments(),
      ]);
      setPipelines(Array.isArray(pipeRes.data?.pipelines) ? pipeRes.data.pipelines : []);
      setDocuments(Array.isArray(docsRes.data?.documents) ? docsRes.data.documents : []);
    } catch {
      setError('Failed to load pipelines/documents');
    }
  }, []);

  // Load jobs once (non-streaming fallback + initial load)
  const loadJobs = useCallback(async () => {
    try {
      const jobsRes = await ingestionApi.listJobs();
      setJobs(Array.isArray(jobsRes.data?.jobs) ? jobsRes.data.jobs : []);
      setError('');
    } catch {
      setError('Failed to load jobs');
    }
  }, []);

  // Connect SSE stream for real-time job updates
  const connectStream = useCallback(() => {
    stopStreamRef.current?.();
    const stop = streamJobs(
      (updatedJobs) => {
        setJobs(updatedJobs);
        setError('');
      },
      () => {
        // On SSE error, fall back to a single fetch
        loadJobs();
      },
    );
    stopStreamRef.current = stop;
  }, [loadJobs]);

  useEffect(() => {
    loadStatic();
    loadJobs();
  }, [loadStatic, loadJobs]);

  const hasActive = useMemo(
    () => jobs.some((j) => j.status === 'queued' || j.status === 'running'),
    [jobs],
  );

  // Open SSE stream when there are active jobs
  useEffect(() => {
    if (!hasActive) {
      stopStreamRef.current?.();
      stopStreamRef.current = null;
      return;
    }
    // Only connect if not already streaming
    if (!stopStreamRef.current) {
      connectStream();
    }
    return () => {
      stopStreamRef.current?.();
      stopStreamRef.current = null;
    };
  }, [hasActive, connectStream]);

  const handleCreate = async () => {
    if (!selectedPipeline || selectedDocs.length === 0) return;
    try {
      await ingestionApi.createJob({ pipeline_name: selectedPipeline, document_ids: selectedDocs });
      setShowCreate(false);
      setSelectedPipeline('');
      setSelectedDocs([]);
      await loadJobs();
      connectStream();
    } catch {
      setError('Failed to create job');
    }
  };

  const handleCancel = async (id: string) => {
    try {
      await ingestionApi.cancelJob(id);
      await loadJobs();
    } catch {
      setError('Failed to cancel job');
    }
  };

  const toggleDoc = (id: string) => {
    setSelectedDocs((prev) => (prev.includes(id) ? prev.filter((d) => d !== id) : [...prev, id]));
  };

  return (
    <div className="animate-fade-in">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-text-primary">Ingestion Jobs</h1>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-1.5 px-4 py-2 bg-gradient-to-r from-accent-500 to-accent-600 text-white text-sm font-medium rounded-lg hover:from-accent-400 hover:to-accent-500 transition-all"
        >
          <Plus className="w-4 h-4" />
          New Job
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
          <h2 className="font-semibold text-text-primary mb-4">Create Ingestion Job</h2>
          <div className="space-y-3">
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-1">Pipeline</label>
              <select
                value={selectedPipeline}
                onChange={(e) => setSelectedPipeline(e.target.value)}
                className="w-full bg-surface-900 border border-border-primary rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent-500"
              >
                <option value="">Select a pipeline...</option>
                {pipelines.map((p) => (
                  <option key={p.name} value={p.name}>{p.name} ({p.steps} steps)</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-1">Documents</label>
              {documents.length === 0 ? (
                <p className="text-sm text-text-muted">No documents available. Upload documents first.</p>
              ) : (
                <div className="space-y-1 max-h-40 overflow-y-auto bg-surface-900 border border-border-primary rounded-lg p-2">
                  {documents.map((doc) => (
                    <label key={doc.id} className="flex items-center gap-2 text-sm cursor-pointer text-text-secondary hover:text-text-primary py-0.5 px-1 rounded hover:bg-surface-800 transition-colors">
                      <input
                        type="checkbox"
                        checked={selectedDocs.includes(doc.id)}
                        onChange={() => toggleDoc(doc.id)}
                        className="accent-accent-500"
                      />
                      {doc.filename}
                    </label>
                  ))}
                </div>
              )}
            </div>
            <div className="flex gap-2 pt-1">
              <button
                onClick={handleCreate}
                disabled={!selectedPipeline || selectedDocs.length === 0}
                className="flex items-center gap-1.5 px-4 py-2 bg-gradient-to-r from-emerald-600 to-emerald-500 text-white text-sm rounded-lg hover:from-emerald-500 hover:to-emerald-400 disabled:opacity-40 transition-all"
              >
                <PlayCircle className="w-4 h-4" />
                Start Job
              </button>
              <button onClick={() => setShowCreate(false)} className="px-4 py-2 border border-border-primary text-text-secondary text-sm rounded-lg hover:bg-surface-700 transition-colors">
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {jobs.length === 0 ? (
        <div className="text-center py-16 animate-slide-up">
          <PlayCircle className="w-12 h-12 mx-auto text-text-muted mb-4 opacity-40" />
          <p className="text-text-muted">No ingestion jobs yet. Create one to start processing documents.</p>
        </div>
      ) : (
        <div className="bg-surface-800 rounded-xl border border-border-primary overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-surface-900 border-b border-border-primary">
              <tr>
                <th className="text-left px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Job ID</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Pipeline</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Documents</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Status</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Progress</th>
                <th className="text-right px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => (
                <tr
                  key={job.id}
                  className="border-b border-border-primary last:border-0 hover:bg-surface-700/50 transition-colors cursor-pointer"
                  onClick={() => navigate(`/ingestion/jobs/${job.id}`)}
                >
                  <td className="px-4 py-3 font-mono text-xs text-text-muted">{job.id.slice(0, 8)}...</td>
                  <td className="px-4 py-3 text-text-primary">{job.pipeline_name}</td>
                  <td className="px-4 py-3 text-text-muted">{job.document_ids.length} doc(s)</td>
                  <td className="px-4 py-3">
                    <StatusBadge status={job.status} />
                  </td>
                  <td className="px-4 py-3">
                    {job.total_steps > 0 ? (
                      <div>
                        <div className="flex items-center gap-2">
                          <div className="w-24 bg-surface-900 rounded-full h-1.5">
                            <div
                              className="bg-accent-500 h-1.5 rounded-full transition-all duration-500"
                              style={{ width: `${job.progress}%` }}
                            />
                          </div>
                          <span className="text-xs text-text-muted">{job.progress}%</span>
                        </div>
                        {job.sub_progress && (
                          <div className="text-[10px] text-text-muted mt-0.5 truncate max-w-[200px]">
                            {job.sub_progress.message}
                          </div>
                        )}
                      </div>
                    ) : (
                      <span className="text-xs text-text-muted">-</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {(job.status === 'queued' || job.status === 'running') ? (
                      <button
                        onClick={(e) => { e.stopPropagation(); handleCancel(job.id); }}
                        className="inline-flex items-center gap-1 text-red-400 hover:text-red-300 text-sm transition-colors"
                      >
                        <XCircle className="w-3.5 h-3.5" />
                        Cancel
                      </button>
                    ) : (
                      <ChevronRight className="w-4 h-4 text-text-muted inline-block" />
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
