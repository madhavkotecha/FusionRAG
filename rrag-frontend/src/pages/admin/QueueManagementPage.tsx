import { useEffect, useState, useCallback, useRef, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { ingestionApi, streamJobs, type IngestionJob } from '../../api/ingestion';
import { adminStatsApi, adminQueueApi } from '../../api/admin';
import type { QueueStats } from '../../types/admin';
import { StatusBadge } from '../../components/ui/StatusBadge';
import {
  Layers,
  Clock,
  Play,
  CheckCircle,
  XCircle,
  RefreshCw,
  Search,
  Timer,
  BarChart3,
  ChevronRight,
  RotateCcw,
  Pause,
  X,
} from 'lucide-react';

function formatDuration(ms: number | null): string {
  if (ms == null) return '-';
  if (ms < 1000) return `${ms}ms`;
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s`;
  return `${Math.floor(s / 60)}m ${s % 60}s`;
}

function formatRelativeTime(dateStr: string | null): string {
  if (!dateStr) return '-';
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

const STATUS_TABS = ['all', 'queued', 'running', 'completed', 'failed'] as const;

export function QueueManagementPage() {
  const navigate = useNavigate();
  const [jobs, setJobs] = useState<IngestionJob[]>([]);
  const [queueStats, setQueueStats] = useState<QueueStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [statusTab, setStatusTab] = useState<string>('all');
  const [search, setSearch] = useState('');
  const [autoRefresh, setAutoRefresh] = useState(true);
  const stopStreamRef = useRef<(() => void) | null>(null);
  const refreshIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadJobs = useCallback(async () => {
    try {
      const res = await ingestionApi.listJobs();
      setJobs(Array.isArray(res.data?.jobs) ? res.data.jobs : []);
      setError('');
    } catch {
      setError('Failed to load jobs');
    } finally {
      setLoading(false);
    }
  }, []);

  const loadStats = useCallback(async () => {
    try {
      const stats = await adminStatsApi.getQueueStats();
      setQueueStats(stats);
    } catch { /* stats are non-critical */ }
  }, []);

  const connectStream = useCallback(() => {
    stopStreamRef.current?.();
    const stop = streamJobs(
      (updatedJobs) => { setJobs(updatedJobs); setError(''); },
      () => { loadJobs(); },
    );
    stopStreamRef.current = stop;
  }, [loadJobs]);

  useEffect(() => {
    loadJobs();
    loadStats();
  }, [loadJobs, loadStats]);

  const hasActive = useMemo(
    () => jobs.some((j) => j.status === 'queued' || j.status === 'running'),
    [jobs],
  );

  useEffect(() => {
    if (!hasActive) {
      stopStreamRef.current?.();
      stopStreamRef.current = null;
      return;
    }
    if (!stopStreamRef.current) connectStream();
    return () => { stopStreamRef.current?.(); stopStreamRef.current = null; };
  }, [hasActive, connectStream]);

  // Auto-refresh stats
  useEffect(() => {
    if (autoRefresh) {
      refreshIntervalRef.current = setInterval(() => { loadStats(); }, 30000);
    }
    return () => { if (refreshIntervalRef.current) clearInterval(refreshIntervalRef.current); };
  }, [autoRefresh, loadStats]);

  const filteredJobs = useMemo(() => {
    let result = jobs;
    if (statusTab !== 'all') result = result.filter((j) => j.status === statusTab);
    if (search) {
      const q = search.toLowerCase();
      result = result.filter(
        (j) => j.pipeline_name.toLowerCase().includes(q) || j.id.toLowerCase().includes(q),
      );
    }
    return result.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
  }, [jobs, statusTab, search]);

  const handleCancel = async (id: string) => {
    try {
      await ingestionApi.cancelJob(id);
      await loadJobs();
    } catch { setError('Failed to cancel job'); }
  };

  const handleRetry = async (job: IngestionJob) => {
    try {
      await ingestionApi.createJob({
        pipeline_name: job.pipeline_name,
        document_ids: job.document_ids,
        datastore_id: job.datastore_id ?? undefined,
      });
      await loadJobs();
      connectStream();
    } catch { setError('Failed to retry job'); }
  };

  const handleQueueAction = async (action: string, label: string) => {
    if (!window.confirm(`${label}? This cannot be undone.`)) return;
    try {
      const { data } = await adminQueueApi.performAction(action);
      setError('');
      await loadJobs();
      await loadStats();
      alert(data.message);
    } catch { setError(`Failed to ${label.toLowerCase()}`); }
  };

  const qs = queueStats;
  const total = qs?.totalJobs || 0;

  return (
    <div className="animate-fade-in">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-text-primary">Queue Management</h1>
          <p className="text-sm text-text-muted mt-0.5">Monitor and manage ingestion job queue</p>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-xs text-text-muted cursor-pointer">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="accent-accent-500"
            />
            Auto-refresh
          </label>
          <button
            onClick={() => { loadJobs(); loadStats(); }}
            className="flex items-center gap-1.5 px-3 py-2 bg-surface-800 border border-border-primary text-text-secondary text-sm rounded-lg hover:bg-surface-700 transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-sm text-red-400 flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError('')}><X className="w-4 h-4" /></button>
        </div>
      )}

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
        {[
          { label: 'Total', value: qs?.totalJobs ?? 0, icon: Layers, color: 'from-surface-700 to-surface-800', text: 'text-text-primary' },
          { label: 'Queued', value: qs?.queued ?? 0, icon: Clock, color: 'from-yellow-500/20 to-yellow-600/10', text: 'text-yellow-400' },
          { label: 'Running', value: qs?.running ?? 0, icon: Play, color: 'from-accent-500/20 to-accent-600/10', text: 'text-accent-400' },
          { label: 'Completed', value: qs?.completed ?? 0, icon: CheckCircle, color: 'from-emerald-500/20 to-emerald-600/10', text: 'text-emerald-400' },
          { label: 'Failed', value: qs?.failed ?? 0, icon: XCircle, color: 'from-red-500/20 to-red-600/10', text: 'text-red-400' },
        ].map((s) => (
          <div key={s.label} className={`bg-gradient-to-br ${s.color} rounded-xl border border-border-primary p-4`}>
            <div className="flex items-center justify-between">
              <s.icon className={`w-4 h-4 ${s.text}`} />
              <span className="text-[10px] font-medium text-text-muted uppercase tracking-wider">{s.label}</span>
            </div>
            <p className={`text-2xl font-bold ${s.text} mt-2`}>{s.value}</p>
            {total > 0 && s.label !== 'Total' && (
              <div className="mt-2">
                <div className="w-full bg-surface-900/50 rounded-full h-1">
                  <div className={`h-1 rounded-full transition-all duration-500 ${
                    s.label === 'Queued' ? 'bg-yellow-400' : s.label === 'Running' ? 'bg-accent-400' : s.label === 'Completed' ? 'bg-emerald-400' : 'bg-red-400'
                  }`} style={{ width: `${Math.round((s.value / total) * 100)}%` }} />
                </div>
                <p className="text-[10px] text-text-muted mt-1">{Math.round((s.value / total) * 100)}%</p>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Distribution Bar & Avg Duration */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="md:col-span-2 bg-surface-800 rounded-xl border border-border-primary p-4">
          <h3 className="text-sm font-medium text-text-primary mb-3 flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-accent-400" />
            Distribution
          </h3>
          {total > 0 ? (
            <>
              <div className="flex h-5 rounded-full overflow-hidden bg-surface-900">
                {[
                  { key: 'queued', val: qs?.queued ?? 0, bg: 'bg-yellow-400' },
                  { key: 'running', val: qs?.running ?? 0, bg: 'bg-accent-400' },
                  { key: 'completed', val: qs?.completed ?? 0, bg: 'bg-emerald-400' },
                  { key: 'failed', val: qs?.failed ?? 0, bg: 'bg-red-400' },
                ].map((s) => {
                  const pct = (s.val / total) * 100;
                  return pct > 0 ? (
                    <div key={s.key} className={`${s.bg} transition-all duration-500`} style={{ width: `${pct}%` }} title={`${s.key}: ${s.val}`} />
                  ) : null;
                })}
              </div>
              <div className="flex flex-wrap gap-4 mt-3 text-xs text-text-muted">
                {[
                  { label: 'Queued', dot: 'bg-yellow-400', val: qs?.queued ?? 0 },
                  { label: 'Running', dot: 'bg-accent-400', val: qs?.running ?? 0 },
                  { label: 'Completed', dot: 'bg-emerald-400', val: qs?.completed ?? 0 },
                  { label: 'Failed', dot: 'bg-red-400', val: qs?.failed ?? 0 },
                ].map((item) => (
                  <span key={item.label} className="flex items-center gap-1.5">
                    <span className={`w-2 h-2 rounded-full ${item.dot}`} />
                    {item.label} <span className="text-text-primary font-medium">{item.val}</span>
                  </span>
                ))}
              </div>
            </>
          ) : (
            <p className="text-sm text-text-muted">No jobs to display</p>
          )}
        </div>
        <div className="bg-surface-800 rounded-xl border border-border-primary p-4">
          <h3 className="text-sm font-medium text-text-primary mb-3 flex items-center gap-2">
            <Timer className="w-4 h-4 text-highlight-400" />
            Performance
          </h3>
          <div>
            <p className="text-xs text-text-muted">Avg. Duration</p>
            <p className="text-xl font-bold text-text-primary mt-1">{formatDuration(qs?.avgDurationMs ?? null)}</p>
          </div>
          <div className="mt-3">
            <p className="text-xs text-text-muted">Active Workers</p>
            <p className="text-xl font-bold text-accent-400 mt-1">{qs?.running ?? 0}</p>
          </div>
        </div>
      </div>

      {/* Admin Actions */}
      <div className="flex flex-wrap gap-2 mb-6">
        <button
          onClick={() => handleQueueAction('retry_all_failed', 'Retry all failed jobs')}
          disabled={(qs?.failed ?? 0) === 0}
          className="flex items-center gap-1.5 px-3 py-2 bg-surface-800 border border-border-primary text-accent-400 text-xs font-medium rounded-lg hover:bg-accent-500/10 hover:border-accent-500/30 disabled:opacity-30 disabled:hover:bg-surface-800 transition-colors"
        >
          <RotateCcw className="w-3.5 h-3.5" />
          Retry All Failed ({qs?.failed ?? 0})
        </button>
        <button
          onClick={() => handleQueueAction('purge_failed', 'Purge all failed jobs')}
          disabled={(qs?.failed ?? 0) === 0}
          className="flex items-center gap-1.5 px-3 py-2 bg-surface-800 border border-border-primary text-red-400 text-xs font-medium rounded-lg hover:bg-red-500/10 hover:border-red-500/30 disabled:opacity-30 disabled:hover:bg-surface-800 transition-colors"
        >
          <XCircle className="w-3.5 h-3.5" />
          Purge Failed
        </button>
        <button
          onClick={() => handleQueueAction('purge_completed', 'Purge all completed jobs')}
          disabled={(qs?.completed ?? 0) === 0}
          className="flex items-center gap-1.5 px-3 py-2 bg-surface-800 border border-border-primary text-text-muted text-xs font-medium rounded-lg hover:bg-surface-700 disabled:opacity-30 disabled:hover:bg-surface-800 transition-colors"
        >
          <CheckCircle className="w-3.5 h-3.5" />
          Purge Completed
        </button>
        <button
          onClick={() => handleQueueAction('purge_all', 'Purge all finished jobs')}
          disabled={total === 0}
          className="flex items-center gap-1.5 px-3 py-2 bg-surface-800 border border-red-500/20 text-red-400 text-xs font-medium rounded-lg hover:bg-red-500/10 disabled:opacity-30 disabled:hover:bg-surface-800 transition-colors"
        >
          <X className="w-3.5 h-3.5" />
          Purge All Finished
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3 mb-5">
        <div className="flex gap-1">
          {STATUS_TABS.map((tab) => (
            <button
              key={tab}
              onClick={() => setStatusTab(tab)}
              className={`text-xs px-3 py-1.5 rounded-lg font-medium transition-colors capitalize ${
                statusTab === tab
                  ? 'bg-accent-500/20 text-accent-400 border border-accent-500/30'
                  : 'bg-surface-800 text-text-muted border border-border-primary hover:text-text-secondary hover:bg-surface-700'
              }`}
            >
              {tab}
            </button>
          ))}
        </div>
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
          <input
            type="text"
            placeholder="Search by pipeline name or job ID..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-2 bg-surface-900 border border-border-primary rounded-lg text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent-500"
          />
        </div>
      </div>

      {/* Jobs Table */}
      {loading ? (
        <div className="bg-surface-800 rounded-xl border border-border-primary p-8 animate-pulse">
          <div className="space-y-3">
            {[1, 2, 3, 4].map((i) => <div key={i} className="h-10 bg-surface-700 rounded" />)}
          </div>
        </div>
      ) : filteredJobs.length === 0 ? (
        <div className="text-center py-16 animate-slide-up">
          <Layers className="w-12 h-12 mx-auto text-text-muted mb-4 opacity-40" />
          <p className="text-text-muted">{statusTab !== 'all' ? `No ${statusTab} jobs` : 'No jobs in the queue'}</p>
        </div>
      ) : (
        <div className="bg-surface-800 rounded-xl border border-border-primary overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-surface-900 border-b border-border-primary">
              <tr>
                <th className="text-left px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Job ID</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Pipeline</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Docs</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Status</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Progress</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Duration</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Created</th>
                <th className="text-right px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredJobs.map((job) => (
                <tr
                  key={job.id}
                  className="border-b border-border-primary last:border-0 hover:bg-surface-700/50 transition-colors cursor-pointer"
                  onClick={() => navigate(`/ingestion/jobs/${job.id}`)}
                >
                  <td className="px-4 py-3 font-mono text-xs text-text-muted">{job.id.slice(0, 8)}...</td>
                  <td className="px-4 py-3 text-text-primary">{job.pipeline_name}</td>
                  <td className="px-4 py-3 text-text-muted">{job.document_ids.length}</td>
                  <td className="px-4 py-3"><StatusBadge status={job.status} /></td>
                  <td className="px-4 py-3">
                    {job.total_steps > 0 ? (
                      <div className="flex items-center gap-2">
                        <div className="w-20 bg-surface-900 rounded-full h-1.5">
                          <div
                            className={`h-1.5 rounded-full transition-all duration-500 ${
                              job.status === 'failed' ? 'bg-red-400' : 'bg-accent-500'
                            }`}
                            style={{ width: `${job.progress}%` }}
                          />
                        </div>
                        <span className="text-xs text-text-muted">{job.progress}%</span>
                      </div>
                    ) : (
                      <span className="text-xs text-text-muted">-</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-xs text-text-muted">{formatDuration(job.total_duration_ms)}</td>
                  <td className="px-4 py-3 text-xs text-text-muted">{formatRelativeTime(job.created_at)}</td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-1" onClick={(e) => e.stopPropagation()}>
                      {(job.status === 'queued' || job.status === 'running') && (
                        <button
                          onClick={() => handleCancel(job.id)}
                          className="inline-flex items-center gap-1 text-red-400 hover:text-red-300 text-xs px-2 py-1 rounded-lg hover:bg-red-500/10 transition-colors"
                          title="Cancel job"
                        >
                          <Pause className="w-3 h-3" />
                          Cancel
                        </button>
                      )}
                      {job.status === 'failed' && (
                        <button
                          onClick={() => handleRetry(job)}
                          className="inline-flex items-center gap-1 text-accent-400 hover:text-accent-300 text-xs px-2 py-1 rounded-lg hover:bg-accent-500/10 transition-colors"
                          title="Retry job"
                        >
                          <RotateCcw className="w-3 h-3" />
                          Retry
                        </button>
                      )}
                      <button
                        onClick={() => navigate(`/ingestion/jobs/${job.id}`)}
                        className="text-text-muted hover:text-text-primary p-1"
                        title="View details"
                      >
                        <ChevronRight className="w-4 h-4" />
                      </button>
                    </div>
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
