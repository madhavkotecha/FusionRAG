/**
 * Keycloak JWT validation using JWKS (RS256).
 * Validates tokens against Keycloak's public keys fetched from the JWKS endpoint.
 */

import { createRemoteJWKSet, jwtVerify, type JWTPayload } from "jose";
import { config } from "../config.js";

export interface KcTokenClaims {
  sub: string;
  email: string;
  email_verified?: boolean;
  name?: string;
  preferred_username?: string;
  given_name?: string;
  family_name?: string;
  realm_access?: { roles: string[] };
}

let jwks: ReturnType<typeof createRemoteJWKSet> | null = null;

function getJwks() {
  if (!jwks) {
    const jwksUrl = new URL(
      `${config.kcRealmUrl}/protocol/openid-connect/certs`,
    );
    jwks = createRemoteJWKSet(jwksUrl);
  }
  return jwks;
}

/**
 * Validate a Keycloak-issued JWT and return its claims.
 * Verifies signature via JWKS, checks issuer.
 */
export async function validateKcToken(token: string): Promise<KcTokenClaims> {
  // Accept both internal and public realm URLs as valid issuers.
  // Keycloak sets `iss` based on the request origin — tokens obtained through
  // the public proxy (Traefik) carry the public URL, not the internal Docker one.
  const issuers = [config.kcRealmUrl];
  if (config.kcPublicRealmUrl && config.kcPublicRealmUrl !== config.kcRealmUrl) {
    issuers.push(config.kcPublicRealmUrl);
  }

  const { payload } = await jwtVerify(token, getJwks(), {
    issuer: issuers,
  });

  const claims = payload as JWTPayload & KcTokenClaims;

  if (!claims.email) {
    throw new Error("KC token missing email claim");
  }

  return {
    sub: claims.sub!,
    email: claims.email,
    email_verified: claims.email_verified,
    name: claims.name,
    preferred_username: claims.preferred_username,
    given_name: claims.given_name,
    family_name: claims.family_name,
    realm_access: claims.realm_access,
  };
}

/** Reset JWKS cache (useful for testing or key rotation). */
export function resetJwksCache() {
  jwks = null;
}
