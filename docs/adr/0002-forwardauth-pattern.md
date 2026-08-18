# ADR-0002: Traefik ForwardAuth for Service Authentication

## Status

Accepted

## Context

Backend services (pipeline, ingestion) need to authenticate requests without duplicating JWT validation logic. Options include sharing a JWT library across services, service mesh with sidecar auth, or gateway-level authentication.

## Decision

Use Traefik's ForwardAuth middleware. For every protected route, Traefik calls `GET /auth/verify` on the auth server. The auth server validates the JWT (or API key), and returns user context as response headers:

- `X-Auth-User-Id`
- `X-Auth-Org-Id`
- `X-Auth-Org-Role`
- `X-Auth-Email`
- `X-Auth-Workspace-Roles` (JSON)

Downstream services read these headers via dependency injection and never handle JWT tokens directly.

## Consequences

**Positive:**
- Single source of truth for authentication logic
- Backend services don't need JWT libraries or shared secrets
- Easy to add new services — just configure Traefik labels
- API key auth works transparently (same header output)

**Negative:**
- Every authenticated request incurs an extra HTTP hop to the auth server
- Auth server becomes a critical path dependency
- Headers can be spoofed if services are accessed directly (mitigated by Docker network isolation)

## Alternatives Considered

1. **Shared JWT library**: Requires distributing the secret to all services
2. **Service mesh (Istio/Linkerd)**: Over-engineered for current scale
3. **JWT validation in each service**: Duplicated logic, harder to update
