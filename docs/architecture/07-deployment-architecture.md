# 07 — Deployment Architecture

> Docker Compose topology, Traefik gateway, networking, volumes, healthchecks, and startup ordering.

---

## Deployment Model

The system runs as a **single-host Docker Compose** stack suitable for development and small-team production. All services share a bridge network (`rrag-net`) and communicate over internal DNS names.

**Production layout** — only ports 80 and 443 are exposed on the host. All infrastructure ports (5432, 6381, 7474, 8180, 9000, 9200, 6333, etc.) are internal only.

```
┌──────────────────────────────────────────────────────────────────┐
│  Host Machine (Production)                                       │
│                                                                  │
│  :80  ─► Traefik ─┬─► Frontend (Nginx :80)                      │
│  :443             │                                              │
│                   ├─► Auth Server (Hono :3000)                   │
│                   ├─► Pipeline Service (Uvicorn :8080)           │
│                   ├─► Ingestion Service (Uvicorn :8001)          │
│                   └─► Keycloak (:8080 internal)                  │
│                                                                  │
│  (all infrastructure ports internal — no host binding)           │
│  PostgreSQL :5432  │  MinIO :9000/:9001  │  OpenSearch :9200     │
│  Redis :6379       │  Neo4j :7474/:7687  │  Qdrant :6333/:6334   │
│  Keycloak :8080    │                                             │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

> **Dev overlay**: `docker-compose.dev.yml` re-adds host port bindings for all infrastructure services. See the [Development Workflow](#development-workflow) section.

---

## Container Inventory

| Container | Image | Exposed Port | Internal Port | Role |
|-----------|-------|-------------|---------------|------|
| `rrag-traefik` | traefik:v3.2 | 80, 443 | 80, 443, 8080 | API gateway / reverse proxy |
| `rrag-docker-socket-proxy` | tecnativa/docker-socket-proxy:0.3 | — | 2375 | Filtered Docker API proxy |
| `rrag-frontend` | custom (Node → Nginx) | — | 80 | SPA serving |
| `rrag-auth-server` | custom (Node 22) | — | 3000 | Auth, RBAC, user management |
| `rrag-pipeline-service` | custom (Python 3.12) | — | 8080 | Pipeline CRUD, execution |
| `rrag-ingestion` | custom (Python 3.12) | — | 8001 | Document ingestion, RAG query |
| `rrag-rq-worker` | custom (Python 3.12) | — | — | Background job processor |
| `rrag-postgres` | postgres:16-alpine | — | 5432 | Primary relational store |
| `rrag-redis` | redis:7-alpine | — | 6379 | Cache, queue, session store |
| `rrag-neo4j` | neo4j:5-community | — | 7474, 7687 | Knowledge graph |
| `rrag-minio` | minio/minio:latest | — | 9000, 9001 | S3-compatible object storage |
| `rrag-opensearch` | opensearch:2.17.0 | — | 9200 | Hybrid search (BM25 + vector) |
| `rrag-qdrant` | qdrant:v1.13.2 | — | 6333, 6334 | Vector database |
| `rrag-keycloak` | keycloak:26.0 | — | 8080 | OIDC identity provider |
| `rrag-keycloak-db` | postgres:16-alpine | — | 5432 | Keycloak persistence |

**Total: 15 containers**

---

## Traefik Gateway Configuration

Traefik acts as the single entry point (port 8000) and routes traffic based on path prefixes.

### Route Priority Map

| Priority | Path Prefix | Target Service | Auth Required |
|----------|-------------|----------------|---------------|
| 200 | `/api/v1/pipelines`, `/api/v1/runs`, `/api/v1/components`, `/api/v1/templates` | pipeline-service:8080 | Yes (ForwardAuth) |
| 200 | `/api/v1/ingestion` | ingestion:8001 | Yes (ForwardAuth) |
| 100 | `/auth` | auth-server:3000 | No |
| 100 | `/users` | auth-server:3000 | No (auth handled internally) |
| 100 | `/workspaces` | auth-server:3000 | No (auth handled internally) |
| 100 | `/teams` | auth-server:3000 | No (auth handled internally) |
| 100 | `/audit-logs` | auth-server:3000 | No (auth handled internally) |
| 100 | `/kc` | keycloak:8080 | No |
| 1 | `/` (catch-all) | frontend:80 | No |

### ForwardAuth Middleware

```yaml
# Defined on auth-server container labels
traefik.http.middlewares.auth-verify.forwardauth.address: http://auth-server:3000/auth/verify
traefik.http.middlewares.auth-verify.forwardauth.authResponseHeaders:
  - X-Auth-User-Id
  - X-Auth-Org-Id
  - X-Auth-Org-Role
  - X-Auth-Email
  - X-Auth-Workspace-Roles
  - X-Auth-Platform-Admin
