import { NavLink } from 'react-router-dom';
import { useAuthStore } from '../../stores/auth.store';
import { WorkspaceSwitcher } from './WorkspaceSwitcher';
import {
  LayoutDashboard,
  FileText,
  GitBranch,
  PlayCircle,
  Database,
  Zap,
  MessageSquare,
  Search,
  PanelLeftClose,
  PanelLeftOpen,
  Shield,
  Users,
  Layers,
  Key,
  ScrollText,
  Settings,
  Activity,
  FolderOpen,
  UsersRound,
  Puzzle,
  Rocket,
} from 'lucide-react';

type NavItem = { to: string; icon: typeof LayoutDashboard; label: string; end: boolean };
type NavSection = { label: string; items: NavItem[]; adminOnly?: boolean };

const NAV_SECTIONS: NavSection[] = [
  {
    label: 'General',
    items: [
      { to: '/', icon: LayoutDashboard, label: 'Dashboard', end: true },
      { to: '/chat', icon: MessageSquare, label: 'Chat', end: false },
      { to: '/publish', icon: Rocket, label: 'Publish', end: false },
    ],
  },
  {
    label: 'Pipelines',
    items: [
      { to: '/ingestion/documents', icon: FileText, label: 'Documents', end: false },
      { to: '/ingestion/datastores', icon: Database, label: 'Knowledge Stores', end: false },
      { to: '/ingestion/pipelines', icon: GitBranch, label: 'Pipelines', end: false },
      { to: '/ingestion/jobs', icon: PlayCircle, label: 'Jobs', end: true },
      { to: '/query-pipelines', icon: Search, label: 'Query Pipelines', end: false },
      { to: '/components', icon: Puzzle, label: 'Components', end: false },
    ],
  },
  {
    label: 'Administration',
    adminOnly: true,
    items: [
      { to: '/admin', icon: Shield, label: 'Overview', end: true },
      { to: '/admin/users', icon: Users, label: 'Users', end: false },
      { to: '/admin/teams', icon: UsersRound, label: 'Teams', end: false },
      { to: '/admin/workspaces', icon: FolderOpen, label: 'Workspaces', end: false },
      { to: '/admin/queue', icon: Layers, label: 'Queue', end: false },
      { to: '/admin/api-keys', icon: Key, label: 'API Keys', end: false },
      { to: '/admin/audit-logs', icon: ScrollText, label: 'Audit Logs', end: false },
      { to: '/admin/health', icon: Activity, label: 'Health', end: false },
      { to: '/admin/settings', icon: Settings, label: 'Settings', end: false },
      { to: '/admin/components', icon: Puzzle, label: 'Manage Components', end: false },
    ],
  },
];

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const user = useAuthStore((s) => s.user);
  const isAdmin = user?.orgRole === 'org_admin' || user?.isPlatformAdmin === true;

  const visibleSections = NAV_SECTIONS.filter(
    (section) => !section.adminOnly || isAdmin,
  );

  return (
    <aside
      className={`bg-surface-900 border-r border-border-primary flex flex-col shrink-0 transition-all duration-200 ${
        collapsed ? 'w-16' : 'w-60'
      }`}
    >
      {/* Brand */}
      <div className="px-3 py-5 border-b border-border-primary flex items-center justify-between">
        <div className={`flex items-center gap-2.5 ${collapsed ? 'justify-center w-full' : ''}`}>
          <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-accent-500 to-highlight-600 flex items-center justify-center shrink-0 shadow-lg shadow-accent-500/25">
            <Zap className="w-4 h-4 text-white" />
          </div>
          {!collapsed && (
            <div>
              <h1 className="text-sm font-bold text-text-primary tracking-tight">RRAG Platform</h1>
              <p className="text-[10px] text-text-muted">RAG Experimentation Platform</p>
            </div>
          )}
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-2 space-y-5 overflow-y-auto">
        {visibleSections.map((section) => (
          <div key={section.label}>
            {!collapsed && (
              <div className={`px-3 mb-2 text-[10px] font-semibold uppercase tracking-widest ${
                section.adminOnly ? 'text-orange-400/70' : 'text-text-muted'
              }`}>
                {section.label}
              </div>
            )}
            <div className="space-y-0.5">
              {section.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  title={collapsed ? item.label : undefined}
                  className={({ isActive }) =>
                    `relative flex items-center ${collapsed ? 'justify-center' : ''} gap-2.5 px-3 py-2 text-sm rounded-lg transition-all duration-150 ${
                      isActive
                        ? section.adminOnly
                          ? 'bg-orange-500/10 text-orange-400 font-medium'
                          : 'bg-accent-500/10 text-accent-400 font-medium'
                        : 'text-text-secondary hover:bg-surface-800 hover:text-text-primary'
                    }`
                  }
                >
                  <item.icon className="w-4 h-4 shrink-0" />
                  {!collapsed && <span>{item.label}</span>}
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </nav>

      {/* Collapse toggle + Workspace */}
      <div className="p-2 border-t border-border-primary space-y-2">
        <WorkspaceSwitcher collapsed={collapsed} />
        <button
          onClick={onToggle}
          className="flex items-center justify-center w-full py-2 rounded-lg text-text-muted hover:text-text-primary hover:bg-surface-800 transition-colors"
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? <PanelLeftOpen className="w-4 h-4" /> : <PanelLeftClose className="w-4 h-4" />}
        </button>
      </div>
    </aside>
  );
}
