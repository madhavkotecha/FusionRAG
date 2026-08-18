import { create } from 'zustand';
import type { User } from '../types/auth';

const STORAGE_KEY_ACCESS = 'kc_access_token';
const STORAGE_KEY_REFRESH = 'kc_refresh_token';

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: User | null;
  isAuthenticated: boolean;
  setAccessToken: (token: string) => void;
  setUser: (user: User) => void;
  login: (accessToken: string, refreshToken: string, user: User) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  accessToken: localStorage.getItem(STORAGE_KEY_ACCESS),
  refreshToken: localStorage.getItem(STORAGE_KEY_REFRESH),
  user: null,
  isAuthenticated: false,
  setAccessToken: (token) => {
    localStorage.setItem(STORAGE_KEY_ACCESS, token);
    set({ accessToken: token });
  },
  setUser: (user) => set({ user }),
  login: (accessToken, refreshToken, user) => {
    localStorage.setItem(STORAGE_KEY_ACCESS, accessToken);
    localStorage.setItem(STORAGE_KEY_REFRESH, refreshToken);
    set({ accessToken, refreshToken, user, isAuthenticated: true });
  },
  logout: () => {
    localStorage.removeItem(STORAGE_KEY_ACCESS);
    localStorage.removeItem(STORAGE_KEY_REFRESH);
    localStorage.removeItem('kc_id_token');
    set({ accessToken: null, refreshToken: null, user: null, isAuthenticated: false });
  },
}));
