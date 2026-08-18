import { useState, useRef, useEffect } from 'react';
import { useWorkspaceStore } from '../../stores/workspace.store';
import { User, Users, Building2, ChevronDown, Check, Layers } from 'lucide-react';

const SCOPE_CONFIG = {
  personal: { label: 'Personal', icon: User, color: 'text-blue-400' },
  team: { label: 'Team', icon: Users, color: 'text-green-400' },
  organization: { label: 'Organization', icon: Building2, color: 'text-text-muted' },
} as const;

interface WorkspaceSwitcherProps {
  collapsed: boolean;
}

export function WorkspaceSwitcher({ collapsed }: WorkspaceSwitcherProps) {
  const { workspaces, activeWorkspaceId, setActiveWorkspace } = useWorkspaceStore();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const active = workspaces.find((w) => w.workspaceId === activeWorkspaceId);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  const grouped = {
    personal: workspaces.filter((w) => w.scope === 'personal'),
    team: workspaces.filter((w) => w.scope === 'team'),
    organization: workspaces.filter((w) => w.scope === 'organization'),
  };

  const ActiveIcon = active ? SCOPE_CONFIG[active.scope].icon : Layers;

  if (collapsed) {
    return (
      <button
        onClick={() => setOpen(!open)}
        title={active?.workspaceName ?? 'Workspace'}
        className="flex items-center justify-center w-full py-2 rounded-lg text-text-muted hover:text-text-primary hover:bg-surface-800 transition-colors"
      >
        <ActiveIcon className="w-4 h-4" />
      </button>
    );
  }

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="w-full px-3 py-2 rounded-lg bg-surface-800/50 hover:bg-surface-800 transition-colors flex items-center gap-2 group"
      >
        <ActiveIcon className={`w-3.5 h-3.5 shrink-0 ${active ? SCOPE_CONFIG[active.scope].color : 'text-text-muted'}`} />
        <div className="flex-1 min-w-0 text-left">
          <div className="text-[10px] text-text-muted uppercase tracking-wider">Workspace</div>
          <div className="text-sm text-text-secondary truncate mt-0.5">
            {active?.workspaceName ?? 'Select...'}
          </div>
        </div>
        <ChevronDown className={`w-3.5 h-3.5 text-text-muted transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div className="absolute bottom-full mb-2 left-0 w-64 bg-surface-900 border border-border-primary rounded-xl shadow-2xl shadow-black/40 z-50 py-1 max-h-80 overflow-y-auto">
          {(['personal', 'team', 'organization'] as const).map((scope) => {
            const items = grouped[scope];
            if (items.length === 0) return null;
            const cfg = SCOPE_CONFIG[scope];
            const ScopeIcon = cfg.icon;

            return (
              <div key={scope}>
                <div className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-text-muted flex items-center gap-1.5">
                  <ScopeIcon className={`w-3 h-3 ${cfg.color}`} />
                  {cfg.label}
                </div>
                {items.map((ws) => (
                  <button
                    key={ws.workspaceId}
                    onClick={() => { setActiveWorkspace(ws.workspaceId); setOpen(false); }}
                    className={`w-full text-left px-3 py-2 text-sm flex items-center gap-2 transition-colors ${
                      ws.workspaceId === activeWorkspaceId
                        ? 'bg-accent-500/10 text-accent-400'
                        : 'text-text-secondary hover:bg-surface-800 hover:text-text-primary'
                    }`}
                  >
                    <span className="flex-1 truncate">{ws.workspaceName}</span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-700 text-text-muted shrink-0">
                      {ws.role}
                    </span>
                    {ws.workspaceId === activeWorkspaceId && (
                      <Check className="w-3.5 h-3.5 text-accent-400 shrink-0" />
                    )}
                  </button>
                ))}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
