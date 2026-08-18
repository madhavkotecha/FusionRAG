# ADR-0025: Production Security Hardening

- **Status:** Accepted
- **Date:** 2026-03-11
- **Deciders:** Architecture Team
- **Relates to:** ADR-0006 (Technology Choices), ADR-0023 (Ingestion Persistence Migration)

## Context

The system ran in development mode with relaxed security defaults throughout its build-out phase:

- **HTTP only**: Traefik served plaintext HTTP with no TLS termination
- **Exposed infrastructure ports**: PostgreSQL (5432), Redis (6379), Neo4j (7474/7687), Qdrant (6333), OpenSearch (9200), Keycloak (8080), MinIO (9000/9001) all bound to `0.0.0.0`
- **Hardcoded credentials**: Database passwords, API keys, and service secrets were committed as defaults in `docker-compose.yml` and service configs
- **Raw Docker socket**: Traefik mounted `/var/run/docker.sock` directly, giving it (and any exploit targeting it) full daemon access
- **Keycloak dev mode**: Running `start-dev`, which disables TLS enforcement and enables the development console
- **No security headers**: No CSP, HSTS, X-Frame-Options, or X-Content-Type-Options on any service
- **Unauthenticated infrastructure**: Redis, Qdrant, and OpenSearch accepted connections without credentials; Neo4j auth was disabled

This was acceptable during rapid prototyping but blocked production deployment and represented significant attack surface for any internet-facing host.

## Decision

Implement comprehensive security hardening guided by a **"secure by default"** philosophy: `docker-compose.yml` becomes the production-ready baseline, and development work requires an explicit overlay (`docker-compose.dev.yml`). Security is opt-out for production, not opt-in.

### 1. TLS — Let's Encrypt via Traefik ACME

- Production: HTTP-01 challenge via Traefik's built-in ACME resolver; certificates stored in a named volume
- Staging/internal: Separate Traefik static config (`traefik.staging.yml`) using self-signed certificates
- All HTTP traffic redirected to HTTPS via Traefik `redirectScheme` middleware
- `ACME_EMAIL` environment variable required; no default provided

### 2. Docker Socket Proxy

