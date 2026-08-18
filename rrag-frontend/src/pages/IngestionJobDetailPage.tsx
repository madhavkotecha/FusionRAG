import { useEffect, useState, useCallback, useRef } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { ingestionApi, streamJob, type IngestionJob, type DataStore } from '../api/ingestion';
import { StatusBadge } from '../components/ui/StatusBadge';
import {
  ArrowLeft,
  Clock,
  FileText,
  Layers,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  MessageSquare,
  RefreshCw,
  GitBranch,
  Database,
  HardDrive,
  Share2,
  Archive,
  Loader2,
  Circle,
} from 'lucide-react';

function formatDuration(ms: number | null | undefined): string {
  if (!ms) return '-';
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return '-';
  return new Date(iso).toLocaleString();
}

const TARGET_ICONS: Record<string, typeof Database> = {
  vector: HardDrive,
  graph: Share2,
  metadata: Archive,
};

export function IngestionJobDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [job, setJob] = useState<IngestionJob | null>(null);
  const [datastore, setDatastore] = useState<DataStore | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const stopStreamRef = useRef<(() => void) | null>(null);

  // Fetch datastore when job has one
  const fetchDatastore = useCallback(async (datastoreId: string) => {
    try {
      const dsRes = await ingestionApi.getDataStore(datastoreId);
      setDatastore(dsRes.data);
    } catch { /* datastore may not exist yet */ }
  }, []);

  // Initial load: fetch job, then open SSE if active
  useEffect(() => {
    if (!id) return;

    let cancelled = false;

    (async () => {
      try {
        const { data } = await ingestionApi.getJob(id);
        if (cancelled) return;
        setJob(data);
        if (data.datastore_id) fetchDatastore(data.datastore_id);
        setError('');

        // If the job is still active, open SSE stream for live updates
        if (data.status === 'queued' || data.status === 'running') {
          stopStreamRef.current?.();
          stopStreamRef.current = streamJob(
            id,
            (updatedJob) => {
              setJob(updatedJob);
              if (updatedJob.datastore_id) fetchDatastore(updatedJob.datastore_id);
            },
            () => {
              // Stream ended (job completed/failed) — do a final fetch for datastore
              ingestionApi.getJob(id).then(({ data: final }) => {
                setJob(final);
                if (final.datastore_id) fetchDatastore(final.datastore_id);
              }).catch(() => {});
            },
            () => setError('Live updates disconnected'),
          );
        }
      } catch {
        if (!cancelled) setError('Failed to load job details');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
      stopStreamRef.current?.();
      stopStreamRef.current = null;
    };
  }, [id, fetchDatastore]);

  const handleRerun = async () => {
    if (!job) return;
    try {
      await ingestionApi.createJob({
        pipeline_name: job.pipeline_name,
        document_ids: job.document_ids,
      });
      navigate('/ingestion/jobs');
    } catch {
      setError('Failed to re-run job');
    }
  };

  if (loading) {
    return <div className="text-text-muted text-center py-12 animate-fade-in">Loading job details...</div>;
  }

  if (error || !job) {
    return (
      <div className="animate-fade-in">
        <div className="flex items-center gap-3 mb-6">
          <Link to="/ingestion/jobs" className="flex items-center gap-1 text-accent-400 hover:text-accent-300 text-sm transition-colors">
            <ArrowLeft className="w-4 h-4" />
            Back to Jobs
          </Link>
        </div>
        <div className="text-center py-16">
          <AlertTriangle className="w-10 h-10 mx-auto text-red-400 mb-3" />
          <p className="text-red-400">{error || 'Job not found'}</p>
        </div>
      </div>
    );
  }

  const completedSteps = job.step_results?.filter((s) => s.status === 'ok').length ?? 0;
  const errorCount = job.step_results?.filter((s) => s.status === 'error').length ?? 0;

  return (
    <div className="animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Link to="/ingestion/jobs" className="flex items-center gap-1 text-accent-400 hover:text-accent-300 text-sm transition-colors">
            <ArrowLeft className="w-4 h-4" />
            Back to Jobs
          </Link>
          <h1 className="text-xl font-bold text-text-primary">
            Job <span className="font-mono text-text-muted">{job.id.slice(0, 8)}</span>
          </h1>
          <StatusBadge status={job.status} />
        </div>
        <div className="flex items-center gap-2">
          {(job.status === 'running' || job.status === 'queued') && (
            <span className="flex items-center gap-1.5 text-xs text-emerald-400">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              Live
            </span>
          )}
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <div className="bg-surface-800 rounded-xl border border-border-primary p-4">
          <div className="flex items-center gap-2 text-text-muted text-xs mb-1">
            <Clock className="w-3.5 h-3.5" />
            Duration
          </div>
          <div className="text-lg font-semibold text-text-primary">{formatDuration(job.total_duration_ms)}</div>
        </div>
        <div className="bg-surface-800 rounded-xl border border-border-primary p-4">
          <div className="flex items-center gap-2 text-text-muted text-xs mb-1">
            <FileText className="w-3.5 h-3.5" />
            Documents
          </div>
          <div className="text-lg font-semibold text-text-primary">{job.document_ids.length}</div>
        </div>
        <div className="bg-surface-800 rounded-xl border border-border-primary p-4">
          <div className="flex items-center gap-2 text-text-muted text-xs mb-1">
            <Layers className="w-3.5 h-3.5" />
            Steps
          </div>
          <div className="text-lg font-semibold text-text-primary">
            {completedSteps + errorCount}/{job.total_steps || '-'}
          </div>
        </div>
        <div className="bg-surface-800 rounded-xl border border-border-primary p-4">
          <div className="flex items-center gap-2 text-text-muted text-xs mb-1">
            <AlertTriangle className="w-3.5 h-3.5" />
            Errors
          </div>
          <div className={`text-lg font-semibold ${errorCount > 0 ? 'text-red-400' : 'text-emerald-400'}`}>
            {errorCount}
          </div>
        </div>
      </div>

      {/* Progress bar for running jobs */}
      {(job.status === 'running' || job.status === 'queued') && (
        <div className="mb-6 bg-surface-800 rounded-xl border border-border-primary p-4">
          <div className="flex items-center justify-between text-sm mb-2">
            <span className="text-text-secondary">
              {job.current_step ? `Running: ${job.current_step}` : 'Waiting...'}
            </span>
            <span className="text-text-muted">{job.progress}%</span>
          </div>
          <div className="w-full bg-surface-900 rounded-full h-2">
            <div
              className="bg-accent-500 h-2 rounded-full transition-all duration-500"
              style={{ width: `${job.progress}%` }}
            />
          </div>
        </div>
      )}

      {/* Step Execution Timeline */}
      <div className="mb-6">
        <h2 className="text-base font-bold text-text-primary mb-3">Step Execution</h2>
        {(() => {
          // Build the full step list from pipeline_steps (all steps) + step_results (completed)
          const steps = job.pipeline_steps ?? [];
          const completedMap = new Map(
            (job.step_results ?? []).map((sr) => [sr.step_index, sr]),
          );
          const isActive = job.status === 'running' || job.status === 'queued';

          if (steps.length === 0 && (!job.step_results || job.step_results.length === 0)) {
            return (
              <div className="bg-surface-800 rounded-xl border border-border-primary p-6 text-center text-text-muted text-sm">
                {job.status === 'queued' ? 'Waiting to start...' : 'No step data available'}
              </div>
            );
          }

          // If pipeline_steps not available (old jobs), fall back to step_results only
          const timeline = steps.length > 0
            ? steps.map((component, i) => ({
                stepIndex: i + 1,
                component,
                result: completedMap.get(i + 1) ?? null,
              }))
            : (job.step_results ?? []).map((sr) => ({
                stepIndex: sr.step_index,
                component: sr.component,
                result: sr,
              }));

          return (
            <div className="space-y-2">
              {timeline.map(({ stepIndex, component, result }, i) => {
                const isRunning = isActive && !result && job.current_step === component;
                const isPending = isActive && !result && job.current_step !== component;
                const isCompleted = result?.status === 'ok';
                const isFailed = result?.status === 'error';

                return (
                  <div
                    key={i}
                    className={`bg-surface-800 rounded-xl border p-4 animate-slide-up ${
                      isRunning ? 'border-accent-500/40' :
                      isPending ? 'border-border-primary opacity-60' :
                      isFailed ? 'border-red-500/30' :
                      'border-border-primary'
                    }`}
                    style={{ animationDelay: `${i * 40}ms` }}
                  >
                    <div className="flex items-center gap-3">
                      <div className={`w-7 h-7 flex items-center justify-center rounded-full text-xs font-bold ${
                        isCompleted ? 'bg-emerald-500/10 text-emerald-400' :
                        isFailed ? 'bg-red-500/10 text-red-400' :
                        isRunning ? 'bg-accent-500/10 text-accent-400' :
                        'bg-surface-700 text-text-muted'
                      }`}>
                        {isCompleted ? (
                          <CheckCircle2 className="w-4 h-4" />
                        ) : isFailed ? (
                          <XCircle className="w-4 h-4" />
                        ) : isRunning ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <Circle className="w-4 h-4" />
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className={`text-sm font-medium truncate ${isPending ? 'text-text-muted' : 'text-text-primary'}`}>
                            {component}
                          </span>
                          <span className="text-xs text-text-muted">Step {stepIndex}</span>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        {result && (
                          <span className="text-xs text-text-muted font-mono">{formatDuration(result.duration_ms)}</span>
                        )}
                        {isCompleted && <StatusBadge status="completed" />}
                        {isFailed && <StatusBadge status="failed" />}
                        {isRunning && <StatusBadge status="running" />}
                        {isPending && (
                          <span className="text-[10px] text-text-muted uppercase tracking-wider">Pending</span>
                        )}
                      </div>
                    </div>

                    {/* Sub-progress for the running step */}
                    {isRunning && job.sub_progress && (
                      <div className="mt-2 ml-10">
                        <div className="flex items-center justify-between text-xs mb-1">
                          <span className="text-accent-400">{job.sub_progress.message}</span>
                          {job.sub_progress.items_total > 0 && (
                            <span className="text-text-muted font-mono">
                              {job.sub_progress.items_done}/{job.sub_progress.items_total}
                            </span>
                          )}
                        </div>
                        {job.sub_progress.items_total > 0 && (
                          <div className="w-full bg-surface-900 rounded-full h-1.5">
                            <div
                              className="bg-accent-500/50 h-1.5 rounded-full transition-all duration-300"
                              style={{ width: `${Math.round((job.sub_progress.items_done / job.sub_progress.items_total) * 100)}%` }}
                            />
                          </div>
                        )}
                      </div>
                    )}

                    {/* Output summary metrics */}
                    {result?.output_summary && Object.keys(result.output_summary).length > 0 && (
                      <div className="mt-2 ml-10 flex flex-wrap gap-2">
                        {Object.entries(result.output_summary).map(([key, value]) => (
                          <span
                            key={key}
                            className="inline-flex items-center px-2 py-0.5 rounded-full text-xs bg-accent-500/10 text-accent-400 ring-1 ring-accent-500/20"
                          >
                            {key}: {String(value)}
                          </span>
                        ))}
                      </div>
                    )}

                    {/* Step error */}
                    {result?.error && (
                      <div className="mt-2 ml-10">
                        <pre className="text-xs text-red-400 bg-red-500/5 border border-red-500/10 p-2 rounded-lg overflow-auto">
                          {result.error}
                        </pre>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          );
        })()}
      </div>

      {/* DataStore Section */}
      {datastore && (
        <div className="mb-6">
          <h2 className="text-base font-bold text-text-primary mb-3">DataStore Created</h2>
          <div className="bg-surface-800 rounded-xl border border-border-primary p-5">
            <div className="flex items-center gap-3 mb-3">
              <Database className="w-5 h-5 text-accent-400" />
              <span className="text-sm font-medium text-text-primary">{datastore.name}</span>
              <StatusBadge status={datastore.status === 'ready' ? 'completed' : datastore.status} />
            </div>
            {datastore.targets.length > 0 && (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {datastore.targets.map((target, i) => {
                  const Icon = TARGET_ICONS[target.type] || Database;
                  return (
                    <div key={i} className="bg-surface-900 rounded-lg border border-border-primary p-3">
                      <div className="flex items-center gap-2 mb-2">
                        <Icon className="w-4 h-4 text-highlight-500" />
                        <span className="text-xs font-medium text-text-primary uppercase tracking-wider">
                          {target.type}
                        </span>
                        <span className="text-xs text-text-muted">({target.backend})</span>
                      </div>
                      <div className="space-y-1">
                        {Object.entries(target.stats).map(([key, value]) => (
                          <div key={key} className="flex items-center justify-between text-xs">
                            <span className="text-text-muted">{key}</span>
                            <span className="text-text-secondary font-mono">{String(value)}</span>
                          </div>
                        ))}
                        {Object.keys(target.stats).length === 0 && (
                          <span className="text-xs text-text-muted">No stats available</span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Timestamps */}
      <div className="mb-6">
        <h2 className="text-base font-bold text-text-primary mb-3">Timeline</h2>
        <div className="bg-surface-800 rounded-xl border border-border-primary p-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
            <div>
              <div className="text-xs text-text-muted mb-1">Created</div>
              <div className="text-text-secondary">{formatDate(job.created_at)}</div>
            </div>
            <div>
              <div className="text-xs text-text-muted mb-1">Started</div>
              <div className="text-text-secondary">{formatDate(job.started_at)}</div>
            </div>
            <div>
              <div className="text-xs text-text-muted mb-1">Completed</div>
              <div className="text-text-secondary">{formatDate(job.completed_at)}</div>
            </div>
          </div>
        </div>
      </div>

      {/* Job-level Errors */}
      {job.errors.length > 0 && (
        <div className="mb-6">
          <h2 className="text-base font-bold text-red-400 mb-3">Errors</h2>
          <div className="space-y-2">
            {job.errors.map((err, i) => (
              <pre key={i} className="text-xs text-red-400 bg-red-500/5 border border-red-500/10 p-3 rounded-lg overflow-auto">
                {err}
              </pre>
            ))}
          </div>
        </div>
      )}

      {/* Action Buttons */}
      {(job.status === 'completed' || job.status === 'failed') && (
        <div className="flex items-center gap-3">
          <button
            onClick={() => {
              const params = new URLSearchParams();
              if (datastore) {
                params.set('datastore_id', datastore.id);
                params.set('datastore_name', datastore.name);
              }
              navigate(`/chat${params.toString() ? '?' + params.toString() : ''}`);
            }}
            className="flex items-center gap-1.5 px-4 py-2 bg-gradient-to-r from-accent-500 to-accent-600 text-white text-sm font-medium rounded-lg hover:from-accent-400 hover:to-accent-500 transition-all"
          >
            <MessageSquare className="w-4 h-4" />
            Query Documents
          </button>
          {(job.status === 'failed' || (job.errors && job.errors.length > 0) ||
            job.step_results?.some((r) => r.status === 'error')) && (
            <button
              onClick={async () => {
                try {
                  setError('');
                  await ingestionApi.resumeJob(job.id);
                  navigate(0);
                } catch (err) {
                  setError(`Failed to resume: ${err instanceof Error ? err.message : 'Unknown error'}`);
                }
              }}
              className="flex items-center gap-1.5 px-4 py-2 bg-gradient-to-r from-amber-600 to-amber-500 text-white text-sm font-medium rounded-lg hover:from-amber-500 hover:to-amber-400 transition-all"
            >
              <RefreshCw className="w-4 h-4" />
              Retry Failed Steps
            </button>
          )}
          <button
            onClick={handleRerun}
            className="flex items-center gap-1.5 px-4 py-2 bg-gradient-to-r from-emerald-600 to-emerald-500 text-white text-sm font-medium rounded-lg hover:from-emerald-500 hover:to-emerald-400 transition-all"
          >
            <RefreshCw className="w-4 h-4" />
            Re-run
          </button>
          <button
            onClick={() => navigate('/ingestion/pipelines')}
            className="flex items-center gap-1.5 px-4 py-2 border border-border-primary text-text-secondary text-sm rounded-lg hover:bg-surface-700 transition-colors"
          >
            <GitBranch className="w-4 h-4" />
            View Pipeline
          </button>
          {datastore && (
            <button
              onClick={() => navigate('/ingestion/datastores')}
              className="flex items-center gap-1.5 px-4 py-2 border border-border-primary text-text-secondary text-sm rounded-lg hover:bg-surface-700 transition-colors"
            >
              <Database className="w-4 h-4" />
              View DataStore
            </button>
          )}
        </div>
      )}
    </div>
  );
}
