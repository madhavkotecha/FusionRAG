import { useState, useEffect } from 'react';
import { adminWorkspacesApi } from '../../api/admin';
import { teamsApi } from '../../api/teams';
import { useAuthStore } from '../../stores/auth.store';
import type { Team } from '../../types/admin';
import { X, FolderPlus, User, Users, Building2 } from 'lucide-react';

interface Props {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
}

const SCOPE_OPTIONS = [
  { value: 'personal' as const, label: 'Personal', icon: User, desc: 'Private to you' },
  { value: 'team' as const, label: 'Team', icon: Users, desc: 'Shared with team members' },
  { value: 'organization' as const, label: 'Organization', icon: Building2, desc: 'Shared across org (admin)' },
];

export function CreateWorkspaceDialog({ open, onClose, onCreated }: Props) {
  const user = useAuthStore((s) => s.user);
  const isAdmin = user?.orgRole === 'org_admin';

  const [name, setName] = useState('');
  const [slug, setSlug] = useState('');
  const [scope, setScope] = useState<'personal' | 'team' | 'organization'>('personal');
  const [teamId, setTeamId] = useState('');
  const [teams, setTeams] = useState<Team[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!open) return;
    setName('');
    setSlug('');
    setScope('personal');
    setTeamId('');
    setError('');
    // Load teams for team scope
    teamsApi.list().then(({ data }) => setTeams(Array.isArray(data) ? data : [])).catch(() => {});
  }, [open]);

  // Auto-generate slug
  useEffect(() => {
    setSlug(name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, ''));
  }, [name]);

  const handleSubmit = async () => {
    if (!name || !slug) return;
    if (scope === 'team' && !teamId) {
      setError('Please select a team');
      return;
    }
    setSaving(true);
    setError('');
    try {
      await adminWorkspacesApi.create({
        name,
        slug,
        scope,
        ...(scope === 'team' && { teamId }),
      });
      onCreated();
      onClose();
    } catch (err: any) {
      setError(err?.response?.data?.message || 'Failed to create workspace');
    } finally {
      setSaving(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-surface-800 border border-border-primary rounded-2xl p-6 w-full max-w-md animate-scale-in" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-semibold text-text-primary flex items-center gap-2">
            <FolderPlus className="w-5 h-5 text-accent-400" />
            Create Workspace
          </h2>
          <button onClick={onClose} className="text-text-muted hover:text-text-primary">
            <X className="w-5 h-5" />
          </button>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-sm text-red-400">
            {error}
          </div>
        )}

        <div className="space-y-4">
          {/* Scope selector */}
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-2">Type</label>
            <div className="grid grid-cols-3 gap-2">
              {SCOPE_OPTIONS.map((opt) => {
                const disabled = opt.value === 'organization' && !isAdmin;
                const Icon = opt.icon;
                return (
                  <button
                    key={opt.value}
                    disabled={disabled}
                    onClick={() => setScope(opt.value)}
                    className={`p-3 rounded-lg border text-center transition-all ${
                      scope === opt.value
                        ? 'border-accent-500/50 bg-accent-500/10'
                        : disabled
                          ? 'border-border-primary opacity-40 cursor-not-allowed'
                          : 'border-border-primary hover:border-border-secondary hover:bg-surface-700'
                    }`}
                  >
                    <Icon className={`w-4 h-4 mx-auto mb-1 ${scope === opt.value ? 'text-accent-400' : 'text-text-muted'}`} />
                    <div className={`text-xs font-medium ${scope === opt.value ? 'text-accent-400' : 'text-text-secondary'}`}>
                      {opt.label}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Team selector (only for team scope) */}
          {scope === 'team' && (
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-1">Team</label>
              <select
                value={teamId}
                onChange={(e) => setTeamId(e.target.value)}
                className="w-full bg-surface-900 border border-border-primary rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent-500"
              >
                <option value="">Select a team...</option>
                {teams.map((t) => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
            </div>
          )}

          {/* Name */}
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-1">Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="My Workspace"
              className="w-full bg-surface-900 border border-border-primary rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent-500"
            />
          </div>

          {/* Slug */}
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-1">Slug</label>
            <input
              type="text"
              value={slug}
              onChange={(e) => setSlug(e.target.value)}
              placeholder="my-workspace"
              className="w-full bg-surface-900 border border-border-primary rounded-lg px-3 py-2 text-sm text-text-primary font-mono focus:outline-none focus:ring-2 focus:ring-accent-500"
            />
          </div>

          {/* Actions */}
          <div className="flex gap-2 pt-2">
            <button
              onClick={handleSubmit}
              disabled={!name || !slug || saving}
              className="flex-1 flex items-center justify-center gap-1.5 px-4 py-2 bg-gradient-to-r from-accent-500 to-accent-600 text-white text-sm font-medium rounded-lg hover:from-accent-400 hover:to-accent-500 disabled:opacity-40 transition-all"
            >
              <FolderPlus className="w-4 h-4" />
              {saving ? 'Creating...' : 'Create'}
            </button>
            <button
              onClick={onClose}
              className="px-4 py-2 border border-border-primary text-text-secondary text-sm rounded-lg hover:bg-surface-700 transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
