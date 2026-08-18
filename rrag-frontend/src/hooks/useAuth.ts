import { useAuthStore } from '../stores/auth.store';
import { oidcApi } from '../api/oidc';

export function useAuth() {
  const { logout: clearAuth, user, isAuthenticated } = useAuthStore();

  const handleLogout = async () => {
    // Grab id_token before clearing state — Keycloak needs it to end the session
    const idToken = localStorage.getItem('kc_id_token');

    // Redirect to Keycloak logout endpoint (terminates KC session)
    try {
      const { data: config } = await oidcApi.getConfig();
      if (config.enabled && config.logoutEndpoint) {
        const params = new URLSearchParams({
          client_id: config.clientId || 'rrag-frontend',
          post_logout_redirect_uri: window.location.origin + '/login?logout=1',
        });
        if (idToken) {
          params.set('id_token_hint', idToken);
        }

        // Clear local state, then redirect to KC logout
        clearAuth();
        sessionStorage.removeItem('kc_token_endpoint');
        window.location.href = `${config.logoutEndpoint}?${params.toString()}`;
        return;
      }
    } catch {
      // If config fetch fails, just clear and redirect to login
    }

    clearAuth();
    sessionStorage.removeItem('kc_token_endpoint');
    window.location.href = '/login?logout=1';
  };

  return {
    user,
    isAuthenticated,
    logout: handleLogout,
  };
}
