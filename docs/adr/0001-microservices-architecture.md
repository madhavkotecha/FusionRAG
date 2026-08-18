# ADR-0001: Microservices Architecture with API Gateway

## Status

Accepted

## Context

The Agentic RAG System needs to support multiple independent concerns: authentication/authorization, visual pipeline management, document ingestion with async processing, and a frontend SPA. These have different technology requirements, scaling characteristics, and development cadences.

## Decision

Adopt a microservices architecture with:
- **Traefik v3.2** as the API gateway and reverse proxy
- **Auth Server** (Node.js/Hono) for identity and access management
- **Pipeline Service** (Python/FastAPI) for pipeline CRUD and execution
- **Ingestion Service** (Python/FastAPI) for document processing
- **RQ Worker** for async job execution
- **Frontend** (React SPA) served via Nginx

All services communicate through Traefik, with ForwardAuth middleware for authentication.

## Consequences

**Positive:**
- Independent deployment and scaling per service
- Technology choice per domain (Node.js for auth, Python for ML/RAG workloads)
- Clear bounded contexts and ownership boundaries
- Service failures are isolated

**Negative:**
- Operational complexity (Docker Compose for dev, potential Kubernetes for prod)
- Network overhead for inter-service communication
- Distributed data consistency challenges (each service manages its own tables)
- Shared PostgreSQL instance is a single point of failure

## Alternatives Considered

1. **Monolith**: Simpler but couples auth, pipelines, and ingestion
2. **Modular monolith**: Shared deployment with module boundaries — considered too constraining for mixed Node.js/Python stack
