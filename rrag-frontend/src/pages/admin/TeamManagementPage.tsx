import { useEffect, useState, useCallback, useMemo } from 'react';
import { teamsApi } from '../../api/teams';
import { adminUsersApi } from '../../api/admin';
import { useAuthStore } from '../../stores/auth.store';
import type { Team, TeamMember, AdminUser } from '../../types/admin';
import {
  UsersRound,
  Search,
  UserPlus,
  UserMinus,
  X,
  MoreVertical,
  ChevronRight,
  Plus,
  Pencil,
  Trash2,
  Crown,
} from 'lucide-react';

export function TeamManagementPage() {
  const user = useAuthStore((s) => s.user);
  const isAdmin = user?.orgRole === 'org_admin';

  const [teams, setTeams] = useState<Team[]>([]);
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [allUsers, setAllUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [selectedTeamId, setSelectedTeamId] = useState<string | null>(null);
  const [loadingMembers, setLoadingMembers] = useState(false);

  // Create/edit team modal
  const [showTeamModal, setShowTeamModal] = useState(false);
  const [editingTeam, setEditingTeam] = useState<Team | null>(null);
  const [teamName, setTeamName] = useState('');
  const [teamSlug, setTeamSlug] = useState('');
  const [teamDesc, setTeamDesc] = useState('');
  const [savingTeam, setSavingTeam] = useState(false);

  // Add member modal
  const [showAddMember, setShowAddMember] = useState(false);
  const [addUserId, setAddUserId] = useState('');
  const [addRole, setAddRole] = useState<'member' | 'lead'>('member');
  const [adding, setAdding] = useState(false);

  const [openMenu, setOpenMenu] = useState<string | null>(null);

  const loadTeams = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await teamsApi.list();
      setTeams(Array.isArray(data) ? data : []);
      setError('');
    } catch {
      setError('Failed to load teams');
    } finally {
      setLoading(false);
    }
  }, []);

  const loadMembers = useCallback(async (teamId: string) => {
    setLoadingMembers(true);
    try {
      const { data } = await teamsApi.listMembers(teamId);
      setMembers(Array.isArray(data) ? data : []);
    } catch {
      setMembers([]);
    } finally {
      setLoadingMembers(false);
    }
  }, []);

  const loadUsers = useCallback(async () => {
    try {
      const { data } = await adminUsersApi.list();
      setAllUsers(Array.isArray(data) ? data : []);
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => { loadTeams(); loadUsers(); }, [loadTeams, loadUsers]);
  useEffect(() => { if (selectedTeamId) loadMembers(selectedTeamId); }, [selectedTeamId, loadMembers]);

  const selectedTeam = teams.find((t) => t.id === selectedTeamId);

  const filteredMembers = useMemo(() => {
    if (!search) return members;
    const q = search.toLowerCase();
    return members.filter(
      (m) => m.name.toLowerCase().includes(q) || m.email.toLowerCase().includes(q),
    );
  }, [members, search]);

  // Auto-generate slug from name
  const updateTeamName = (val: string) => {
    setTeamName(val);
    if (!editingTeam) {
      setTeamSlug(val.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, ''));
    }
  };

  const openCreateModal = () => {
    setEditingTeam(null);
    setTeamName('');
    setTeamSlug('');
    setTeamDesc('');
    setShowTeamModal(true);
  };

  const openEditModal = (team: Team) => {
    setEditingTeam(team);
    setTeamName(team.name);
    setTeamSlug(team.slug);
    setTeamDesc(team.description || '');
    setShowTeamModal(true);
  };

  const handleSaveTeam = async () => {
    if (!teamName || !teamSlug) return;
    setSavingTeam(true);
    setError('');
    try {
      if (editingTeam) {
        await teamsApi.update(editingTeam.id, {
          name: teamName,
          description: teamDesc || null,
        });
      } else {
        await teamsApi.create({
          name: teamName,
          slug: teamSlug,
          description: teamDesc || undefined,
        });
      }
      setShowTeamModal(false);
      await loadTeams();
    } catch (err: any) {
      setError(err?.response?.data?.message || `Failed to ${editingTeam ? 'update' : 'create'} team`);
    } finally {
      setSavingTeam(false);
    }
  };

  const handleDeleteTeam = async (teamId: string) => {
    if (!window.confirm('Delete this team? This cannot be undone.')) return;
    try {
      await teamsApi.delete(teamId);
      if (selectedTeamId === teamId) {
        setSelectedTeamId(null);
        setMembers([]);
      }
      await loadTeams();
    } catch (err: any) {
      setError(err?.response?.data?.message || 'Failed to delete team');
    }
  };

  const handleAddMember = async () => {
    if (!selectedTeamId || !addUserId) return;
    setAdding(true);
    try {
      await teamsApi.addMember(selectedTeamId, addUserId, addRole);
      setShowAddMember(false);
      setAddUserId('');
      setAddRole('member');
      await loadMembers(selectedTeamId);
    } catch (err: any) {
      setError(err?.response?.data?.message || 'Failed to add member');
    } finally {
      setAdding(false);
    }
  };

  const handleRoleChange = async (userId: string, currentRole: string) => {
    if (!selectedTeamId) return;
    const newRole = currentRole === 'lead' ? 'member' : 'lead';
    if (!window.confirm(`Change role to ${newRole}?`)) return;
    try {
      await teamsApi.updateMemberRole(selectedTeamId, userId, newRole);
      setOpenMenu(null);
      await loadMembers(selectedTeamId);
    } catch {
      setError('Failed to update member role');
    }
  };

  const handleRemoveMember = async (userId: string) => {
    if (!selectedTeamId) return;
    if (!window.confirm('Remove this member from the team?')) return;
    try {
      await teamsApi.removeMember(selectedTeamId, userId);
      setOpenMenu(null);
      await loadMembers(selectedTeamId);
    } catch {
      setError('Failed to remove member');
    }
  };

  // Users not already in the selected team
  const availableUsers = allUsers.filter(
    (u) => !members.some((m) => m.userId === u.id),
  );

  return (
    <div className="animate-fade-in">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-text-primary flex items-center gap-2">
            <UsersRound className="w-5 h-5 text-green-400" />
            Team Management
          </h1>
          <p className="text-sm text-text-muted mt-0.5">Create teams and manage team members</p>
        </div>
        {isAdmin && (
          <button
            onClick={openCreateModal}
            className="flex items-center gap-1.5 px-4 py-2 bg-gradient-to-r from-accent-500 to-accent-600 text-white text-sm font-medium rounded-lg hover:from-accent-400 hover:to-accent-500 transition-all"
          >
            <Plus className="w-4 h-4" />
            Create Team
          </button>
        )}
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-sm text-red-400 flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError('')}><X className="w-4 h-4" /></button>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Team List */}
        <div className="lg:col-span-1">
          <div className="bg-surface-800 rounded-xl border border-border-primary overflow-hidden">
            <div className="p-3 border-b border-border-primary">
              <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider">Teams</h3>
            </div>
            {loading ? (
              <div className="p-4 animate-pulse">
                {[1, 2].map((i) => <div key={i} className="h-12 bg-surface-700 rounded mb-2" />)}
              </div>
            ) : teams.length === 0 ? (
              <div className="p-6 text-center">
                <UsersRound className="w-8 h-8 mx-auto text-text-muted mb-2 opacity-40" />
                <p className="text-sm text-text-muted">No teams yet</p>
              </div>
            ) : (
              <div className="p-2 space-y-1">
                {teams.map((team) => (
                  <button
                    key={team.id}
                    onClick={() => setSelectedTeamId(team.id)}
                    className={`w-full text-left px-3 py-3 rounded-lg transition-all flex items-center gap-3 ${
                      selectedTeamId === team.id
                        ? 'bg-accent-500/10 border border-accent-500/30'
                        : 'hover:bg-surface-700 border border-transparent'
                    }`}
                  >
                    <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                      selectedTeamId === team.id ? 'bg-green-500/20' : 'bg-surface-700'
                    }`}>
                      <UsersRound className={`w-4 h-4 ${selectedTeamId === team.id ? 'text-green-400' : 'text-text-muted'}`} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className={`text-sm font-medium truncate ${
                        selectedTeamId === team.id ? 'text-accent-400' : 'text-text-primary'
                      }`}>
                        {team.name}
                      </p>
                      <p className="text-xs text-text-muted">{team.slug}</p>
                    </div>
                    <ChevronRight className={`w-4 h-4 ${selectedTeamId === team.id ? 'text-accent-400' : 'text-text-muted'}`} />
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Team Details + Members */}
        <div className="lg:col-span-3">
          {selectedTeam ? (
            <div className="space-y-4">
              {/* Team Info Card */}
              <div className="bg-surface-800 rounded-xl border border-border-primary p-5 animate-slide-up">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-green-500/20 to-accent-500/20 flex items-center justify-center">
                      <UsersRound className="w-6 h-6 text-green-400" />
                    </div>
                    <div>
                      <h2 className="text-lg font-bold text-text-primary">{selectedTeam.name}</h2>
                      <p className="text-xs text-text-muted font-mono">{selectedTeam.slug}</p>
                      {selectedTeam.description && (
                        <p className="text-xs text-text-secondary mt-1">{selectedTeam.description}</p>
                      )}
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
                    {isAdmin && (
                      <>
                        <button
                          onClick={() => openEditModal(selectedTeam)}
                          className="p-2 rounded-lg border border-border-primary text-text-muted hover:text-text-primary hover:bg-surface-700 transition-colors"
                          title="Edit team"
                        >
                          <Pencil className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleDeleteTeam(selectedTeam.id)}
                          className="p-2 rounded-lg border border-red-500/20 text-red-400 hover:bg-red-500/10 transition-colors"
                          title="Delete team"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </>
                    )}
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
                      {members.filter((m) => m.role === 'lead').length}
                    </p>
                    <p className="text-xs text-text-muted">Leads</p>
                  </div>
                  <div className="text-center">
                    <p className="text-lg font-bold text-text-primary">
                      {members.filter((m) => m.role === 'member').length}
                    </p>
                    <p className="text-xs text-text-muted">Members</p>
                  </div>
                </div>
              </div>

              {/* Members Table */}
              <div className="bg-surface-800 rounded-xl border border-border-primary overflow-hidden animate-slide-up" style={{ animationDelay: '50ms' }}>
                <div className="p-4 border-b border-border-primary flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-text-primary flex items-center gap-2">
                    <UsersRound className="w-4 h-4 text-green-400" />
                    Team Members
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
                    <UsersRound className="w-10 h-10 mx-auto text-text-muted mb-3 opacity-40" />
                    <p className="text-sm text-text-muted">
                      {search ? 'No members match your search' : 'No members in this team'}
                    </p>
                  </div>
                ) : (
                  <table className="w-full text-sm">
                    <thead className="bg-surface-900 border-b border-border-primary">
                      <tr>
                        <th className="text-left px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Member</th>
                        <th className="text-left px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Role</th>
                        <th className="text-left px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Added</th>
                        <th className="text-right px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredMembers.map((member) => (
                        <tr key={member.userId} className="border-b border-border-primary last:border-0 hover:bg-surface-700/50 transition-colors">
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-3">
                              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-green-500/20 to-accent-500/20 flex items-center justify-center text-xs font-bold text-green-400">
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
                              member.role === 'lead'
                                ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                                : 'bg-surface-700 text-text-secondary border border-border-primary'
                            }`}>
                              {member.role === 'lead' && <Crown className="w-3 h-3" />}
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
                                  <Crown className="w-3.5 h-3.5" />
                                  {member.role === 'lead' ? 'Set as Member' : 'Set as Lead'}
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
              <UsersRound className="w-12 h-12 mx-auto text-text-muted mb-4 opacity-40" />
              <p className="text-text-muted">Select a team to manage</p>
            </div>
          )}
        </div>
      </div>

      {/* Create/Edit Team Modal */}
      {showTeamModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50" onClick={() => setShowTeamModal(false)}>
          <div className="bg-surface-800 border border-border-primary rounded-2xl p-6 w-full max-w-md animate-scale-in" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-lg font-semibold text-text-primary flex items-center gap-2">
                <UsersRound className="w-5 h-5 text-green-400" />
                {editingTeam ? 'Edit Team' : 'Create Team'}
              </h2>
              <button onClick={() => setShowTeamModal(false)} className="text-text-muted hover:text-text-primary">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-1">Name</label>
                <input
                  type="text"
                  value={teamName}
                  onChange={(e) => updateTeamName(e.target.value)}
                  placeholder="Engineering"
                  className="w-full bg-surface-900 border border-border-primary rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent-500"
                />
              </div>
              {!editingTeam && (
                <div>
                  <label className="block text-sm font-medium text-text-secondary mb-1">Slug</label>
                  <input
                    type="text"
                    value={teamSlug}
                    onChange={(e) => setTeamSlug(e.target.value)}
                    placeholder="engineering"
                    className="w-full bg-surface-900 border border-border-primary rounded-lg px-3 py-2 text-sm text-text-primary font-mono focus:outline-none focus:ring-2 focus:ring-accent-500"
                  />
                </div>
              )}
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-1">Description</label>
                <textarea
                  value={teamDesc}
                  onChange={(e) => setTeamDesc(e.target.value)}
                  placeholder="Optional team description..."
                  rows={2}
                  className="w-full bg-surface-900 border border-border-primary rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent-500 resize-none"
                />
              </div>
              <div className="flex gap-2 pt-2">
                <button
                  onClick={handleSaveTeam}
                  disabled={!teamName || (!editingTeam && !teamSlug) || savingTeam}
                  className="flex-1 flex items-center justify-center gap-1.5 px-4 py-2 bg-gradient-to-r from-accent-500 to-accent-600 text-white text-sm font-medium rounded-lg hover:from-accent-400 hover:to-accent-500 disabled:opacity-40 transition-all"
                >
                  {savingTeam ? 'Saving...' : editingTeam ? 'Save Changes' : 'Create Team'}
                </button>
                <button
                  onClick={() => setShowTeamModal(false)}
                  className="px-4 py-2 border border-border-primary text-text-secondary text-sm rounded-lg hover:bg-surface-700 transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Add Member Modal */}
      {showAddMember && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50" onClick={() => setShowAddMember(false)}>
          <div className="bg-surface-800 border border-border-primary rounded-2xl p-6 w-full max-w-md animate-scale-in" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-lg font-semibold text-text-primary flex items-center gap-2">
                <UserPlus className="w-5 h-5 text-accent-400" />
                Add Team Member
              </h2>
              <button onClick={() => setShowAddMember(false)} className="text-text-muted hover:text-text-primary">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-1">User</label>
                <select
                  value={addUserId}
                  onChange={(e) => setAddUserId(e.target.value)}
                  className="w-full bg-surface-900 border border-border-primary rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent-500"
                >
                  <option value="">Select a user...</option>
                  {availableUsers.map((u) => (
                    <option key={u.id} value={u.id}>{u.name} ({u.email})</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-1">Role</label>
                <select
                  value={addRole}
                  onChange={(e) => setAddRole(e.target.value as 'member' | 'lead')}
                  className="w-full bg-surface-900 border border-border-primary rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent-500"
                >
                  <option value="member">Member</option>
                  <option value="lead">Lead</option>
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
    </div>
  );
}
