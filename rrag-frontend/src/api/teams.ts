import client from './client';
import type { Team, TeamMember } from '../types/admin';

export const teamsApi = {
  list: () => client.get<Team[]>('/teams'),

  create: (data: { name: string; slug: string; description?: string }) =>
    client.post<Team>('/teams', data),

  get: (teamId: string) => client.get<Team>(`/teams/${teamId}`),

  update: (teamId: string, data: { name?: string; description?: string | null }) =>
    client.put<Team>(`/teams/${teamId}`, data),

  delete: (teamId: string) => client.delete(`/teams/${teamId}`),

  listMembers: (teamId: string) =>
    client.get<TeamMember[]>(`/teams/${teamId}/members`),

  addMember: (teamId: string, userId: string, role: string) =>
    client.post(`/teams/${teamId}/members`, { userId, role }),

  updateMemberRole: (teamId: string, userId: string, role: string) =>
    client.put(`/teams/${teamId}/members/${userId}`, { role }),

  removeMember: (teamId: string, userId: string) =>
    client.delete(`/teams/${teamId}/members/${userId}`),
};
