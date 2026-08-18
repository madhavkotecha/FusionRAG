import { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { adminStatsApi } from '../../api/admin';
import type { SystemStats } from '../../types/admin';
import {
  Users,
  GitBranch,
  PlayCircle,
  FileText,
  Database,
  RefreshCw,
  Activity,
  TrendingUp,
  Clock,
  CheckCircle,
  XCircle,
  AlertTriangle,
  ChevronRight,
} from 'lucide-react';

function StatCard({
  icon: Icon,
  label,
  value,
  sub,
  color,
  delay,
}: {
  icon: typeof Users;
  label: string;
  value: number;
  sub?: string;
  color: string;
  delay: number;
}) {
  return (
    <div
      className="bg-surface-800 rounded-xl border border-border-primary p-5 animate-slide-up"
      style={{ animationDelay: `${delay}ms` }}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium text-text-muted uppercase tracking-wider">{label}</p>
          <p className="text-2xl font-bold text-text-primary mt-1">{value}</p>
          {sub && <p className="text-xs text-text-muted mt-1">{sub}</p>}
        </div>
        <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${color} flex items-center justify-center`}>
          <Icon className="w-5 h-5 text-white/80" />
        </div>
      </div>
    </div>
  );
}

const ACTION_ICONS: Record<string, typeof Activity> = {
  login: Users,
  logout: Users,
  user_invite: Users,
  user_role_change: Users,
  user_suspend: AlertTriangle,
  user_activate: CheckCircle,
  pipeline_create: GitBranch,
  pipeline_delete: GitBranch,
  job_create: PlayCircle,
  api_key_create: Activity,
  api_key_revoke: XCircle,
  member_add: Users,
  member_remove: Users,
};

const ACTION_COLORS: Record<string, string> = {
  login: 'text-accent-400',
  logout: 'text-text-muted',
  user_invite: 'text-highlight-400',
  user_role_change: 'text-violet-400',
  user_suspend: 'text-red-400',
  user_activate: 'text-emerald-400',
  api_key_create: 'text-orange-400',
  api_key_revoke: 'text-red-400',
  member_add: 'text-emerald-400',
  member_remove: 'text-red-400',
};

export function AdminDashboardPage() {
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await adminStatsApi.getOverview();
      setStats(data);
      setError('');
    } catch {
      setError('Failed to load system stats');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const jobTotal = stats ? stats.totalJobs : 0;
  const statusEntries = stats ? Object.entries(stats.jobsByStatus) : [];

  return (
    <div className="animate-fade-in">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-text-primary">System Overview</h1>
          <p className="text-sm text-text-muted mt-0.5">Platform administration dashboard</p>
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="flex items-center gap-1.5 px-3 py-2 bg-surface-800 border border-border-primary text-text-secondary text-sm rounded-lg hover:bg-surface-700 disabled:opacity-50 transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Stats Grid */}
      {loading && !stats ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 mb-8">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="bg-surface-800 rounded-xl border border-border-primary p-5 animate-pulse">
              <div className="h-3 bg-surface-700 rounded w-20 mb-3" />
              <div className="h-7 bg-surface-700 rounded w-12" />
            </div>
          ))}
        </div>
      ) : stats ? (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 mb-8">
            <StatCard icon={Users} label="Users" value={stats.totalUsers} sub={`${stats.activeUsers} active, ${stats.suspendedUsers} suspended`} color="from-accent-500 to-accent-600" delay={0} />
            <StatCard icon={GitBranch} label="Pipelines" value={stats.totalPipelines} color="from-violet-500 to-violet-600" delay={50} />
            <StatCard icon={PlayCircle} label="Jobs" value={stats.totalJobs} sub={`${stats.jobsByStatus['running'] || 0} running`} color="from-highlight-500 to-highlight-600" delay={100} />
            <StatCard icon={FileText} label="Documents" value={stats.totalDocuments} color="from-emerald-500 to-emerald-600" delay={150} />
            <StatCard icon={Database} label="DataStores" value={stats.totalDataStores} color="from-orange-500 to-orange-600" delay={200} />
          </div>

          {/* Queue Status */}
          <div className="bg-surface-800 rounded-xl border border-border-primary p-5 mb-8 animate-slide-up" style={{ animationDelay: '250ms' }}>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-semibold text-text-primary flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-accent-400" />
                Queue Distribution
              </h2>
              <Link to="/admin/queue" className="text-xs text-accent-400 hover:text-accent-300 flex items-center gap-1">
                View Details <ChevronRight className="w-3 h-3" />
              </Link>
            </div>

            {jobTotal > 0 ? (
              <>
                <div className="flex h-4 rounded-full overflow-hidden bg-surface-900 mb-3">
                  {statusEntries.map(([status, count]) => {
                    const colors: Record<string, string> = {
                      queued: 'bg-yellow-400',
                      running: 'bg-accent-400',
                      completed: 'bg-emerald-400',
                      failed: 'bg-red-400',
                    };
                    const pct = (count / jobTotal) * 100;
                    return pct > 0 ? (
                      <div
                        key={status}
                        className={`${colors[status] || 'bg-surface-600'} transition-all duration-500`}
                        style={{ width: `${pct}%` }}
                        title={`${status}: ${count} (${Math.round(pct)}%)`}
                      />
                    ) : null;
                  })}
                </div>
                <div className="flex flex-wrap gap-4 text-xs text-text-muted">
                  {statusEntries.map(([status, count]) => {
                    const dots: Record<string, string> = {
                      queued: 'bg-yellow-400',
                      running: 'bg-accent-400',
                      completed: 'bg-emerald-400',
                      failed: 'bg-red-400',
                    };
                    return (
                      <div key={status} className="flex items-center gap-1.5">
                        <div className={`w-2 h-2 rounded-full ${dots[status] || 'bg-surface-600'}`} />
                        <span className="capitalize">{status}</span>
                        <span className="text-text-primary font-medium">{count}</span>
                      </div>
                    );
                  })}
                </div>
              </>
            ) : (
              <p className="text-sm text-text-muted">No jobs in the queue</p>
            )}
          </div>

          {/* Recent Activity */}
          <div className="bg-surface-800 rounded-xl border border-border-primary p-5 animate-slide-up" style={{ animationDelay: '300ms' }}>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-semibold text-text-primary flex items-center gap-2">
                <Activity className="w-4 h-4 text-highlight-400" />
                Recent Activity
              </h2>
              <Link to="/admin/audit-logs" className="text-xs text-accent-400 hover:text-accent-300 flex items-center gap-1">
                View All <ChevronRight className="w-3 h-3" />
              </Link>
            </div>

            {stats.recentActivity.length > 0 ? (
              <div className="space-y-0">
                {stats.recentActivity.map((entry) => {
                  const Icon = ACTION_ICONS[entry.action] || Activity;
                  const color = ACTION_COLORS[entry.action] || 'text-text-muted';
                  return (
                    <div
                      key={entry.id}
                      className="flex items-center gap-3 py-2.5 border-b border-border-primary/50 last:border-0"
                    >
                      <div className={`w-7 h-7 rounded-lg bg-surface-900 flex items-center justify-center shrink-0 ${color}`}>
                        <Icon className="w-3.5 h-3.5" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm text-text-primary">
                          <span className="font-medium">{entry.action.replace(/_/g, ' ')}</span>
                          {entry.resourceType && (
                            <span className="text-text-muted"> on {entry.resourceType}</span>
                          )}
                        </p>
                        <p className="text-xs text-text-muted flex items-center gap-2">
                          <Clock className="w-3 h-3" />
                          {new Date(entry.timestamp).toLocaleString()}
                          {entry.ipAddress && <span>from {entry.ipAddress}</span>}
                        </p>
                      </div>
                      <span
                        className={`text-xs px-2 py-0.5 rounded-md font-medium ${
                          entry.status === 'success'
                            ? 'bg-emerald-500/10 text-emerald-400'
                            : 'bg-red-500/10 text-red-400'
                        }`}
                      >
                        {entry.status}
                      </span>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="text-sm text-text-muted text-center py-6">No recent activity</p>
            )}
          </div>

          {/* Quick Links */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mt-6">
            {[
              { to: '/admin/users', label: 'Manage Users', icon: Users, color: 'from-accent-500/20 to-accent-500/10' },
              { to: '/admin/queue', label: 'Queue Management', icon: PlayCircle, color: 'from-highlight-500/20 to-highlight-500/10' },
              { to: '/admin/api-keys', label: 'API Keys', icon: Activity, color: 'from-orange-500/20 to-orange-500/10' },
              { to: '/admin/audit-logs', label: 'Audit Logs', icon: FileText, color: 'from-violet-500/20 to-violet-500/10' },
              { to: '/admin/health', label: 'Service Health', icon: Activity, color: 'from-emerald-500/20 to-emerald-500/10' },
              { to: '/admin/settings', label: 'System Settings', icon: Activity, color: 'from-surface-700/50 to-surface-700/30' },
              { to: '/admin/workspaces', label: 'Workspaces', icon: Users, color: 'from-highlight-500/20 to-highlight-500/10' },
            ].map((link) => (
              <Link
                key={link.to}
                to={link.to}
                className={`flex items-center gap-3 p-4 bg-gradient-to-r ${link.color} border border-border-primary rounded-xl hover:border-accent-500/30 transition-all group`}
              >
                <link.icon className="w-5 h-5 text-text-secondary group-hover:text-accent-400 transition-colors" />
                <span className="text-sm font-medium text-text-primary group-hover:text-accent-400 transition-colors">{link.label}</span>
                <ChevronRight className="w-4 h-4 text-text-muted ml-auto" />
              </Link>
            ))}
          </div>
        </>
      ) : null}
    </div>
  );
}
