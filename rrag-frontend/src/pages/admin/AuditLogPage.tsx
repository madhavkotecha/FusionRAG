import { Fragment, useEffect, useState, useCallback } from 'react';
import { adminAuditApi } from '../../api/admin';
import type { AuditLogEntry } from '../../types/admin';
import {
  FileText,
  ChevronDown,
  ChevronRight,
  ChevronLeft,
  Clock,
  Filter,
  X,
} from 'lucide-react';

const ACTION_OPTIONS = [
  '', 'login', 'logout', 'user_invite', 'user_role_change', 'user_suspend', 'user_activate',
  'member_add', 'member_remove', 'member_role_change', 'api_key_create', 'api_key_revoke',
  'pipeline_create', 'pipeline_delete', 'job_create',
];

const RESOURCE_OPTIONS = [
  '', 'user', 'workspace_member', 'api_key', 'invitation', 'pipeline', 'job', 'session',
];

const ACTION_BADGE_COLORS: Record<string, string> = {
  login: 'bg-violet-500/10 text-violet-400',
  logout: 'bg-surface-700 text-text-muted',
  user_invite: 'bg-highlight-500/10 text-highlight-400',
  user_role_change: 'bg-violet-500/10 text-violet-400',
  user_suspend: 'bg-red-500/10 text-red-400',
  user_activate: 'bg-emerald-500/10 text-emerald-400',
  member_add: 'bg-emerald-500/10 text-emerald-400',
  member_remove: 'bg-red-500/10 text-red-400',
  member_role_change: 'bg-violet-500/10 text-violet-400',
  api_key_create: 'bg-orange-500/10 text-orange-400',
  api_key_revoke: 'bg-red-500/10 text-red-400',
  pipeline_create: 'bg-accent-500/10 text-accent-400',
  pipeline_delete: 'bg-red-500/10 text-red-400',
  job_create: 'bg-highlight-500/10 text-highlight-400',
};

