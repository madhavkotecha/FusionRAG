import { create } from 'zustand';
import type { WorkspaceMembership } from '../types/auth';

const STORAGE_KEY = 'rrag_active_workspace';

interface WorkspaceState {
  workspaces: WorkspaceMembership[];
  activeWorkspaceId: string | null;
  setWorkspaces: (workspaces: WorkspaceMembership[]) => void;
  setActiveWorkspace: (id: string) => void;
  getActiveWorkspace: () => WorkspaceMembership | undefined;
}

export const useWorkspaceStore = create<WorkspaceState>((set, get) => ({
  workspaces: [],
  activeWorkspaceId: localStorage.getItem(STORAGE_KEY),

  setWorkspaces: (workspaces) => {
    set({ workspaces });
    const current = get().activeWorkspaceId;
    if (!current || !workspaces.find((w) => w.workspaceId === current)) {
      const first = workspaces[0]?.workspaceId ?? null;
      if (first) localStorage.setItem(STORAGE_KEY, first);
      else localStorage.removeItem(STORAGE_KEY);
      set({ activeWorkspaceId: first });
    }
  },

  setActiveWorkspace: (id) => {
    localStorage.setItem(STORAGE_KEY, id);
    set({ activeWorkspaceId: id });
  },

  getActiveWorkspace: () => {
    const { workspaces, activeWorkspaceId } = get();
    return workspaces.find((w) => w.workspaceId === activeWorkspaceId);
  },
}));
