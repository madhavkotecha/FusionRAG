import { useEffect, useState } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '../../stores/auth.store';
import { useWorkspaceStore } from '../../stores/workspace.store';
import { authApi } from '../../api/auth';

/**
 * Refresh KC tokens using the stored refresh token.
 * Returns the new access token, or throws on failure.
 */
async function refreshKcTokens(): Promise<{ access_token: string; refresh_token: string }> {
  const refreshToken = useAuthStore.getState().refreshToken;
  if (!refreshToken) throw new Error('No refresh token');

  let tokenEndpoint = sessionStorage.getItem('kc_token_endpoint');
  if (!tokenEndpoint) {
    // Fetch from OIDC config
    const baseURL = import.meta.env.VITE_API_URL || '';
    const res = await fetch(`${baseURL}/auth/oidc/config`);
    const config = await res.json();
    if (!config.enabled || !config.tokenEndpoint) throw new Error('OIDC not configured');
    tokenEndpoint = config.tokenEndpoint;
    sessionStorage.setItem('kc_token_endpoint', tokenEndpoint!);
  }

  const body = new URLSearchParams({
    grant_type: 'refresh_token',
    client_id: 'rrag-frontend',
    refresh_token: refreshToken,
  });

  const res = await fetch(tokenEndpoint!, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: body.toString(),
  });

  if (!res.ok) throw new Error('Token refresh failed');
  return res.json();
}

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const location = useLocation();
  const [checking, setChecking] = useState(!isAuthenticated);

  useEffect(() => {
    if (isAuthenticated) return;

    let cancelled = false;

    const tryRecover = async () => {
      try {
        const kcTokens = await refreshKcTokens();
        if (cancelled) return;

        const store = useAuthStore.getState();
        store.setAccessToken(kcTokens.access_token);
        localStorage.setItem('kc_refresh_token', kcTokens.refresh_token);
        useAuthStore.setState({ refreshToken: kcTokens.refresh_token });

        const { data: profile } = await authApi.getMe();
        if (cancelled) return;

        store.login(kcTokens.access_token, kcTokens.refresh_token, profile);
        useWorkspaceStore.getState().setWorkspaces(profile.workspaces);
      } catch {
        useAuthStore.getState().logout();
      } finally {
        if (!cancelled) setChecking(false);
      }
    };

    tryRecover();
    return () => { cancelled = true; };
  }, [isAuthenticated]);

  if (checking) {
    return (
      <div className="flex items-center justify-center h-screen bg-surface-950">
        <div className="text-text-muted text-sm animate-fade-in">Restoring session...</div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  return <>{children}</>;
}