Replace the raw `/var/run/docker.sock` mount on Traefik with a [Tecnativa docker-socket-proxy](https://github.com/Tecnativa/docker-socket-proxy) sidecar:

- Proxy exposes only `CONTAINERS=1` and `NETWORKS=1` endpoints (read-only)
- All other Docker API endpoints blocked by default
- Traefik connects to `tcp://socket-proxy:2375` instead of the raw socket
- Raw socket never leaves the `socket-proxy` container

### 3. Container Hardening

All service containers receive:

```yaml
read_only: true
security_opt:
  - no-new-privileges:true
cap_drop:
  - ALL
```

Containers that require writable paths use `tmpfs` mounts (e.g., `/tmp`, `/var/run`, application cache directories) rather than relaxing `read_only`.

Capabilities are added back only where strictly required (e.g., `NET_BIND_SERVICE` for services binding to ports < 1024).

### 4. Infrastructure Authentication

| Service | Mechanism |
|---------|-----------|
| Redis | `--requirepass $REDIS_PASSWORD` |
| Qdrant | `QDRANT__SERVICE__API_KEY` env var |
| OpenSearch | Security plugin enabled; auth without internal TLS (`plugins.security.ssl.http.enabled: false`) |
| Neo4j | `NEO4J_AUTH=neo4j/$NEO4J_PASSWORD` |
| PostgreSQL | Existing `POSTGRES_PASSWORD` — no change, already required |

All credentials are parameterized via environment variables; no hardcoded defaults remain in compose or config files.

### 5. Credential Management

- `.env.prod.example` template lists every required variable with descriptions and no default values
- Services use `os.environ["KEY"]` (fail-fast) rather than `os.environ.get("KEY", "default")` for security-critical variables
- `.env.prod` added to `.gitignore`; only the example template is committed
- Docker Compose `env_file: .env.prod` replaces inline `environment:` blocks for secrets

### 6. CORS

- Wildcard `CORS_ORIGINS=*` removed from all services
- Each service reads `CORS_ORIGINS` from environment at startup
- Production value: the single public frontend origin
- Development overlay sets `CORS_ORIGINS=*` to restore previous behavior

### 7. Security Headers

**Frontend (nginx)**:
- `Content-Security-Policy`: restrictive default-src with explicit allowlists for scripts, styles, fonts, and API origins
- `X-Frame-Options: DENY`
- `X-Content-Type-Options: nosniff`
- `Strict-Transport-Security: max-age=63072000; includeSubDomains; preload`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: geolocation=(), microphone=(), camera=()`

**API services (pipeline-service, ingestion, auth-server)**:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`

Headers applied at the application layer (FastAPI/Hono middleware) so they are present regardless of whether Traefik is in front.

### 8. Keycloak Production Mode

- Switch from `start-dev` to `start` command
- `sslRequired: "external"` in realm config (enforces HTTPS for non-localhost clients)
- Test users (`testuser@rrag.io`) removed from committed realm export
- `KC_HOSTNAME` and `KC_HOSTNAME_ADMIN` set explicitly; no wildcard hostname inference

### 9. Port Exposure

**Production `docker-compose.yml`**: only ports 80 and 443 published (Traefik ingress).

**Development overlay (`docker-compose.dev.yml`)** re-adds all infrastructure ports:

| Service | Port |
|---------|------|
| PostgreSQL | 5432 |
| Redis | 6379 |
| Neo4j | 7474, 7687 |
| Qdrant | 6333 |
| OpenSearch | 9200 |
| Keycloak | 8080 |
| MinIO | 9000, 9001 |

## Consequences

### Positive

- Production deployment is secure by default; no manual hardening checklist required
- Raw Docker socket never exposed to Traefik — lateral movement from a Traefik exploit is contained
- All infrastructure services require authentication — unauthenticated access eliminated
- TLS end-to-end for all browser traffic; HSTS preloading available after initial deployment
- Container `read_only` + `no-new-privileges` limits damage from RCE exploits inside containers
- Security headers block clickjacking, MIME sniffing, and unintended cross-origin access

### Negative

- **Development workflow change**: `docker compose up` no longer works alone; must use `docker compose -f docker-compose.yml -f docker-compose.dev.yml up`
- **No defaults for secrets**: First deployment requires filling out `.env.prod` completely — partial configs fail fast at startup rather than silently using weak defaults
- **`read_only` compatibility**: Some containers required `tmpfs` investigation to identify all writable paths; new service additions must be audited
- **One additional container**: `socket-proxy` sidecar adds a process but this is a net reduction in attack surface

### Neutral

- Self-signed staging config available for internal or CI deployments without public DNS
- Existing Keycloak realm data requires a one-time migration to remove test users and set `sslRequired`
- Redis connection strings across all services must be updated to include the password (connection URL format: `redis://:$REDIS_PASSWORD@redis:6379/0`)

## Alternatives Considered

### Alternative 1: Dev-first, harden later (prod overlay)

- Description: Keep current `docker-compose.yml` as the dev baseline; add a `docker-compose.prod.yml` overlay for hardening
- Rejected because: Too easy to accidentally deploy the insecure baseline to a public host. The "secure by default" inversion ensures a cold deployment is safe without additional steps.

### Alternative 2: Secrets manager (Vault / SOPS)

- Description: Use HashiCorp Vault or Mozilla SOPS for secret distribution instead of `.env` files
- Rejected because: Adds significant operational complexity for a single-host Docker Compose deployment. The `.env.prod` pattern is sufficient for the current deployment model. Vault/SOPS can be layered on top later without changing service code (secrets are still env vars).

### Alternative 3: httpOnly cookie migration for Keycloak tokens

- Description: Move KC access/refresh tokens from `localStorage` to `httpOnly` cookies to eliminate XSS token theft risk
- Deferred: Requires significant frontend refactoring and a Traefik cookie-injection middleware to forward tokens as `Authorization` headers to backend services. Tracked as a future hardening item; current CSP and short token TTLs reduce the localStorage risk in the interim.
