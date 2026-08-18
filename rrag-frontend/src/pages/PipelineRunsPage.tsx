import { useEffect, useState, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { pipelineApi } from '../api/pipelines';
import type { PipelineRun } from '../types/pipeline';
import { StatusBadge } from '../components/ui/StatusBadge';
import { ArrowLeft, RefreshCw, Eye, X, Play } from 'lucide-react';

function getErrorMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  return String(err);
}

export function PipelineRunsPage() {
  const { id } = useParams<{ id: string }>();
  const [runs, setRuns] = useState<PipelineRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedRun, setSelectedRun] = useState<PipelineRun | null>(null);

  const fetchRuns = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const { data } = await pipelineApi.listRuns(id);
      setRuns(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(`Failed to load runs: ${getErrorMessage(err)}`);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchRuns();
  }, [fetchRuns]);

  const getDuration = (run: PipelineRun) => {
    if (!run.startedAt) return '-';
    const start = new Date(run.startedAt).getTime();
    const end = run.completedAt
      ? new Date(run.completedAt).getTime()
      : Date.now();
    const seconds = Math.round((end - start) / 1000);
    return `${seconds}s`;
  };

  return (
    <div className="animate-fade-in">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Link
            to={`/pipelines/${id}/edit`}
            className="flex items-center gap-1 text-accent-400 hover:text-accent-300 text-sm transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Editor
          </Link>
          <h2 className="text-xl font-bold text-text-primary">Run History</h2>
        </div>
        <button
          onClick={fetchRuns}
          className="flex items-center gap-1.5 text-sm text-text-secondary py-1.5 px-3 rounded-lg hover:bg-surface-800 border border-border-primary transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Refresh
        </button>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-sm text-red-400 flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="text-red-500 hover:text-red-300 ml-2">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {loading ? (
        <div className="text-text-muted text-center py-12">Loading runs...</div>
      ) : runs.length === 0 ? (
        <div className="text-center py-16 animate-slide-up">
          <Play className="w-12 h-12 mx-auto text-text-muted mb-4 opacity-40" />
          <p className="text-text-muted">No runs yet for this pipeline.</p>
        </div>
      ) : (
        <div className="bg-surface-800 rounded-xl border border-border-primary overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-surface-900 border-b border-border-primary">
              <tr>
                <th className="text-left px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Run ID</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Status</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Started</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Duration</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.id} className="border-b border-border-primary last:border-0 hover:bg-surface-700/50 transition-colors">
                  <td className="px-4 py-3 font-mono text-xs text-text-muted">{run.id.slice(0, 12)}...</td>
                  <td className="px-4 py-3"><StatusBadge status={run.status} /></td>
                  <td className="px-4 py-3 text-xs text-text-muted">
                    {run.startedAt ? new Date(run.startedAt).toLocaleString() : '-'}
                  </td>
                  <td className="px-4 py-3 text-xs text-text-muted">{getDuration(run)}</td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => setSelectedRun(run)}
                      className="flex items-center gap-1 text-accent-400 hover:text-accent-300 text-xs font-medium transition-colors"
                    >
                      <Eye className="w-3.5 h-3.5" />
                      View Result
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Modal */}
      {selectedRun && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 animate-fade-in">
          <div className="bg-surface-800 rounded-2xl border border-border-primary shadow-2xl max-w-2xl w-full mx-4 max-h-[80vh] overflow-hidden animate-scale-in">
            <div className="flex items-center justify-between px-6 py-4 border-b border-border-primary">
              <h3 className="font-medium text-text-primary">
                Run {selectedRun.id.slice(0, 12)}...
              </h3>
              <button onClick={() => setSelectedRun(null)} className="text-text-muted hover:text-text-primary transition-colors">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-6 overflow-auto max-h-[60vh] space-y-4">
              <div className="flex items-center gap-2">
                <StatusBadge status={selectedRun.status} />
                <span className="text-xs text-text-muted">Duration: {getDuration(selectedRun)}</span>
              </div>
              {selectedRun.error && (
                <div>
                  <h4 className="text-xs font-medium text-red-400 mb-1 uppercase tracking-wider">Error</h4>
                  <pre className="text-xs text-red-400 bg-red-500/5 border border-red-500/10 p-3 rounded-lg overflow-auto">
                    {selectedRun.error}
                  </pre>
                </div>
              )}
              {selectedRun.result && (
                <div>
                  <h4 className="text-xs font-medium text-text-muted mb-1 uppercase tracking-wider">Result</h4>
                  <pre className="text-xs text-text-secondary bg-surface-900 border border-border-primary p-3 rounded-lg overflow-auto">
                    {JSON.stringify(selectedRun.result, null, 2)}
                  </pre>
                </div>
              )}
              {selectedRun.inputParams && (
                <div>
                  <h4 className="text-xs font-medium text-text-muted mb-1 uppercase tracking-wider">Input Parameters</h4>
                  <pre className="text-xs text-text-secondary bg-surface-900 border border-border-primary p-3 rounded-lg overflow-auto">
                    {JSON.stringify(selectedRun.inputParams, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
