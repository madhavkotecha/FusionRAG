/**
 * Token utilities. Only hash helper remains — Keycloak handles all JWT lifecycle.
 */

import crypto from "node:crypto";

export class TokenService {
  static hashToken(token: string): string {
    return crypto.createHash("sha256").update(token).digest("hex");
  }
}