```

```mermaid
sequenceDiagram
    participant Client
    participant Traefik
    participant AuthServer
    participant Upstream

    Client->>Traefik: GET /api/v1/pipelines
    Traefik->>AuthServer: GET /auth/verify (Forward headers)
    AuthServer->>AuthServer: Validate JWT / API key
    alt Valid
        AuthServer-->>Traefik: 200 + X-Auth-* headers
        Traefik->>Upstream: GET /api/v1/pipelines + X-Auth-*
        Upstream-->>Traefik: 200 Response
        Traefik-->>Client: 200 Response
    else Invalid
        AuthServer-->>Traefik: 401 Unauthorized
        Traefik-->>Client: 401 Unauthorized
    end
```

---

## Network Architecture

All containers connect to a single bridge network:

```mermaid
graph LR
    subgraph rrag-net [rrag-net bridge network]
        T[Traefik :80]
        DSP[Docker Socket Proxy :2375]
        F[Frontend :80]
        A[Auth Server :3000]
        P[Pipeline Service :8080]
        I[Ingestion :8001]
        W[RQ Worker]
        PG[PostgreSQL :5432]
        R[Redis :6379]
        N[Neo4j :7687]
        M[MinIO :9000]
        OS[OpenSearch :9200]
        QD[Qdrant :6333]
        KC[Keycloak :8080]
        KDB[Keycloak DB :5432]
    end

    T --> DSP
    T --> F
    T --> A
    T --> P
    T --> I
    T --> KC

    A --> PG
    A --> R
    A --> KC

    P --> PG

    I --> PG
    I --> R
    I --> N
    I --> M
    I --> OS
    I --> QD

    W --> R
    W --> N
    W --> M
    W --> OS
    W --> QD

    KC --> KDB
```

**DNS resolution**: Containers reference each other by service name (e.g., `postgres`, `redis`, `keycloak`).

---

## Volume Mounts

| Volume | Mount Point | Purpose |
|--------|------------|---------|
| `pgdata` | `/var/lib/postgresql/data` (postgres) | Application database persistence |
| `redisdata` | `/data` (redis) | Redis RDB/AOF persistence |
| `neo4jdata` | `/data` (neo4j) | Knowledge graph persistence |
| `ingestion_data` | `/data/documents` (ingestion, rq-worker) | Local document cache |
| `configs_data` | `/app/configs` (ingestion, rq-worker) | Pipeline YAML configs |
| `keycloak_pgdata` | `/var/lib/postgresql/data` (keycloak-db) | Keycloak database persistence |
| `minio_data` | `/data` (minio) | Object storage for documents |
| `opensearch_data` | `/usr/share/opensearch/data` (opensearch) | Search index data |
| `qdrant_data` | `/qdrant/storage` (qdrant) | Vector index storage |
| `acme_data` | `/acme` (traefik) | ACME certificate storage |

**Bind mounts:**

| Source | Target | Purpose |
|--------|--------|---------|
| `./rrag-auth-server/traefik/traefik.yml` | `/etc/traefik/traefik.yml` | Traefik static config |
| `./rrag-auth-server/traefik/dynamic` | `/etc/traefik/dynamic` | Traefik dynamic config directory |
| `./keycloak/rrag-realm.json` | `/opt/keycloak/data/import/rrag-realm.json` | Keycloak realm auto-import |

> The raw Docker socket (`/var/run/docker.sock`) is no longer bind-mounted into Traefik. It is replaced by the `docker-socket-proxy` container, which exposes only the read-only containers API on an internal TCP socket (`tcp://docker-socket-proxy:2375`).

---

## Healthcheck Configuration

Every service has a healthcheck. Traefik and Docker Compose use these to determine readiness.

