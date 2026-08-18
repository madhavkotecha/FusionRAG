import { useAuth } from '../../hooks/useAuth';
import { useThemeStore } from '../../stores/theme.store';
import { LogOut, Sun, Moon } from 'lucide-react';

export function Header() {
  const { user, logout } = useAuth();
  const { theme, toggle: toggleTheme } = useThemeStore();

  const initials = user?.name
    ? user.name
        .split(' ')
        .map((n) => n[0])
        .join('')
        .slice(0, 2)
        .toUpperCase()
    : '?';

  return (
    <header className="h-14 bg-surface-900/80 backdrop-blur-sm border-b border-border-primary flex items-center justify-between px-6">
      <div />
      <div className="flex items-center gap-3">
        <button
          onClick={toggleTheme}
          aria-label="Toggle theme"
          className="p-2 rounded-lg text-text-muted hover:text-text-primary hover:bg-surface-800 transition-colors"
        >
          {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
        </button>
        {user && (
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-full bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center text-[10px] font-bold text-white">
              {initials}
            </div>
            <span className="text-sm text-text-secondary">
              {user.name}
            </span>
          </div>
        )}
        <button
          onClick={logout}
          className="flex items-center gap-1.5 text-sm text-text-muted hover:text-text-primary px-2.5 py-1.5 rounded-lg hover:bg-surface-800 transition-colors"
        >
          <LogOut className="w-3.5 h-3.5" />
          Logout
        </button>
      </div>
    </header>
  );
}
