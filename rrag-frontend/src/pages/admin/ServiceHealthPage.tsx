import { useEffect, useState, useCallback, useRef } from 'react';
import {
  Activity,
  RefreshCw,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Clock,
  Server,
  Wifi,
  WifiOff,
  Zap,
  MemoryStick,
  Users as UsersIcon,
  Database,
  HardDrive,
  Search,
  Shield,
  GitBranch,
} from 'lucide-react';
import client from '../../api/client';

interface ServiceHealth {
  name: string;
  status: string;
  url: string;
  responseTimeMs: number | null;
  version: string | null;
  details: Record<string, unknown> | null;
}

interface HealthCheckResponse {
  overall: string;
  services: ServiceHealth[];
  checkedAt: string;
}

const STATUS_CONFIG: Record<string, { icon: typeof CheckCircle; color: string; bg: string; label: string }> = {
  healthy: { icon: CheckCircle, color: 'text-emerald-400', bg: 'bg-emerald-500/10 border-emerald-500/20', label: 'Healthy' },
  degraded: { icon: AlertTriangle, color: 'text-yellow-400', bg: 'bg-yellow-500/10 border-yellow-500/20', label: 'Degraded' },
  down: { icon: XCircle, color: 'text-red-400', bg: 'bg-red-500/10 border-red-500/20', label: 'Down' },
};

const SERVICE_ICONS: Record<string, typeof Server> = {
  'Ingestion Service': Zap,
  'Pipeline Service': Activity,
  'Auth Server': UsersIcon,
  'Redis': MemoryStick,
  'PostgreSQL': Database,
  'Keycloak': Shield,
  'MinIO': HardDrive,
  'OpenSearch': Search,
  'Qdrant': GitBranch,
  'Neo4j': GitBranch,
};

function ResponseTimeBadge({ ms }: { ms: number | null }) {
  if (ms == null) return <span className="text-xs text-text-muted">-</span>;
  const color = ms < 100 ? 'text-emerald-400' : ms < 500 ? 'text-yellow-400' : 'text-red-400';
  return <span className={`text-xs font-mono ${color}`}>{ms}ms</span>;
}