export function AuditLogPage() {
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // Filters
  const [actionFilter, setActionFilter] = useState('');
  const [resourceFilter, setResourceFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, unknown> = { page, pageSize };
      if (actionFilter) params.action = actionFilter;
      if (resourceFilter) params.resourceType = resourceFilter;
      if (statusFilter) params.status = statusFilter;
      if (fromDate) params.from = fromDate;
      if (toDate) params.to = toDate;

      const { data } = await adminAuditApi.query(params as Record<string, string>);
      setLogs(data.logs ?? []);
      setTotal(data.total ?? 0);
      setError('');
    } catch {
      setError('Failed to load audit logs');
    } finally {
      setLoading(false);
    }
  }, [page, actionFilter, resourceFilter, statusFilter, fromDate, toDate]);

  useEffect(() => { load(); }, [load]);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const clearFilters = () => {
    setActionFilter('');
    setResourceFilter('');
    setStatusFilter('');
    setFromDate('');
    setToDate('');
    setPage(1);
  };

  const hasFilters = actionFilter || resourceFilter || statusFilter || fromDate || toDate;

  return (
    <div className="animate-fade-in">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-text-primary flex items-center gap-2">
            <FileText className="w-5 h-5 text-violet-400" />
            Audit Logs
          </h1>
          <p className="text-sm text-text-muted mt-0.5">{total} total entries</p>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-sm text-red-400 flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError('')}><X className="w-4 h-4" /></button>
        </div>
      )}

      {/* Filters */}
      <div className="bg-surface-800 rounded-xl border border-border-primary p-4 mb-5">
        <div className="flex items-center gap-2 mb-3">
          <Filter className="w-4 h-4 text-text-muted" />
          <span className="text-sm font-medium text-text-secondary">Filters</span>
          {hasFilters && (
            <button onClick={clearFilters} className="text-xs text-accent-400 hover:text-accent-300 ml-auto">
              Clear All
            </button>
          )}
        </div>
        <div className="flex flex-wrap gap-3">
          <select
            value={actionFilter}
            onChange={(e) => { setActionFilter(e.target.value); setPage(1); }}
            className="bg-surface-900 border border-border-primary rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent-500"
          >
            <option value="">All Actions</option>
            {ACTION_OPTIONS.filter(Boolean).map((a) => (
              <option key={a} value={a}>{a.replace(/_/g, ' ')}</option>
            ))}
          </select>
          <select
            value={resourceFilter}
            onChange={(e) => { setResourceFilter(e.target.value); setPage(1); }}
            className="bg-surface-900 border border-border-primary rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent-500"
          >
            <option value="">All Resources</option>
            {RESOURCE_OPTIONS.filter(Boolean).map((r) => (
              <option key={r} value={r}>{r.replace(/_/g, ' ')}</option>
            ))}
          </select>
          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
            className="bg-surface-900 border border-border-primary rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent-500"
          >
            <option value="">All Status</option>
            <option value="success">Success</option>
            <option value="failure">Failure</option>
          </select>
          <div className="flex items-center gap-2">
            <input
              type="date"
              value={fromDate}
              onChange={(e) => { setFromDate(e.target.value); setPage(1); }}
              className="bg-surface-900 border border-border-primary rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent-500"
              placeholder="From"
            />
            <span className="text-text-muted text-xs">to</span>
            <input
              type="date"
              value={toDate}
              onChange={(e) => { setToDate(e.target.value); setPage(1); }}
              className="bg-surface-900 border border-border-primary rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent-500"
              placeholder="To"
            />
          </div>
        </div>
      </div>

      {/* Logs Table */}
      {loading ? (
        <div className="bg-surface-800 rounded-xl border border-border-primary p-8 animate-pulse">
          <div className="space-y-3">
            {[1, 2, 3, 4, 5].map((i) => <div key={i} className="h-10 bg-surface-700 rounded" />)}
          </div>
        </div>
      ) : logs.length === 0 ? (
        <div className="text-center py-16 animate-slide-up">
          <FileText className="w-12 h-12 mx-auto text-text-muted mb-4 opacity-40" />
          <p className="text-text-muted">No audit log entries found</p>
        </div>
      ) : (
        <div className="bg-surface-800 rounded-xl border border-border-primary overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-surface-900 border-b border-border-primary">
              <tr>
                <th className="w-8 px-2 py-3" />
                <th className="text-left px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Timestamp</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Action</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Resource</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">User</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Status</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">IP</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((entry) => (
                <Fragment key={entry.id}>
                  <tr
                    className="border-b border-border-primary hover:bg-surface-700/50 transition-colors cursor-pointer"
                    onClick={() => setExpandedId(expandedId === entry.id ? null : entry.id)}
                  >
                    <td className="px-2 py-3 text-center">
                      {expandedId === entry.id ? (
                        <ChevronDown className="w-3.5 h-3.5 text-text-muted" />
                      ) : (
                        <ChevronRight className="w-3.5 h-3.5 text-text-muted" />
                      )}
                    </td>
                    <td className="px-4 py-3 text-text-muted text-xs whitespace-nowrap">
                      <div className="flex items-center gap-1.5">
                        <Clock className="w-3 h-3" />
                        {new Date(entry.timestamp).toLocaleString()}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium ${ACTION_BADGE_COLORS[entry.action] || 'bg-surface-700 text-text-muted'}`}>
                        {entry.action.replace(/_/g, ' ')}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-text-secondary text-xs">
                      <span className="text-text-primary">{entry.resourceType}</span>
                      {entry.resourceId && (
                        <span className="text-text-muted font-mono ml-1">/{entry.resourceId.slice(0, 8)}</span>
                      )}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-text-muted">
                      {entry.userId ? entry.userId.slice(0, 8) + '...' : '-'}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium ${
                        entry.status === 'success' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'
                      }`}>
                        {entry.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-text-muted">{entry.ipAddress || '-'}</td>
                  </tr>
                  {expandedId === entry.id && (
                    <tr key={`${entry.id}-details`} className="bg-surface-900/50">
                      <td colSpan={7} className="px-6 py-4">
                        <div className="grid grid-cols-2 gap-4 text-xs">
                          <div>
                            <span className="text-text-muted">Full User ID:</span>
                            <span className="text-text-primary font-mono ml-2">{entry.userId || 'N/A'}</span>
                          </div>
                          <div>
                            <span className="text-text-muted">Full Resource ID:</span>
                            <span className="text-text-primary font-mono ml-2">{entry.resourceId || 'N/A'}</span>
                          </div>
                          <div>
                            <span className="text-text-muted">Workspace:</span>
                            <span className="text-text-primary font-mono ml-2">{entry.workspaceId || 'N/A'}</span>
                          </div>
                          <div>
                            <span className="text-text-muted">User Agent:</span>
                            <span className="text-text-primary ml-2 truncate block max-w-md">{entry.userAgent || 'N/A'}</span>
                          </div>
                        </div>
                        {entry.details && Object.keys(entry.details).length > 0 && (
                          <div className="mt-3">
                            <span className="text-text-muted text-xs">Details:</span>
                            <pre className="mt-1 bg-surface-900 rounded-lg p-3 text-xs text-text-secondary font-mono overflow-x-auto">
                              {JSON.stringify(entry.details, null, 2)}
                            </pre>
                          </div>
                        )}
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>

          {/* Pagination */}
          <div className="flex items-center justify-between px-4 py-3 border-t border-border-primary bg-surface-900">
            <div className="text-xs text-text-muted">
              Showing {((page - 1) * pageSize) + 1} - {Math.min(page * pageSize, total)} of {total}
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage(Math.max(1, page - 1))}
                disabled={page <= 1}
                className="flex items-center gap-1 px-3 py-1.5 text-xs bg-surface-800 border border-border-primary rounded-lg text-text-secondary hover:bg-surface-700 disabled:opacity-40 transition-colors"
              >
                <ChevronLeft className="w-3 h-3" />
                Prev
              </button>
              <span className="text-xs text-text-muted">
                Page {page} of {totalPages}
              </span>
              <button
                onClick={() => setPage(Math.min(totalPages, page + 1))}
                disabled={page >= totalPages}
                className="flex items-center gap-1 px-3 py-1.5 text-xs bg-surface-800 border border-border-primary rounded-lg text-text-secondary hover:bg-surface-700 disabled:opacity-40 transition-colors"
              >
                Next
                <ChevronRight className="w-3 h-3" />
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
