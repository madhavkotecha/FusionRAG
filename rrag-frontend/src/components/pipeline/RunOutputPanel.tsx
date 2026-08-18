import { useState, useEffect, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { pipelineApi } from '../../api/pipelines';
import type { PipelineRun } from '../../types/pipeline';
import { StatusBadge } from '../ui/StatusBadge';
import { RefreshCw, Terminal, CheckCircle, XCircle, Clock, ChevronDown, ChevronRight } from 'lucide-react';

function getErrorMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  return String(err);
}

interface NodeResult {
  node_id: string;
  node_type: string;
  label: string;
  category: string;
  status: string;
  message: string;
  output_data: Record<string, unknown>;
  duration_ms: number;
}

function NodeResultRow({ result }: { result: NodeResult }) {
  const [expanded, setExpanded] = useState(false);
  const isOk = result.status === 'completed';

  return (
    <div className="border border-border-primary rounded-lg overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-surface-800/50 transition-colors"
      >
        {expanded ? <ChevronDown className="w-3 h-3 text-text-muted shrink-0" /> : <ChevronRight className="w-3 h-3 text-text-muted shrink-0" />}
        {isOk ? (
          <CheckCircle className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
        ) : (
          <XCircle className="w-3.5 h-3.5 text-red-400 shrink-0" />
        )}
        <span className="text-xs font-medium text-text-primary truncate">
          {result.label || result.node_type}
        </span>
        <span className="text-[10px] text-text-muted px-1.5 py-0.5 bg-surface-700 rounded">
          {result.category || result.node_type}
        </span>
        <span className="text-xs text-text-muted ml-auto flex items-center gap-1 shrink-0">
          <Clock className="w-2.5 h-2.5" />
          {result.duration_ms}ms
        </span>
      </button>
      {!expanded && result.message && (
        <div className="px-3 pb-2 -mt-1">
          <span className="text-[11px] text-text-muted">{result.message}</span>
        </div>
      )}
      {expanded && (
        <div className="px-3 pb-3 border-t border-border-primary pt-2 animate-fade-in">
          {result.message && (
            <p className="text-xs text-text-secondary mb-2">{result.message}</p>
          )}
          <pre className="text-[10px] text-text-muted bg-surface-950 border border-border-primary p-2 rounded overflow-auto max-h-32">
            {JSON.stringify(result.output_data, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

export function RunOutputPanel() {
  const { id } = useParams<{ id: string }>();
  const [runs, setRuns] = useState<PipelineRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<PipelineRun | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pollError, setPollError] = useState<string | null>(null);

  const fetchRuns = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const { data } = await pipelineApi.listRuns(id);
      setRuns(data);
    } catch (err) {
      setError(`Failed to load runs: ${getErrorMessage(err)}`);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchRuns();
  }, [fetchRuns]);

  // Poll for active runs
  useEffect(() => {
    const activeRun = runs.find(
      (r) => r.status === 'pending' || r.status === 'running'
    );
    if (!activeRun) return;

    let consecutiveFailures = 0;

    const interval = setInterval(async () => {
      try {
        const { data } = await pipelineApi.getRun(activeRun.id);
        consecutiveFailures = 0;
        setPollError(null);
        setRuns((prev) =>
          prev.map((r) => (r.id === data.id ? data : r))
        );
        if (data.status === 'completed' || data.status === 'failed') {
          setSelectedRun(data);
        }
      } catch (err) {
        consecutiveFailures++;
        if (consecutiveFailures >= 3) {
          setPollError(`Polling failed: ${getErrorMessage(err)}`);
          clearInterval(interval);
        }
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [runs]);

  const getDuration = (run: PipelineRun) => {
    if (!run.startedAt) return '-';
    const start = new Date(run.startedAt).getTime();
    const end = run.completedAt
      ? new Date(run.completedAt).getTime()
      : Date.now();
    const seconds = Math.round((end - start) / 1000);
    return `${seconds}s`;
  };

  const nodeResults: NodeResult[] =
    (selectedRun?.result as Record<string, unknown>)?.node_results as NodeResult[] ?? [];

  const runSummary = selectedRun?.result as Record<string, unknown> | null;

  return (
    <div className="flex h-full bg-surface-900">
      {/* Runs list */}
      <div className="w-64 border-r border-border-primary overflow-y-auto">
        <div className="flex items-center justify-between px-3 py-2 border-b border-border-primary">
          <h4 className="text-[10px] font-semibold text-text-muted uppercase tracking-widest">
            Runs
          </h4>
          <button
            onClick={fetchRuns}
            className="text-xs text-accent-400 hover:text-accent-300 flex items-center gap-1"
          >
            <RefreshCw className="w-3 h-3" />
            Refresh
          </button>
        </div>
        {(error || pollError) && (
          <div className="p-2 text-xs text-red-400 bg-red-500/5 border-b border-red-500/10">
            {error || pollError}
          </div>
        )}
        {loading && runs.length === 0 && (
          <div className="p-3 text-xs text-text-muted">Loading...</div>
        )}
        {runs.length === 0 && !loading && !error && (
          <div className="p-3 text-xs text-text-muted">No runs yet</div>
        )}
        {runs.map((run) => (
          <button
            key={run.id}
            onClick={() => setSelectedRun(run)}
            className={`w-full text-left px-3 py-2 border-b border-border-primary hover:bg-surface-800 text-xs transition-colors ${
              selectedRun?.id === run.id ? 'bg-surface-800 border-l-2 border-l-accent-500' : ''
            }`}
          >
            <div className="flex items-center justify-between">
              <StatusBadge status={run.status} />
              <span className="text-text-muted">{getDuration(run)}</span>
            </div>
            <div className="text-text-muted mt-1 truncate font-mono">
              {run.id.slice(0, 12)}...
            </div>
          </button>
        ))}
      </div>

      {/* Output detail */}
      <div className="flex-1 overflow-auto p-3">
        {selectedRun ? (
          <div className="space-y-3 animate-fade-in">
            <div className="flex items-center gap-3">
              <StatusBadge status={selectedRun.status} />
              <span className="text-xs text-text-muted">
                Duration: {getDuration(selectedRun)}
              </span>
              {runSummary?.total_nodes != null && (
                <span className="text-xs text-text-muted">
                  {String(runSummary.completed_nodes)}/{String(runSummary.total_nodes)} nodes completed
                </span>
              )}
              {runSummary?.total_duration_ms != null && (
                <span className="text-xs text-text-muted flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {Number(runSummary.total_duration_ms).toFixed(0)}ms total
                </span>
              )}
            </div>
            {selectedRun.error && (
              <pre className="text-xs text-red-400 bg-red-500/5 border border-red-500/10 p-3 rounded-lg overflow-auto">
                {selectedRun.error}
              </pre>
            )}
            {nodeResults.length > 0 ? (
              <div className="space-y-1.5">
                {nodeResults.map((result) => (
                  <NodeResultRow key={result.node_id} result={result} />
                ))}
              </div>
            ) : selectedRun.result ? (
              <pre className="text-xs text-text-secondary bg-surface-950 border border-border-primary p-3 rounded-lg overflow-auto">
                {JSON.stringify(selectedRun.result, null, 2)}
              </pre>
            ) : null}
          </div>
        ) : (
          <div className="text-xs text-text-muted text-center mt-6">
            <Terminal className="w-6 h-6 mx-auto mb-2 opacity-30" />
            Select a run to view its output
          </div>
        )}
      </div>
    </div>
  );
}
