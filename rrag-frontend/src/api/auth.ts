import client from './client';
import type { User } from '../types/auth';

export const authApi = {
  getMe: () => client.get<User>('/auth/me'),
};
