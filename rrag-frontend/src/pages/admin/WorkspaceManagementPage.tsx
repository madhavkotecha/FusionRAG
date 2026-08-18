import { useEffect, useState, useCallback, useMemo } from 'react';
import { adminWorkspacesApi } from '../../api/admin';
import type { Workspace, WorkspaceMember } from '../../types/admin';
import { CreateWorkspaceDialog } from '../../components/workspaces/CreateWorkspaceDialog';
import {
  FolderOpen,
  Search,
  Users,
  Shield,
  UserPlus,
  UserMinus,
  X,
  MoreVertical,
  ChevronRight,
  Plus,
  User,
  UsersRound,
  Building2,
  Trash2,
} from 'lucide-react';

const SCOPE_BADGE = {
  personal: { label: 'Personal', icon: User, color: 'text-blue-400 bg-blue-500/10 border-blue-500/20' },
  team: { label: 'Team', icon: UsersRound, color: 'text-green-400 bg-green-500/10 border-green-500/20' },
  organization: { label: 'Org', icon: Building2, color: 'text-text-muted bg-surface-700 border-border-primary' },
} as const;

export function WorkspaceManagementPage() {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [members, setMembers] = useState<WorkspaceMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [selectedWs, setSelectedWs] = useState<string | null>(null);
  const [loadingMembers, setLoadingMembers] = useState(false);

  // Add member modal
  const [showAddMember, setShowAddMember] = useState(false);
  const [addUserId, setAddUserId] = useState('');
  const [addRole, setAddRole] = useState('developer');
  const [adding, setAdding] = useState(false);

  // Create workspace dialog
  const [showCreate, setShowCreate] = useState(false);

  const [openMenu, setOpenMenu] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await adminWorkspacesApi.list();
      const wsList = Array.isArray(data) ? data : [];
      setWorkspaces(wsList);
      if (!selectedWs && wsList.length > 0) {
        setSelectedWs(wsList[0].id);
      }
      setError('');
    } catch {
      setError('Failed to load workspaces');
    } finally {
      setLoading(false);
    }
  }, [selectedWs]);

  const loadMembers = useCallback(async (wsId: string) => {
    setLoadingMembers(true);
    try {
      const { data } = await adminWorkspacesApi.listMembers(wsId);
      setMembers(Array.isArray(data) ? data : []);
    } catch {
      setMembers([]);
    } finally {
      setLoadingMembers(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { if (selectedWs) loadMembers(selectedWs); }, [selectedWs, loadMembers]);

  const filteredMembers = useMemo(() => {
    if (!search) return members;
    const q = search.toLowerCase();
    return members.filter(
      (m) => m.name.toLowerCase().includes(q) || m.email.toLowerCase().includes(q),
    );
  }, [members, search]);

  const handleAddMember = async () => {
    if (!selectedWs || !addUserId) return;
    setAdding(true);
    try {
      await adminWorkspacesApi.addMember(selectedWs, addUserId, addRole);
      setShowAddMember(false);
      setAddUserId('');
      setAddRole('developer');
      await loadMembers(selectedWs);
    } catch {
      setError('Failed to add member');
    } finally {
      setAdding(false);
    }
  };

  const handleRoleChange = async (userId: string, currentRole: string) => {
    if (!selectedWs) return;
    const newRole = currentRole === 'admin' ? 'developer' : 'admin';
    if (!window.confirm(`Change role to ${newRole}?`)) return;
    try {
      await adminWorkspacesApi.updateMemberRole(selectedWs, userId, newRole);
      setOpenMenu(null);
      await loadMembers(selectedWs);
    } catch {
      setError('Failed to update member role');
    }
  };

  const handleRemoveMember = async (userId: string) => {
    if (!selectedWs) return;
    if (!window.confirm('Remove this member from the workspace?')) return;
    try {
      await adminWorkspacesApi.removeMember(selectedWs, userId);
      setOpenMenu(null);
      await loadMembers(selectedWs);
    } catch {
      setError('Failed to remove member');
    }
  };

  const handleDeleteWorkspace = async (wsId: string) => {
    if (!window.confirm('Delete this workspace? This cannot be undone.')) return;
    try {
      await adminWorkspacesApi.delete(wsId);
      if (selectedWs === wsId) {
        setSelectedWs(null);
        setMembers([]);
      }
      await load();
    } catch (err: any) {
      setError(err?.response?.data?.message || 'Failed to delete workspace');
    }
  };

  const selectedWorkspace = workspaces.find((w) => w.id === selectedWs);
  const scopeCfg = selectedWorkspace ? SCOPE_BADGE[selectedWorkspace.scope] : null;

  return (
    <div className="animate-fade-in">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-text-primary flex items-center gap-2">
            <FolderOpen className="w-5 h-5 text-highlight-400" />
            Workspace Management
          </h1>
          <p className="text-sm text-text-muted mt-0.5">Manage workspaces, members, and permissions</p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-1.5 px-4 py-2 bg-gradient-to-r from-accent-500 to-accent-600 text-white text-sm font-medium rounded-lg hover:from-accent-400 hover:to-accent-500 transition-all"
        >
          <Plus className="w-4 h-4" />
          Create Workspace
        </button>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-sm text-red-400 flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError('')}><X className="w-4 h-4" /></button>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Workspace List */}
        <div className="lg:col-span-1">
          <div className="bg-surface-800 rounded-xl border border-border-primary overflow-hidden">
            <div className="p-3 border-b border-border-primary">
              <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider">Workspaces</h3>
            </div>
            {loading ? (
              <div className="p-4 animate-pulse">
                {[1, 2].map((i) => <div key={i} className="h-12 bg-surface-700 rounded mb-2" />)}
              </div>
            ) : workspaces.length === 0 ? (
              <div className="p-6 text-center">
                <FolderOpen className="w-8 h-8 mx-auto text-text-muted mb-2 opacity-40" />
                <p className="text-sm text-text-muted">No workspaces</p>
              </div>
            ) : (
              <div className="p-2 space-y-1">
                {workspaces.map((ws) => {
                  const badge = SCOPE_BADGE[ws.scope];
                  const ScopeIcon = badge.icon;
                  return (
                    <button
                      key={ws.id}
                      onClick={() => setSelectedWs(ws.id)}
                      className={`w-full text-left px-3 py-3 rounded-lg transition-all flex items-center gap-3 ${
                        selectedWs === ws.id
                          ? 'bg-accent-500/10 border border-accent-500/30'
                          : 'hover:bg-surface-700 border border-transparent'
                      }`}
                    >
                      <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                        selectedWs === ws.id ? 'bg-accent-500/20' : 'bg-surface-700'
                      }`}>
                        <ScopeIcon className={`w-4 h-4 ${selectedWs === ws.id ? 'text-accent-400' : 'text-text-muted'}`} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className={`text-sm font-medium truncate ${
                          selectedWs === ws.id ? 'text-accent-400' : 'text-text-primary'
                        }`}>
                          {ws.name}
                        </p>
                        <div className="flex items-center gap-1.5 mt-0.5">
                          <span className="text-[10px] text-text-muted">{ws.slug}</span>
                          <span className={`text-[10px] px-1 py-0.5 rounded border ${badge.color}`}>
                            {badge.label}
                          </span>
                        </div>
                      </div>
                      <ChevronRight className={`w-4 h-4 shrink-0 ${selectedWs === ws.id ? 'text-accent-400' : 'text-text-muted'}`} />
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Workspace Details + Members */}
        <div className="lg:col-span-3">
          {selectedWorkspace && scopeCfg ? (
            <div className="space-y-4">
              {/* Workspace Info Card */}
              <div className="bg-surface-800 rounded-xl border border-border-primary p-5 animate-slide-up">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-highlight-500/20 to-accent-500/20 flex items-center justify-center">
                      <FolderOpen className="w-6 h-6 text-highlight-400" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h2 className="text-lg font-bold text-text-primary">{selectedWorkspace.name}</h2>
                        <span className={`inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded border ${scopeCfg.color}`}>
                          <scopeCfg.icon className="w-3 h-3" />
                          {scopeCfg.label}
                        </span>
                      </div>
                      <p className="text-xs text-text-muted font-mono">ID: {selectedWorkspace.id}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setShowAddMember(true)}
                      className="flex items-center gap-1.5 px-4 py-2 bg-gradient-to-r from-accent-500 to-accent-600 text-white text-sm font-medium rounded-lg hover:from-accent-400 hover:to-accent-500 transition-all"
                    >
                      <UserPlus className="w-4 h-4" />
                      Add Member
                    </button>
                    <button
                      onClick={() => handleDeleteWorkspace(selectedWorkspace.id)}
                      className="p-2 rounded-lg border border-red-500/20 text-red-400 hover:bg-red-500/10 transition-colors"
                      title="Delete workspace"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                {/* Quick Stats */}
                <div className="grid grid-cols-3 gap-3 mt-4 pt-4 border-t border-border-primary/50">
                  <div className="text-center">
                    <p className="text-lg font-bold text-text-primary">{members.length}</p>
                    <p className="text-xs text-text-muted">Members</p>
                  </div>
                  <div className="text-center">
                    <p className="text-lg font-bold text-text-primary">
                      {members.filter((m) => m.role === 'admin').length}
                    </p>
                    <p className="text-xs text-text-muted">Admins</p>
                  </div>
                  <div className="text-center">
                    <p className="text-lg font-bold text-text-primary">
                      {members.filter((m) => m.role === 'developer').length}
                    </p>
                    <p className="text-xs text-text-muted">Developers</p>
                  </div>
                </div>
              </div>

              {/* Members Table */}
              <div className="bg-surface-800 rounded-xl border border-border-primary overflow-hidden animate-slide-up" style={{ animationDelay: '50ms' }}>
                <div className="p-4 border-b border-border-primary flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-text-primary flex items-center gap-2">
                    <Users className="w-4 h-4 text-accent-400" />
                    Members
                  </h3>
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                    <input
                      type="text"
                      placeholder="Search members..."
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                      className="pl-9 pr-3 py-1.5 bg-surface-900 border border-border-primary rounded-lg text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent-500 w-56"
                    />
                  </div>
                </div>

                {loadingMembers ? (
                  <div className="p-8 animate-pulse">
                    <div className="space-y-3">
                      {[1, 2, 3].map((i) => <div key={i} className="h-10 bg-surface-700 rounded" />)}
                    </div>
                  </div>
                ) : filteredMembers.length === 0 ? (
                  <div className="text-center py-12">
                    <Users className="w-10 h-10 mx-auto text-text-muted mb-3 opacity-40" />
                    <p className="text-sm text-text-muted">
                      {search ? 'No members match your search' : 'No members in this workspace'}
                    </p>
                  </div>
                ) : (
                  <table className="w-full text-sm">
                    <thead className="bg-surface-900 border-b border-border-primary">
                      <tr>
                        <th className="text-left px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Member</th>
                        <th className="text-left px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Role</th>
                        <th className="text-left px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Joined</th>
                        <th className="text-right px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredMembers.map((member) => (
                        <tr key={member.userId} className="border-b border-border-primary last:border-0 hover:bg-surface-700/50 transition-colors">
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-3">
                              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-highlight-500/20 to-accent-500/20 flex items-center justify-center text-xs font-bold text-highlight-400">
                                {member.name.charAt(0).toUpperCase()}
                              </div>
                              <div>
                                <p className="text-text-primary font-medium">{member.name}</p>
                                <p className="text-xs text-text-muted">{member.email}</p>
                              </div>
                            </div>
                          </td>
                          <td className="px-4 py-3">
                            <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium ${
                              member.role === 'admin'
                                ? 'bg-violet-500/10 text-violet-400 border border-violet-500/20'
                                : 'bg-surface-700 text-text-secondary border border-border-primary'
                            }`}>
                              {member.role === 'admin' && <Shield className="w-3 h-3" />}
                              {member.role}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-text-muted text-xs">
                            {member.createdAt ? new Date(member.createdAt).toLocaleDateString() : '-'}
                          </td>
                          <td className="px-4 py-3 text-right relative">
                            <button
                              onClick={() => setOpenMenu(openMenu === member.userId ? null : member.userId)}
                              className="p-1.5 rounded-lg hover:bg-surface-700 text-text-muted hover:text-text-primary transition-colors"
                            >
                              <MoreVertical className="w-4 h-4" />
                            </button>
                            {openMenu === member.userId && (
                              <div className="absolute right-4 top-full mt-1 bg-surface-900 border border-border-primary rounded-xl shadow-xl z-20 py-1 min-w-[160px]">
                                <button
                                  onClick={() => handleRoleChange(member.userId, member.role)}
                                  className="w-full text-left px-4 py-2 text-sm text-text-secondary hover:bg-surface-800 hover:text-text-primary flex items-center gap-2"
                                >
                                  <Shield className="w-3.5 h-3.5" />
                                  {member.role === 'admin' ? 'Set as Developer' : 'Set as Admin'}
                                </button>
                                <button
                                  onClick={() => handleRemoveMember(member.userId)}
                                  className="w-full text-left px-4 py-2 text-sm text-red-400 hover:bg-red-500/10 flex items-center gap-2"
                                >
                                  <UserMinus className="w-3.5 h-3.5" />
                                  Remove Member
                                </button>
                              </div>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          ) : (
            <div className="text-center py-24 animate-slide-up">
              <FolderOpen className="w-12 h-12 mx-auto text-text-muted mb-4 opacity-40" />
              <p className="text-text-muted">Select a workspace to manage</p>
            </div>
          )}
        </div>
      </div>

      {/* Add Member Modal */}
      {showAddMember && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50" onClick={() => setShowAddMember(false)}>
          <div className="bg-surface-800 border border-border-primary rounded-2xl p-6 w-full max-w-md animate-scale-in" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-lg font-semibold text-text-primary flex items-center gap-2">
                <UserPlus className="w-5 h-5 text-accent-400" />
                Add Member
              </h2>
              <button onClick={() => setShowAddMember(false)} className="text-text-muted hover:text-text-primary">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-1">User ID or Email</label>
                <input
                  type="text"
                  value={addUserId}
                  onChange={(e) => setAddUserId(e.target.value)}
                  placeholder="user@example.com or user ID"
                  className="w-full bg-surface-900 border border-border-primary rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-1">Role</label>
                <select
                  value={addRole}
                  onChange={(e) => setAddRole(e.target.value)}
                  className="w-full bg-surface-900 border border-border-primary rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent-500"
                >
                  <option value="developer">Developer</option>
                  <option value="admin">Workspace Admin</option>
                </select>
              </div>
              <div className="flex gap-2 pt-2">
                <button
                  onClick={handleAddMember}
                  disabled={!addUserId || adding}
                  className="flex-1 flex items-center justify-center gap-1.5 px-4 py-2 bg-gradient-to-r from-accent-500 to-accent-600 text-white text-sm font-medium rounded-lg hover:from-accent-400 hover:to-accent-500 disabled:opacity-40 transition-all"
                >
                  <UserPlus className="w-4 h-4" />
                  {adding ? 'Adding...' : 'Add Member'}
                </button>
                <button
                  onClick={() => setShowAddMember(false)}
                  className="px-4 py-2 border border-border-primary text-text-secondary text-sm rounded-lg hover:bg-surface-700 transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Create Workspace Dialog */}
      <CreateWorkspaceDialog
        open={showCreate}
        onClose={() => setShowCreate(false)}
        onCreated={load}
      />
    </div>
  );
}