export function ServiceHealthPage() {
  const [health, setHealth] = useState<HealthCheckResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [history, setHistory] = useState<Array<{ time: string; overall: string; services: Record<string, string> }>>([]);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async () => {
    try {
      const { data } = await client.get<HealthCheckResponse>('/api/v1/ingestion/admin/health');
      setHealth(data);
      setError('');

      // Track history (last 20 checks)
      setHistory((prev) => {
        const entry = {
          time: new Date().toLocaleTimeString(),
          overall: data.overall,
          services: Object.fromEntries(data.services.map((s) => [s.name, s.status])),
        };
        return [...prev.slice(-19), entry];
      });
    } catch {
      setError('Failed to check service health');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (autoRefresh) {
      intervalRef.current = setInterval(load, 15000);
    }
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [autoRefresh, load]);

  const overallCfg = STATUS_CONFIG[health?.overall ?? 'down'] ?? STATUS_CONFIG.down;
  const OverallIcon = overallCfg.icon;

  return (
    <div className="animate-fade-in">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-text-primary flex items-center gap-2">
            <Activity className="w-5 h-5 text-emerald-400" />
            Service Health
          </h1>
          <p className="text-sm text-text-muted mt-0.5">
            Real-time health monitoring for all platform services
          </p>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-xs text-text-muted cursor-pointer">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="accent-accent-500"
            />
            Auto-refresh (15s)
          </label>
          <button
            onClick={load}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-2 bg-surface-800 border border-border-primary text-text-secondary text-sm rounded-lg hover:bg-surface-700 disabled:opacity-50 transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Check Now
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-sm text-red-400 flex items-center gap-2">
          <WifiOff className="w-4 h-4" />
          {error}
        </div>
      )}

      {/* Overall Status Banner */}
      {health && (
        <div className={`rounded-xl border p-5 mb-6 flex items-center justify-between ${overallCfg.bg} animate-slide-up`}>
          <div className="flex items-center gap-4">
            <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${overallCfg.bg}`}>
              <OverallIcon className={`w-6 h-6 ${overallCfg.color}`} />
            </div>
            <div>
              <p className={`text-lg font-bold ${overallCfg.color}`}>System {overallCfg.label}</p>
              <p className="text-xs text-text-muted flex items-center gap-1.5 mt-0.5">
                <Clock className="w-3 h-3" />
                Last checked: {new Date(health.checkedAt).toLocaleTimeString()}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {health.services.map((s) => {
              return (
                <div
                  key={s.name}
                  className={`w-3 h-3 rounded-full ${
                    s.status === 'healthy' ? 'bg-emerald-400' :
                    s.status === 'degraded' ? 'bg-yellow-400' : 'bg-red-400'
                  }`}
                  title={`${s.name}: ${s.status}`}
                />
              );
            })}
          </div>
        </div>
      )}

      {/* Service Cards */}
      {loading && !health ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="bg-surface-800 rounded-xl border border-border-primary p-6 animate-pulse">
              <div className="h-5 bg-surface-700 rounded w-32 mb-4" />
              <div className="h-4 bg-surface-700 rounded w-24 mb-2" />
              <div className="h-4 bg-surface-700 rounded w-48" />
            </div>
          ))}
        </div>
      ) : health ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          {health.services.map((service, i) => {
            const cfg = STATUS_CONFIG[service.status] ?? STATUS_CONFIG.down;
            const StatusIcon = cfg.icon;
            const ServiceIcon = SERVICE_ICONS[service.name] || Server;

            return (
              <div
                key={service.name}
                className={`bg-surface-800 rounded-xl border p-5 transition-all animate-slide-up ${
                  service.status === 'healthy' ? 'border-border-primary' :
                  service.status === 'degraded' ? 'border-yellow-500/30' : 'border-red-500/30'
                }`}
                style={{ animationDelay: `${i * 50}ms` }}
              >
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${cfg.bg} border`}>
                      <ServiceIcon className={`w-5 h-5 ${cfg.color}`} />
                    </div>
                    <div>
                      <h3 className="text-sm font-semibold text-text-primary">{service.name}</h3>
                      <p className="text-xs text-text-muted font-mono">{service.url}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <StatusIcon className={`w-4 h-4 ${cfg.color}`} />
                    <span className={`text-xs font-medium ${cfg.color}`}>{cfg.label}</span>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div>
                    <span className="text-text-muted">Response Time</span>
                    <div className="mt-1">
                      <ResponseTimeBadge ms={service.responseTimeMs} />
                    </div>
                  </div>
                  <div>
                    <span className="text-text-muted">Version</span>
                    <div className="mt-1 text-text-secondary font-mono">
                      {service.version || '-'}
                    </div>
                  </div>
                </div>

                {/* Extra details for services that expose them */}
                {service.details && (
                  <div className="mt-3 pt-3 border-t border-border-primary/50">
                    <div className="flex flex-wrap gap-3 text-xs">
                      {service.details.connectedClients != null && (
                        <div className="flex items-center gap-1 text-text-muted">
                          <Wifi className="w-3 h-3" />
                          {String(service.details.connectedClients)} clients
                        </div>
                      )}
                      {!!service.details.usedMemoryHuman && (
                        <div className="flex items-center gap-1 text-text-muted">
                          <MemoryStick className="w-3 h-3" />
                          {String(service.details.usedMemoryHuman)}
                        </div>
                      )}
                      {!!service.details.status && !service.details.connectedClients && (
                        <div className="flex items-center gap-1 text-text-muted">
                          <Server className="w-3 h-3" />
                          {String(service.details.status)}
                        </div>
                      )}
                      {!!service.details.service && (
                        <div className="flex items-center gap-1 text-text-muted">
                          <Zap className="w-3 h-3" />
                          {String(service.details.service)}
                        </div>
                      )}
                      {!!service.details.error && (
                        <div className="flex items-center gap-1 text-red-400">
                          <AlertTriangle className="w-3 h-3" />
                          <span className="truncate max-w-[200px]">{String(service.details.error)}</span>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      ) : null}

      {/* Health History */}
      {history.length > 1 && (
        <div className="bg-surface-800 rounded-xl border border-border-primary p-5 animate-slide-up" style={{ animationDelay: '200ms' }}>
          <h2 className="text-sm font-semibold text-text-primary mb-4 flex items-center gap-2">
            <Clock className="w-4 h-4 text-accent-400" />
            Recent Health Checks
          </h2>
          <div className="overflow-x-auto">
            <div className="flex gap-1 min-w-0">
              {history.map((entry, i) => (
                <div
                  key={i}
                  className="flex flex-col items-center gap-1 min-w-[48px]"
                  title={`${entry.time}: ${entry.overall}`}
                >
                  <div className={`w-full h-8 rounded flex items-center justify-center text-[10px] font-medium ${
                    entry.overall === 'healthy' ? 'bg-emerald-500/20 text-emerald-400' :
                    entry.overall === 'degraded' ? 'bg-yellow-500/20 text-yellow-400' :
                    'bg-red-500/20 text-red-400'
                  }`}>
                    {entry.overall === 'healthy' ? 'OK' : entry.overall === 'degraded' ? '!!' : 'XX'}
                  </div>
                  <span className="text-[9px] text-text-muted whitespace-nowrap">{entry.time}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