| Service | Check Method | Interval | Timeout | Retries | Start Period |
|---------|-------------|----------|---------|---------|-------------|
| PostgreSQL | `pg_isready -U $USER` | 5s | 3s | 5 | — |
| Redis | `redis-cli ping` | 5s | 3s | 5 | — |
| Neo4j | Cypher `RETURN 1` | 10s | 10s | 10 | 60s |
| MinIO | `mc ready local` | 10s | 5s | 5 | 10s |
| OpenSearch | `curl http://localhost:9200/_cluster/health` | 15s | 10s | 20 | 90s |
| Qdrant | TCP check on port 6333 | 10s | 5s | 5 | 10s |
| Keycloak | TCP + HTTP 200 check on :9000 | 10s | 5s | 12 | 30s |
| Keycloak DB | `pg_isready -U keycloak` | 5s | 3s | 5 | — |
| Auth Server | `wget http://localhost:3000/health` | 10s | 5s | 3 | 10s |
| Pipeline Service | Python urllib `/health` | 10s | 5s | 3 | 10s |
| Ingestion | Python urllib `/health` | 10s | 5s | 3 | 15s |
| RQ Worker | Redis `PING` via Python | 15s | 5s | 3 | 10s |

---

## Startup Dependency Graph

```mermaid
graph TD
    PG[PostgreSQL] --> A[Auth Server]
    R[Redis] --> A
    KC_DB[Keycloak DB] --> KC[Keycloak]
    KC --> A

    PG --> P[Pipeline Service]

    PG --> I[Ingestion Service]
    R --> I
    N[Neo4j] --> I
    M[MinIO] --> I
    OS[OpenSearch] --> I
    QD[Qdrant] --> I

    R --> W[RQ Worker]
    N --> W
    M --> W
    OS --> W
    QD --> W

    A --> T{Traefik}
    P --> T
    I --> T
    F[Frontend] --> T
```

**Startup order** (determined by `depends_on` + `condition: service_healthy`):

1. **Infrastructure tier**: PostgreSQL, Redis, Neo4j, MinIO, OpenSearch, Qdrant, Keycloak DB (start in parallel)
2. **Identity tier**: Keycloak (waits for Keycloak DB)
3. **Service tier**: Auth Server (waits for PostgreSQL, Redis, Keycloak), Pipeline Service (waits for PostgreSQL), Ingestion + RQ Worker (wait for PostgreSQL, Redis, Neo4j, MinIO, OpenSearch, Qdrant)
4. **Gateway tier**: Traefik + Frontend (no explicit depends_on, but route to healthy backends)

---

## Build Pipeline

### Multi-Stage Docker Builds

All custom images use multi-stage builds to minimize image size:

**Auth Server (Node.js)**
```
Stage 1 (builder): node:22-alpine → npm ci → tsc compile
Stage 2 (runtime): node:22-alpine → copy dist/ + node_modules + drizzle migrations
CMD: node dist/index.js (runs Drizzle migrate on startup)
```

**Pipeline Service (Python)**
```
Single stage: python:3.12-slim → uv sync → copy src/ + alembic/
CMD: alembic upgrade head && uvicorn (runs migrations on startup)
```

**Ingestion Service (Python)**
```
Single stage: python:3.12-slim → uv pip install .[docker] → copy src/ + configs/
CMD: uvicorn (no migrations — uses Redis)
```

**Frontend (React)**
```
Stage 1 (builder): node:22-alpine → npm ci → npm run build (Vite)
Stage 2 (runtime): nginx:alpine → copy dist/ → serve via nginx.conf
```

---

## Environment Configuration (Production / Development)

The project uses a two-file compose strategy:

- **`docker-compose.yml`** — production-secure base: no host port bindings for infrastructure, TLS enabled, Keycloak in `start` mode, OpenSearch security plugin on, docker-socket-proxy in place of raw socket.
- **`docker-compose.dev.yml`** — dev overlay: re-adds host port bindings, relaxes security, enables hot-reload and debug tooling.

Copy the appropriate template before starting:

```bash
# Production
cp .env.prod.example .env

# Development
cp .env.dev.example .env
```

### Required Variables

