import client from './client';

export interface OidcConfig {
  enabled: boolean;
  realmUrl?: string;
  clientId?: string;
  authEndpoint?: string;
  tokenEndpoint?: string;
  logoutEndpoint?: string;
}

export const oidcApi = {
  getConfig: () => client.get<OidcConfig>('/auth/oidc/config'),
};
