/**
 * OIDC routes — returns public Keycloak configuration for the frontend.
 * Token exchange and login routes removed (frontend exchanges directly with KC).
 */

import { Hono } from "hono";
import type { AppEnv } from "../types.js";
import { config } from "../config.js";

export const oidcRoutes = new Hono<AppEnv>();

// ── GET /auth/oidc/config — Public endpoint returning OIDC config ───────
oidcRoutes.get("/config", (c) => {
  if (!config.kcRealmUrl) {
    return c.json({ enabled: false }, 200);
  }
  const publicUrl = config.kcPublicRealmUrl || config.kcRealmUrl;
  return c.json({
    enabled: true,
    realmUrl: publicUrl,
    clientId: "rrag-frontend",
    authEndpoint: `${publicUrl}/protocol/openid-connect/auth`,
    tokenEndpoint: `${publicUrl}/protocol/openid-connect/token`,
    logoutEndpoint: `${publicUrl}/protocol/openid-connect/logout`,
  });
});
