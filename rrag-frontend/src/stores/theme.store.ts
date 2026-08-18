import { create } from 'zustand';

type Theme = 'dark' | 'light';

const STORAGE_KEY = 'rrag_theme';

interface ThemeState {
  theme: Theme;
  toggle: () => void;
}

function applyTheme(theme: Theme) {
  document.documentElement.classList.toggle('light', theme === 'light');
}

function getStoredTheme(): Theme {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === 'light' || stored === 'dark') return stored;
  return 'dark';
}

export const useThemeStore = create<ThemeState>((set, get) => ({
  theme: getStoredTheme(),
  toggle: () => {
    const next = get().theme === 'dark' ? 'light' : 'dark';
    localStorage.setItem(STORAGE_KEY, next);
    applyTheme(next);
    set({ theme: next });
  },
}));

// Apply on module load so the class is set before first render
applyTheme(getStoredTheme());
