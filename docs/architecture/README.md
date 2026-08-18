# Architecture Documentation

Comprehensive architecture documentation for the Agentic RAG System — a multi-tenant, microservices-based platform for building and executing visual RAG (Retrieval Augmented Generation) pipelines.

## Table of Contents

| Document | Description |
|----------|-------------|
| [Microservices Overview](./microservices-overview.md) | **Single-page reference** — all services, APIs, data stores, ports |
| [System Context](./01-system-context.md) | High-level overview, stakeholders, and external integrations (C4 Level 1) |
| [Container Architecture](./02-container-architecture.md) | Services, infrastructure, and deployment topology (C4 Level 2) |
| [Component Architecture](./03-component-architecture.md) | Internal module structure per service (C4 Level 3) |
| [Data Architecture](./04-data-architecture.md) | Database schemas, data flow, and storage strategies |
| [Security Architecture](./05-security-architecture.md) | Auth flows, RBAC, rate limiting, audit |
| [API Contracts](./06-api-contracts.md) | Complete API surface for all services |
| [Deployment Architecture](./07-deployment-architecture.md) | Docker, Traefik, networking, volumes, healthchecks |
| [Quality Attributes](./08-quality-attributes.md) | Performance, reliability, observability, scalability, DR |
| [Data Flow Diagrams](./09-data-flow-diagrams.md) | End-to-end flows for auth, ingestion, query, chat |
| [Evolution Roadmap](./10-evolution-roadmap.md) | Phased architecture evolution and tech debt register |
| [Interactive Viewer](./interactive-viewer.html) | Interactive architecture visualization (open in browser) |
| [ADRs](../adr/) | Architecture Decision Records (24 ADRs) |

## Quick Reference

### Tech Stack

| Layer | Technology |
|-------|-----------|
| API Gateway | Traefik v3.2 |
| Auth Service | Node.js 22 + Hono 4.6 + Drizzle ORM |
| Identity Provider | Keycloak 26 (OIDC + PKCE) |
| Pipeline Service | Python 3.12 + FastAPI + SQLAlchemy 2.0 |
| Ingestion Service | Python 3.12 + FastAPI + SQLAlchemy 2.0 + RQ |
| Frontend | React 19 + TypeScript + Vite 7 + Tailwind CSS 4 |
| Database | PostgreSQL 16 |
| Cache/Queue | Redis 7 |
| Knowledge Graph | Neo4j 5 Community |
| Object Storage | MinIO (S3-compatible) |
| Vector Database | Qdrant v1.13 |
| Search Engine | OpenSearch 2.17 |
| Visual Editor | XYFlow 12 + Monaco Editor |

### Port Map

| Port | Service |
|------|---------|
| 8000 | Traefik HTTP (public gateway) |
| 8443 | Traefik HTTPS |
| 8888 | Traefik dashboard |
| 3000 | Auth server (internal) |
| 8080 | Pipeline service (internal) |
| 8001 | Ingestion service (internal) |
| 5432 | PostgreSQL |
| 6381 | Redis |
| 7474 | Neo4j Browser |
| 7687 | Neo4j Bolt |
| 9000 | MinIO API |
| 9001 | MinIO Console |
| 9200 | OpenSearch |
| 6333 | Qdrant HTTP |
| 6334 | Qdrant gRPC |
| 8180 | Keycloak Admin |

### Traefik Route Map

| Path | Service | Auth Required |
|------|---------|---------------|
| `/auth/*` | auth-server | No |
| `/users/*` | auth-server | Yes |
| `/workspaces/*` | auth-server | Yes |
| `/teams/*` | auth-server | Yes |
| `/audit-logs/*` | auth-server | Yes |
| `/kc/*` | keycloak | No |
| `/api/v1/pipelines*` | pipeline-service | Yes |
| `/api/v1/runs*` | pipeline-service | Yes |
| `/api/v1/components*` | pipeline-service | Yes |
| `/api/v1/templates*` | pipeline-service | Yes |
| `/api/v1/ingestion*` | ingestion | Yes |
| `/` | frontend (nginx) | No |
