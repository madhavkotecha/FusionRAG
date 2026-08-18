import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { authApi } from '../api/auth';
import { useAuthStore } from '../stores/auth.store';
import { useWorkspaceStore } from '../stores/workspace.store';
import { AlertCircle, Loader2 } from 'lucide-react';

const VERIFIER_KEY = 'oidc_code_verifier';
const CONFIG_KEY = 'oidc_token_endpoint';

export function OidcCallbackPage() {
  const [error, setError] = useState<string | null>(null);
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  useEffect(() => {
    const code = searchParams.get('code');
    const kcError = searchParams.get('error');

    if (kcError) {
      setError(`Keycloak error: ${searchParams.get('error_description') || kcError}`);
      return;
    }

    if (!code) {
      setError('No authorization code received from Keycloak.');
      return;
    }

    const codeVerifier = sessionStorage.getItem(VERIFIER_KEY);
    const tokenEndpoint = sessionStorage.getItem(CONFIG_KEY);

    if (!codeVerifier || !tokenEndpoint) {
      setError('Missing PKCE state. Please try logging in again.');
      return;
    }

    let cancelled = false;

    (async () => {
      try {
        // Step 1: Exchange code for KC tokens (PKCE, public client)
        const redirectUri = `${window.location.origin}/oidc/callback`;
        const body = new URLSearchParams({
          grant_type: 'authorization_code',
          client_id: 'rrag-frontend',
          code,
          redirect_uri: redirectUri,
          code_verifier: codeVerifier,
        });

        const kcRes = await fetch(tokenEndpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: body.toString(),
        });

        if (!kcRes.ok) {
          const text = await kcRes.text();
          throw new Error(`Keycloak token exchange failed: ${text}`);
        }

        const kcTokens = await kcRes.json();
        if (cancelled) return;

        // Step 2: Store KC tokens immediately
        const store = useAuthStore.getState();
        store.setAccessToken(kcTokens.access_token);
        localStorage.setItem('kc_refresh_token', kcTokens.refresh_token);
        if (kcTokens.id_token) {
          localStorage.setItem('kc_id_token', kcTokens.id_token);
        }
        useAuthStore.setState({ refreshToken: kcTokens.refresh_token });

        // Cache the token endpoint for refresh
        sessionStorage.setItem('kc_token_endpoint', tokenEndpoint);

        // Step 3: Fetch profile from auth-server (auto-provisions user if needed)
        const { data: profile } = await authApi.getMe();
        if (cancelled) return;

        store.login(kcTokens.access_token, kcTokens.refresh_token, profile);
        useWorkspaceStore.getState().setWorkspaces(profile.workspaces);
        navigate('/', { replace: true });
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'SSO login failed.');
        }
      } finally {
        sessionStorage.removeItem(VERIFIER_KEY);
        sessionStorage.removeItem(CONFIG_KEY);
      }
    })();

    return () => { cancelled = true; };
  }, [searchParams, navigate]);

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-surface-950 px-4">
        <div className="max-w-md w-full space-y-4 text-center">
          <div className="bg-red-500/10 border border-red-500/20 text-red-400 px-4 py-3 rounded-xl text-sm flex items-center gap-2 justify-center">
            <AlertCircle className="w-4 h-4 shrink-0" />
            {error}
          </div>
          <button
            onClick={() => navigate('/login', { replace: true })}
            className="text-accent-400 hover:text-accent-300 font-medium transition-colors text-sm"
          >
            Back to Login
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface-950">
      <div className="flex items-center gap-3 text-text-secondary">
        <Loader2 className="w-5 h-5 animate-spin" />
        Completing sign-in...
      </div>
    </div>
  );
}