| Variable | Example | Used By |
|----------|---------|---------|
| `POSTGRES_DB` | `rrag` | PostgreSQL |
| `POSTGRES_USER` | `rrag` | PostgreSQL |
| `POSTGRES_PASSWORD` | `change_me_strong_password` | PostgreSQL |
| `DATABASE_URL_DOCKER` | `postgresql://rrag:...@postgres:5432/rrag` | Auth Server |
| `DATABASE_URL_ASYNCPG` | `postgresql+asyncpg://rrag:...@postgres:5432/rrag` | Pipeline, Ingestion |
| `REDIS_PASSWORD` | `change_me_redis_password` | Redis, Auth Server, Ingestion |
| `REDIS_URL` | `redis://:password@redis:6379/0` | Auth Server |
| `REDIS_URL_INGESTION` | `redis://:password@redis:6379/1` | Ingestion, RQ Worker |
| `NEO4J_USERNAME` | `neo4j` | Neo4j, Ingestion, RQ Worker |
| `NEO4J_PASSWORD` | `change_me_neo4j_password` | Neo4j, Ingestion, RQ Worker |
| `NEO4J_URI` | `bolt://neo4j:7687` | Ingestion, RQ Worker |
| `OPENSEARCH_ADMIN_PASSWORD` | `change_me_os_password` | OpenSearch |
| `OPENSEARCH_USERNAME` | `admin` | Ingestion, RQ Worker |
| `OPENSEARCH_PASSWORD` | `change_me_os_password` | Ingestion, RQ Worker |
| `QDRANT_API_KEY` | `change_me_qdrant_key` | Qdrant, Ingestion, RQ Worker |
| `KC_CLIENT_SECRET` | `change_me_kc_secret` | Keycloak client, Auth Server |
| `CORS_ORIGINS` | `https://yourdomain.com` | Pipeline Service |
| `ENVIRONMENT` | `production` | Auth Server, Pipeline Service |
| `DOMAIN` | `yourdomain.com` | Traefik (ACME, routing) |
| `ACME_EMAIL` | `admin@yourdomain.com` | Traefik Let's Encrypt |
| `OPENAI_API_KEY` | `sk-...` | Ingestion, RQ Worker |

### Optional Variables (with defaults)

| Variable | Default | Used By |
|----------|---------|---------|
| `KC_DB_PASSWORD` | `keycloak_dev_password` | Keycloak DB |
| `KC_ADMIN_USER` | `admin` | Keycloak |
| `KC_ADMIN_PASSWORD` | `admin` | Keycloak |
| `RATE_LIMIT_UNAUTHENTICATED` | `20` | Auth Server |
| `RATE_LIMIT_AUTHENTICATED` | `300` | Auth Server |
| `RATE_LIMIT_API_KEY` | `600` | Auth Server |
| `MINIO_ROOT_USER` | `minioadmin` | MinIO, Ingestion, RQ Worker |
| `MINIO_ROOT_PASSWORD` | `minioadmin` | MinIO, Ingestion, RQ Worker |

---

## Scaling Considerations

### Current (Single-Host)

- All services run as single instances
- Redis serves dual roles: cache (DB 0) and job queue (DB 1)
- PostgreSQL shared between auth and pipeline services
- Suitable for development and teams up to ~20 users

### Future (Multi-Host)

| Component | Scaling Strategy |
|-----------|-----------------|
| Auth Server | Horizontal (stateless, JWT validation) |
| Pipeline Service | Horizontal (stateless, DB-backed) |
| Ingestion API | Horizontal (stateless) |
| RQ Workers | Horizontal (multiple workers per queue) |
| PostgreSQL | Vertical first, then read replicas |
| Redis | Redis Cluster or managed Redis |
| Neo4j | Neo4j Cluster (causal clustering) |
| MinIO | Distributed mode (multi-node, multi-drive) |
| OpenSearch | Multi-node cluster with sharding |
| Qdrant | Distributed mode with sharding + replication |
| Traefik | HA pair with shared config |

### Production Checklist

- [x] Replace Keycloak `start-dev` with `start` (production mode) — DONE
- [x] Enable TLS termination at Traefik — DONE (Let's Encrypt ACME)
- [x] Remove exposed debug ports from compose — DONE (prod has only 80/443)
- [x] Enable Traefik access logs — DONE (`accessLog` in `traefik.yml`)
- [ ] Use managed PostgreSQL (RDS, Cloud SQL)
- [ ] Use managed Redis (ElastiCache, Memorystore)
- [ ] Add resource limits (`deploy.resources`) to all containers
- [ ] Configure log aggregation (stdout → Loki/CloudWatch)
- [ ] Add backup strategy for PostgreSQL and Neo4j volumes
- [ ] Set `KC_HOSTNAME_STRICT=true` with proper domain

---

## Development Workflow

Development uses a Docker Compose overlay that relaxes production defaults:

```bash
# Copy dev environment template
cp .env.dev.example .env

# Start with dev overlay
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

The dev overlay (`docker-compose.dev.yml`):

- Re-adds host port bindings for all infrastructure services
- Sets `read_only: false` on all containers
- Mounts raw Docker socket (bypasses docker-socket-proxy)
- Uses `traefik-dev.yml` (HTTP, dashboard enabled, debug logging)
- Switches Keycloak to `start-dev --import-realm`
- Disables OpenSearch security plugin
- Points auth-server `KC_PUBLIC_REALM_URL` to `http://localhost:8000/kc/realms/rrag`
