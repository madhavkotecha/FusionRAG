import { useEffect, useState, useCallback, useMemo } from 'react';
import { adminUsersApi } from '../../api/admin';
import type { AdminUser } from '../../types/admin';
import {
  Users,
  Plus,
  Search,
  Shield,
  UserCheck,
  UserX,
  X,
  Mail,
  MoreVertical,
  Crown,
} from 'lucide-react';

export function UserManagementPage() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [showInvite, setShowInvite] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState('member');
  const [inviting, setInviting] = useState(false);
  const [openMenu, setOpenMenu] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await adminUsersApi.list();
      setUsers(Array.isArray(data) ? data : []);
      setError('');
    } catch {
      setError('Failed to load users');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const filtered = useMemo(() => {
    let result = users;
    if (search) {
      const q = search.toLowerCase();
      result = result.filter(
        (u) => u.name.toLowerCase().includes(q) || u.email.toLowerCase().includes(q),
      );
    }
    if (roleFilter) result = result.filter((u) => u.orgRole === roleFilter);
    if (statusFilter) result = result.filter((u) => u.status === statusFilter);
    return result;
  }, [users, search, roleFilter, statusFilter]);

  const handleInvite = async () => {
    if (!inviteEmail) return;
    setInviting(true);
    try {
      await adminUsersApi.invite({ email: inviteEmail, role: inviteRole });
      setShowInvite(false);
      setInviteEmail('');
      setInviteRole('member');
      await load();
    } catch {
      setError('Failed to send invitation');
    } finally {
      setInviting(false);
    }
  };

  const handleRoleChange = async (userId: string, currentRole: string) => {
    const newRole = currentRole === 'org_admin' ? 'member' : 'org_admin';
    if (!window.confirm(`Change role to ${newRole}?`)) return;
    try {
      await adminUsersApi.updateRole(userId, newRole);
      setOpenMenu(null);
      await load();
    } catch {
      setError('Failed to update role');
    }
  };

  const handleStatusChange = async (userId: string, currentStatus: string) => {
    const newStatus = currentStatus === 'active' ? 'suspended' : 'active';
    if (!window.confirm(`${newStatus === 'suspended' ? 'Suspend' : 'Activate'} this user?`)) return;
    try {
      await adminUsersApi.updateStatus(userId, newStatus as 'active' | 'suspended');
      setOpenMenu(null);
      await load();
    } catch {
      setError('Failed to update status');
    }
  };

  return (
    <div className="animate-fade-in">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-text-primary">User Management</h1>
          <p className="text-sm text-text-muted mt-0.5">{users.length} total users</p>
        </div>
        <button
          onClick={() => setShowInvite(true)}
          className="flex items-center gap-1.5 px-4 py-2 bg-gradient-to-r from-accent-500 to-accent-600 text-white text-sm font-medium rounded-lg hover:from-accent-400 hover:to-accent-500 transition-all"
        >
          <Plus className="w-4 h-4" />
          Invite User
        </button>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-sm text-red-400 flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError('')}><X className="w-4 h-4" /></button>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-5">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
          <input
            type="text"
            placeholder="Search by name or email..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-2 bg-surface-900 border border-border-primary rounded-lg text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent-500"
          />
        </div>
        <select
          value={roleFilter}
          onChange={(e) => setRoleFilter(e.target.value)}
          className="bg-surface-900 border border-border-primary rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent-500"
        >
          <option value="">All Roles</option>
          <option value="member">Member</option>
          <option value="org_admin">Org Admin</option>
        </select>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="bg-surface-900 border border-border-primary rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent-500"
        >
          <option value="">All Status</option>
          <option value="active">Active</option>
          <option value="suspended">Suspended</option>
        </select>
      </div>

      {/* Users Table */}
      {loading ? (
        <div className="bg-surface-800 rounded-xl border border-border-primary p-8">
          <div className="animate-pulse space-y-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="flex gap-4">
                <div className="h-4 bg-surface-700 rounded w-1/4" />
                <div className="h-4 bg-surface-700 rounded w-1/3" />
                <div className="h-4 bg-surface-700 rounded w-16" />
                <div className="h-4 bg-surface-700 rounded w-16" />
              </div>
            ))}
          </div>
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16 animate-slide-up">
          <Users className="w-12 h-12 mx-auto text-text-muted mb-4 opacity-40" />
          <p className="text-text-muted">{search || roleFilter || statusFilter ? 'No users match your filters' : 'No users found'}</p>
        </div>
      ) : (
        <div className="bg-surface-800 rounded-xl border border-border-primary overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-surface-900 border-b border-border-primary">
              <tr>
                <th className="text-left px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">User</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Role</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Status</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Last Login</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Joined</th>
                <th className="text-right px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((user) => (
                <tr key={user.id} className="border-b border-border-primary last:border-0 hover:bg-surface-700/50 transition-colors">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-gradient-to-br from-accent-500/20 to-highlight-500/20 flex items-center justify-center text-xs font-bold text-accent-400">
                        {user.name.charAt(0).toUpperCase()}
                      </div>
                      <div>
                        <p className="text-text-primary font-medium">{user.name}</p>
                        <p className="text-xs text-text-muted">{user.email}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium ${
                        user.orgRole === 'org_admin'
                          ? 'bg-violet-500/10 text-violet-400 border border-violet-500/20'
                          : 'bg-surface-700 text-text-secondary border border-border-primary'
                      }`}
                    >
                      {user.orgRole === 'org_admin' && <Crown className="w-3 h-3" />}
                      {user.orgRole === 'org_admin' ? 'Admin' : 'Member'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium ${
                        user.status === 'active'
                          ? 'bg-emerald-500/10 text-emerald-400'
                          : 'bg-red-500/10 text-red-400'
                      }`}
                    >
                      {user.status === 'active' ? <UserCheck className="w-3 h-3" /> : <UserX className="w-3 h-3" />}
                      {user.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-text-muted text-xs">
                    {user.lastLoginAt ? new Date(user.lastLoginAt).toLocaleDateString() : 'Never'}
                  </td>
                  <td className="px-4 py-3 text-text-muted text-xs">
                    {new Date(user.createdAt).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3 text-right relative">
                    <button
                      onClick={() => setOpenMenu(openMenu === user.id ? null : user.id)}
                      className="p-1.5 rounded-lg hover:bg-surface-700 text-text-muted hover:text-text-primary transition-colors"
                    >
                      <MoreVertical className="w-4 h-4" />
                    </button>
                    {openMenu === user.id && (
                      <div className="absolute right-4 top-full mt-1 bg-surface-900 border border-border-primary rounded-xl shadow-xl z-20 py-1 min-w-[160px]">
                        <button
                          onClick={() => handleRoleChange(user.id, user.orgRole)}
                          className="w-full text-left px-4 py-2 text-sm text-text-secondary hover:bg-surface-800 hover:text-text-primary flex items-center gap-2"
                        >
                          <Shield className="w-3.5 h-3.5" />
                          {user.orgRole === 'org_admin' ? 'Demote to Member' : 'Promote to Admin'}
                        </button>
                        <button
                          onClick={() => handleStatusChange(user.id, user.status)}
                          className={`w-full text-left px-4 py-2 text-sm flex items-center gap-2 ${
                            user.status === 'active'
                              ? 'text-red-400 hover:bg-red-500/10'
                              : 'text-emerald-400 hover:bg-emerald-500/10'
                          }`}
                        >
                          {user.status === 'active' ? <UserX className="w-3.5 h-3.5" /> : <UserCheck className="w-3.5 h-3.5" />}
                          {user.status === 'active' ? 'Suspend User' : 'Activate User'}
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Invite Modal */}
      {showInvite && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50" onClick={() => setShowInvite(false)}>
          <div className="bg-surface-800 border border-border-primary rounded-2xl p-6 w-full max-w-md animate-scale-in" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-lg font-semibold text-text-primary flex items-center gap-2">
                <Mail className="w-5 h-5 text-accent-400" />
                Invite User
              </h2>
              <button onClick={() => setShowInvite(false)} className="text-text-muted hover:text-text-primary">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-1">Email Address</label>
                <input
                  type="email"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  placeholder="user@example.com"
                  className="w-full bg-surface-900 border border-border-primary rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-1">Role</label>
                <select
                  value={inviteRole}
                  onChange={(e) => setInviteRole(e.target.value)}
                  className="w-full bg-surface-900 border border-border-primary rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent-500"
                >
                  <option value="member">Member</option>
                  <option value="org_admin">Organization Admin</option>
                </select>
              </div>
              <div className="flex gap-2 pt-2">
                <button
                  onClick={handleInvite}
                  disabled={!inviteEmail || inviting}
                  className="flex-1 flex items-center justify-center gap-1.5 px-4 py-2 bg-gradient-to-r from-accent-500 to-accent-600 text-white text-sm font-medium rounded-lg hover:from-accent-400 hover:to-accent-500 disabled:opacity-40 transition-all"
                >
                  <Mail className="w-4 h-4" />
                  {inviting ? 'Sending...' : 'Send Invitation'}
                </button>
                <button
                  onClick={() => setShowInvite(false)}
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
