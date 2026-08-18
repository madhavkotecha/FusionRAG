import { useEffect, useState, useCallback } from 'react';
import { adminApiKeysApi } from '../../api/admin';
import { useAuthStore } from '../../stores/auth.store';
import type { ApiKey } from '../../types/admin';
import {
  Key,
  Plus,
  Trash2,
  Copy,
  X,
  Shield,
  Clock,
  AlertTriangle,
  CheckCircle,
  Eye,
  EyeOff,
} from 'lucide-react';

export function ApiKeysPage() {
  const user = useAuthStore((s) => s.user);
  const workspaceId = user?.workspaces?.[0]?.workspaceId ?? 'default';

  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [newKeyName, setNewKeyName] = useState('');
  const [newKeyRole, setNewKeyRole] = useState('developer');
  const [newKeyExpiry, setNewKeyExpiry] = useState('');
  const [creating, setCreating] = useState(false);
  const [createdKey, setCreatedKey] = useState<string | null>(null);
  const [showKey, setShowKey] = useState(false);
  const [copied, setCopied] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await adminApiKeysApi.list(workspaceId);
      setKeys(Array.isArray(data) ? data : []);
      setError('');
    } catch {
      setError('Failed to load API keys');
    } finally {
      setLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => { load(); }, [load]);

  const handleCreate = async () => {
    if (!newKeyName) return;
    setCreating(true);
    try {
      const payload: { name: string; role?: string; expiresInDays?: number } = { name: newKeyName, role: newKeyRole };
      if (newKeyExpiry) payload.expiresInDays = parseInt(newKeyExpiry);
      const { data } = await adminApiKeysApi.create(workspaceId, payload);
      setCreatedKey(data.key || null);
      setShowCreate(false);
      setNewKeyName('');
      setNewKeyRole('developer');
      setNewKeyExpiry('');
      await load();
    } catch {
      setError('Failed to create API key');
    } finally {
      setCreating(false);
    }
  };

  const handleRevoke = async (keyId: string) => {
    if (!window.confirm('Revoke this API key? This cannot be undone.')) return;
    try {
      await adminApiKeysApi.revoke(workspaceId, keyId);
      await load();
    } catch {
      setError('Failed to revoke API key');
    }
  };

  const handleCopy = () => {
    if (createdKey) {
      navigator.clipboard.writeText(createdKey);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const roleBadgeColor: Record<string, string> = {
    admin: 'bg-red-500/10 text-red-400 border-red-500/20',
    developer: 'bg-accent-500/10 text-accent-400 border-accent-500/20',
    viewer: 'bg-surface-700 text-text-muted border-border-primary',
  };

  return (
    <div className="animate-fade-in">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-text-primary flex items-center gap-2">
            <Key className="w-5 h-5 text-orange-400" />
            API Keys
          </h1>
          <p className="text-sm text-text-muted mt-0.5">Manage API keys for programmatic access</p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-1.5 px-4 py-2 bg-gradient-to-r from-accent-500 to-accent-600 text-white text-sm font-medium rounded-lg hover:from-accent-400 hover:to-accent-500 transition-all"
        >
          <Plus className="w-4 h-4" />
          Create API Key
        </button>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-sm text-red-400 flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError('')}><X className="w-4 h-4" /></button>
        </div>
      )}

      {/* Info Banner */}
      <div className="bg-accent-500/5 border border-accent-500/20 rounded-xl p-4 text-sm text-text-secondary mb-5 flex items-start gap-3">
        <Shield className="w-5 h-5 text-accent-400 shrink-0 mt-0.5" />
        <div>
          <p className="font-medium text-text-primary">API Key Security</p>
          <p className="text-xs text-text-muted mt-1">
            API keys provide programmatic access to the platform. Keys are only shown once at creation.
            Each key is identified by its <code className="text-accent-400">sk_</code> prefix. Use the <code className="text-accent-400">X-API-Key</code> header for authentication.
          </p>
        </div>
      </div>

      {/* Created Key Display */}
      {createdKey && (
        <div className="mb-5 bg-surface-800 border border-accent-500/30 rounded-xl p-5 animate-scale-in">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-text-primary flex items-center gap-2">
              <CheckCircle className="w-4 h-4 text-emerald-400" />
              API Key Created
            </h3>
            <button onClick={() => setCreatedKey(null)} className="text-text-muted hover:text-text-primary">
              <X className="w-4 h-4" />
            </button>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex-1 bg-surface-900 border border-accent-500/30 rounded-lg px-4 py-3 font-mono text-sm text-accent-400 break-all">
              {showKey ? createdKey : createdKey.replace(/./g, '*')}
            </div>
            <button
              onClick={() => setShowKey(!showKey)}
              className="p-2 bg-surface-700 hover:bg-surface-600 text-text-secondary rounded-lg transition-colors"
              title={showKey ? 'Hide key' : 'Show key'}
            >
              {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
            <button
              onClick={handleCopy}
              className="p-2 bg-surface-700 hover:bg-surface-600 text-text-secondary rounded-lg transition-colors"
              title="Copy key"
            >
              {copied ? <CheckCircle className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
            </button>
          </div>
          <div className="flex items-center gap-1.5 mt-3 text-yellow-400 text-xs">
            <AlertTriangle className="w-3.5 h-3.5" />
            This key will only be shown once. Save it securely now.
          </div>
        </div>
      )}

      {/* Keys Table */}
      {loading ? (
        <div className="bg-surface-800 rounded-xl border border-border-primary p-8 animate-pulse">
          <div className="space-y-3">
            {[1, 2, 3].map((i) => <div key={i} className="h-10 bg-surface-700 rounded" />)}
          </div>
        </div>
      ) : keys.length === 0 ? (
        <div className="text-center py-16 animate-slide-up">
          <Key className="w-12 h-12 mx-auto text-text-muted mb-4 opacity-40" />
          <p className="text-text-muted">No API keys yet. Create one for programmatic access.</p>
        </div>
      ) : (
        <div className="bg-surface-800 rounded-xl border border-border-primary overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-surface-900 border-b border-border-primary">
              <tr>
                <th className="text-left px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Name</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Key Prefix</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Role</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Rate Limit</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Status</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Last Used</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Expires</th>
                <th className="text-right px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody>
              {keys.map((key) => (
                <tr key={key.id} className="border-b border-border-primary last:border-0 hover:bg-surface-700/50 transition-colors">
                  <td className="px-4 py-3 text-text-primary font-medium">{key.name}</td>
                  <td className="px-4 py-3 font-mono text-xs text-accent-400">{key.keyPrefix}...</td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium border ${roleBadgeColor[key.role] || roleBadgeColor.viewer}`}>
                      {key.role}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-text-muted text-xs">{key.rateLimitRpm} RPM</td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium ${
                      key.status === 'active' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'
                    }`}>
                      {key.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-text-muted text-xs flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {key.lastUsedAt ? new Date(key.lastUsedAt).toLocaleDateString() : 'Never'}
                  </td>
                  <td className="px-4 py-3 text-text-muted text-xs">
                    {key.expiresAt ? new Date(key.expiresAt).toLocaleDateString() : 'Never'}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {key.status === 'active' && (
                      <button
                        onClick={() => handleRevoke(key.id)}
                        className="inline-flex items-center gap-1 text-red-400 hover:text-red-300 text-xs px-2 py-1 rounded-lg hover:bg-red-500/10 transition-colors"
                      >
                        <Trash2 className="w-3 h-3" />
                        Revoke
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create Modal */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50" onClick={() => setShowCreate(false)}>
          <div className="bg-surface-800 border border-border-primary rounded-2xl p-6 w-full max-w-md animate-scale-in" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-lg font-semibold text-text-primary flex items-center gap-2">
                <Key className="w-5 h-5 text-orange-400" />
                Create API Key
              </h2>
              <button onClick={() => setShowCreate(false)} className="text-text-muted hover:text-text-primary">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-1">Name</label>
                <input
                  type="text"
                  value={newKeyName}
                  onChange={(e) => setNewKeyName(e.target.value)}
                  placeholder="e.g., Production API"
                  className="w-full bg-surface-900 border border-border-primary rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-1">Role</label>
                <select
                  value={newKeyRole}
                  onChange={(e) => setNewKeyRole(e.target.value)}
                  className="w-full bg-surface-900 border border-border-primary rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent-500"
                >
                  <option value="viewer">Viewer (read-only)</option>
                  <option value="developer">Developer (read/write)</option>
                  <option value="admin">Admin (full access)</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-1">Expiration</label>
                <select
                  value={newKeyExpiry}
                  onChange={(e) => setNewKeyExpiry(e.target.value)}
                  className="w-full bg-surface-900 border border-border-primary rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent-500"
                >
                  <option value="">No expiration</option>
                  <option value="30">30 days</option>
                  <option value="90">90 days</option>
                  <option value="365">1 year</option>
                </select>
              </div>
              <div className="flex gap-2 pt-2">
                <button
                  onClick={handleCreate}
                  disabled={!newKeyName || creating}
                  className="flex-1 flex items-center justify-center gap-1.5 px-4 py-2 bg-gradient-to-r from-accent-500 to-accent-600 text-white text-sm font-medium rounded-lg hover:from-accent-400 hover:to-accent-500 disabled:opacity-40 transition-all"
                >
                  <Key className="w-4 h-4" />
                  {creating ? 'Creating...' : 'Create Key'}
                </button>
                <button
                  onClick={() => setShowCreate(false)}
                  className="px-4 py-2 border border-border-primary text-text-secondary text-sm rounded-lg hover:bg-surface-700 transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
