import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { oidcApi } from '../api/oidc';
import { generateCodeVerifier, generateCodeChallenge } from '../lib/pkce';
import { Zap, Loader2, AlertCircle, LogIn } from 'lucide-react';

const VERIFIER_KEY = 'oidc_code_verifier';
const CONFIG_KEY = 'oidc_token_endpoint';

async function redirectToKeycloak() {
  const { data: config } = await oidcApi.getConfig();
  if (!config.enabled || !config.authEndpoint || !config.tokenEndpoint || !config.clientId) {
    throw new Error('SSO is not configured. Please contact your administrator.');
  }

  const verifier = generateCodeVerifier();
  const challenge = await generateCodeChallenge(verifier);

  sessionStorage.setItem(VERIFIER_KEY, verifier);
  sessionStorage.setItem(CONFIG_KEY, config.tokenEndpoint);

  const redirectUri = `${window.location.origin}/oidc/callback`;
  const params = new URLSearchParams({
    response_type: 'code',
    client_id: config.clientId,
    redirect_uri: redirectUri,
    scope: 'openid profile email',
    code_challenge: challenge,
    code_challenge_method: 'S256',
  });

  window.location.href = `${config.authEndpoint}?${params.toString()}`;
}

export function LoginPage() {
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [searchParams] = useSearchParams();
  const redirectingRef = useRef(false);

  // If user arrived here after logout, show the sign-in button instead of auto-redirecting
  const fromLogout = searchParams.get('logout') === '1';

  useEffect(() => {
    if (fromLogout) return;
    // Guard against StrictMode double-invoke: the second call would overwrite
    // the PKCE verifier in sessionStorage while the browser navigates with
    // the first verifier's challenge, causing a code_verifier mismatch.
    if (redirectingRef.current) return;
    redirectingRef.current = true;

    setLoading(true);
    redirectToKeycloak().catch(() => {
      redirectingRef.current = false;
      setError('Unable to reach authentication service.');
      setLoading(false);
    });
  }, [fromLogout]);

  const handleSignIn = () => {
    setLoading(true);
    setError(null);
    redirectToKeycloak().catch(() => {
      setError('Unable to reach authentication service.');
      setLoading(false);
    });
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface-950 relative overflow-hidden">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-accent-500/15 via-surface-950 to-surface-950" />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom_right,_var(--tw-gradient-stops))] from-highlight-600/10 via-transparent to-transparent" />

      <div className="relative z-10 w-full max-w-md mx-4 animate-scale-in">
        <div className="flex items-center justify-center gap-2.5 mb-8">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-accent-500 to-highlight-600 flex items-center justify-center shadow-lg shadow-accent-500/25">
            <Zap className="w-5 h-5 text-white" />
          </div>
          <span className="text-xl font-bold text-text-primary tracking-tight">RRAG Platform</span>
        </div>

        <div className="bg-surface-800/80 backdrop-blur-sm p-8 rounded-2xl border border-border-primary shadow-2xl shadow-black/30">
          {error ? (
            <div className="space-y-4">
              <div className="bg-red-500/10 border border-red-500/20 text-red-400 px-4 py-3 rounded-xl text-sm flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                {error}
              </div>
              <button
                onClick={handleSignIn}
                className="w-full flex items-center justify-center gap-2 bg-surface-700 hover:bg-surface-600 text-text-primary py-2.5 px-4 rounded-xl border border-border-primary transition-all font-medium"
              >
                <LogIn className="w-4 h-4" />
                Try Again
              </button>
            </div>
          ) : loading ? (
            <div className="flex flex-col items-center gap-3 py-4">
              <Loader2 className="w-6 h-6 animate-spin text-accent-400" />
              <p className="text-text-secondary text-sm">Redirecting to sign-in...</p>
            </div>
          ) : (
            <div className="space-y-4">
              <p className="text-text-secondary text-sm text-center">You have been signed out.</p>
              <button
                onClick={handleSignIn}
                className="w-full flex items-center justify-center gap-2 bg-gradient-to-r from-accent-500 to-accent-600 hover:from-accent-400 hover:to-accent-500 text-white py-2.5 px-4 rounded-xl transition-all font-medium"
              >
                <LogIn className="w-4 h-4" />
                Sign In
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
