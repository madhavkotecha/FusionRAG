# ADR-0006: Technology Stack Selection

## Status

Accepted

## Context

The project requires a full-stack platform with authentication, API services for ML/RAG workloads, async processing, and a rich frontend. Technology choices must balance developer productivity, ecosystem maturity, and operational simplicity.

## Decision

### Auth Server: Node.js + Hono + Drizzle ORM

- **Hono**: Lightweight, fast, excellent TypeScript support, works across runtimes
- **Drizzle ORM**: Type-safe SQL, no heavy abstractions, great migration tooling
- **Rationale**: Auth is I/O-bound (DB + Redis), benefits from Node.js event loop. Hono is simpler than Express/Fastify with modern DX.

### Backend Services: Python + FastAPI + SQLAlchemy

- **FastAPI**: Async-native, OpenAPI auto-generation, Pydantic validation
- **SQLAlchemy 2.0**: Mature async ORM with asyncpg driver
- **Rationale**: Python is the lingua franca for ML/AI workloads. Libraries like FAISS, sentence-transformers, and LLM SDKs are Python-first.

### Frontend: React + TypeScript + Vite + Tailwind CSS

- **React 19**: Latest with concurrent features
- **Vite 7**: Fast HMR, modern build tooling
- **Tailwind CSS 4**: Utility-first, design-system-friendly
- **Zustand**: Minimal, performant state management
- **XYFlow**: Production-grade flow/graph editor
- **Monaco Editor**: VS Code editor component for configs

### Infrastructure: Docker Compose + Traefik + PostgreSQL + Redis

- **Docker Compose**: Simple local development and deployment
- **Traefik**: Auto-discovery via Docker labels, ForwardAuth support
- **PostgreSQL 16**: Robust relational DB with JSONB support
- **Redis 7**: Cache, queue, and session store

### Package Management: uv (Python)

- **uv**: 10-100x faster than pip, modern lockfile support, great for Docker builds

## Consequences

- Mixed Node.js/Python stack requires maintaining two ecosystems
- All services can be containerized with Docker
- Python services share libraries for ML workloads
- Frontend build is fast with Vite (< 5s incremental)

## Alternatives Considered

| Choice | Alternative | Why Not |
|--------|-----------|---------|
| Hono | Express, Fastify | Heavier, less modern TypeScript DX |
| Drizzle | Prisma, TypeORM | Prisma too abstracted, TypeORM less type-safe |
| FastAPI | Django, Flask | Django too opinionated, Flask lacks async |
| Zustand | Redux, Jotai | Redux too verbose, Jotai less mainstream |
| Tailwind | CSS Modules, styled-components | Less consistent, slower development |
| Docker Compose | Kubernetes | Over-engineered for development/small deployments |
| uv | pip, poetry | Significantly slower, weaker lockfile support |
