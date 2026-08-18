export interface WorkspaceMembership {
  workspaceId: string;
  workspaceName: string;
  workspaceSlug: string;
  scope: 'personal' | 'team' | 'organization';
  role: string;
}

export interface User {
  id: string;
  email: string;
  name: string;
  orgId: string;
  orgRole: string;
  isPlatformAdmin?: boolean;
  status: string;
  createdAt: string;
  workspaces: WorkspaceMembership[];
}
