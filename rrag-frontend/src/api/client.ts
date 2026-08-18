import axios from 'axios';
import { useAuthStore } from '../stores/auth.store';
import { useWorkspaceStore } from '../stores/workspace.store';

const client = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '',
});

/** Routes that should receive the active workspace_id query param */
const WORKSPACE_SCOPED_PREFIXES = ['/api/v1/pipelines', '/api/v1/ingestion'];

client.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  // Inject active workspace_id for pipeline/ingestion calls
  const url = config.url || '';
  if (WORKSPACE_SCOPED_PREFIXES.some((p) => url.startsWith(p))) {
    const params = config.params ?? {};
    if (!params.workspace_id) {
      const wsId = useWorkspaceStore.getState().activeWorkspaceId;
      if (wsId) {
        config.params = { ...params, workspace_id: wsId };
      }
    }
  }

  return config;
});

let isRefreshing = false;
let failedQueue: Array<{ resolve: (token: string | null) => void; reject: (error: unknown) => void }> = [];

const processQueue = (error: unknown, token: string | null) => {
  failedQueue.forEach((prom) => {
    if (error) prom.reject(error);
    else prom.resolve(token);
  });
  failedQueue = [];
};

/**
 * Refresh KC tokens using the Keycloak token endpoint.
 * Uses the stored KC refresh_token with grant_type=refresh_token.
 */
async function refreshKcTokens(): Promise<{ access_token: string; refresh_token: string; id_token?: string }> {
  const refreshToken = useAuthStore.getState().refreshToken;
  if (!refreshToken) throw new Error('No refresh token');

  // Fetch KC token endpoint from OIDC config (cached in sessionStorage for perf)
  let tokenEndpoint = sessionStorage.getItem('kc_token_endpoint');
  if (!tokenEndpoint) {
    const baseURL = import.meta.env.VITE_API_URL || '';
    const { data } = await axios.get(`${baseURL}/auth/oidc/config`);
    if (!data.enabled || !data.tokenEndpoint) throw new Error('OIDC not configured');
    tokenEndpoint = data.tokenEndpoint;
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

client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise<string | null>((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then((token) => {
          originalRequest.headers.Authorization = `Bearer ${token}`;
          return client(originalRequest);
        });
      }
      originalRequest._retry = true;
      isRefreshing = true;
      try {
        const kcTokens = await refreshKcTokens();
        const store = useAuthStore.getState();
        store.setAccessToken(kcTokens.access_token);
        // Update refresh token + id_token in store + localStorage
        localStorage.setItem('kc_refresh_token', kcTokens.refresh_token);
        if (kcTokens.id_token) {
          localStorage.setItem('kc_id_token', kcTokens.id_token);
        }
        useAuthStore.setState({ refreshToken: kcTokens.refresh_token });

        processQueue(null, kcTokens.access_token);
        originalRequest.headers.Authorization = `Bearer ${kcTokens.access_token}`;
        return client(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        useAuthStore.getState().logout();
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }
    return Promise.reject(error);
  }
);

export default client;
