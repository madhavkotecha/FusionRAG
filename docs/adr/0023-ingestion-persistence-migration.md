# ADR-0023: Ingestion Service Persistence Migration to PostgreSQL

- **Status:** Accepted
- **Date:** 2026-03-07
- **Deciders:** Architecture Team
- **Relates to:** ADR-0005 (Async Ingestion with RQ), ADR-0006 (Technology Choices), ADR-0024 (Redis Cache-Aside Pattern)

## Context

The ingestion service originally stored all persistent state (documents, datastores, jobs, query pipelines) in Redis using workspace-scoped hash keys (`rrag:{type}:{workspace_id}:{id}`). While this was simple and fast for prototyping, it introduced several problems:

1. **Durability risk**: Redis persistence (RDB/AOF) provides weaker guarantees than PostgreSQL WAL. A Redis restart could lose in-flight job state.
2. **Query limitations**: Filtering, sorting, and aggregating Redis hashes requires scanning all keys — no secondary indexes, no `WHERE` clauses.
3. **Schema drift**: JSON values in Redis hashes lack schema enforcement, leading to inconsistent field names across versions.
4. **Operational burden**: Two persistence systems (PostgreSQL for auth+pipeline, Redis for ingestion) meant two backup strategies and two recovery procedures.
5. **Data isolation gap**: Cross-workspace data isolation relied on key naming conventions rather than enforceable constraints.

Meanwhile, the auth server and pipeline service were already using PostgreSQL successfully with Drizzle and SQLAlchemy respectively.

## Decision

Migrate the ingestion service's persistent state from Redis to PostgreSQL, keeping Redis for ephemeral data only.

### What moved to PostgreSQL

| Entity | Old Storage | New Storage |
|--------|-----------|-------------|
| Documents | `rrag:doc:{ws}:{id}` Redis hash | `documents` PostgreSQL table |
| DataStores | `rrag:datastore:{ws}:{id}` Redis hash | `datastores` PostgreSQL table |
| Jobs | `rrag:job:{ws}:{id}` Redis hash | `jobs` PostgreSQL table |
| Query Pipelines | `rrag:qp:{ws}:{id}` Redis hash | `query_pipelines` PostgreSQL table |

### What stays in Redis

| Data | Reason |
|------|--------|
| Job queue (`rq:queue:ingestion`) | RQ requires Redis |
| Live job progress (`rrag:progress:{job_id}`) | High-frequency updates, ephemeral |
| Conversations (`rrag:conv:{ws}:{conv_id}`) | Short-lived (24h TTL), append-heavy |
| Cache-aside entries (`rrag:ing:{entity}:{ws}:{id}`) | TTL-based read acceleration |

### Database access modes

- **Async** (FastAPI endpoints): `asyncpg` via SQLAlchemy `async_sessionmaker`, pool_size=10, max_overflow=20
- **Sync** (RQ workers): Standard `psycopg2` sessions via `sessionmaker` for background job processing
- **Schema creation**: `Base.metadata.create_all()` on FastAPI startup (no Alembic — tables are additive)

### Cache-aside pattern

A Redis cache-aside layer was added across all three backend services to maintain read performance:

1. **Read**: Check Redis cache → on miss, query PostgreSQL → populate cache with TTL
2. **Write**: Mutate PostgreSQL → invalidate entity key + list key in Redis
3. **Failure**: All cache errors are non-fatal (logged, request continues against DB)

Key format: `rrag:{service}:{entity}:{workspace_id}:{suffix}`

## Consequences

### Positive
- All persistent data in a single PostgreSQL instance — unified backup/restore
- ACID transactions for job state transitions (no more partial updates on crash)
- SQL queries for filtering, pagination, and aggregation (e.g., jobs by status)
- Schema enforcement via SQLAlchemy models — column types, NOT NULL, indexes
- Workspace isolation enforced by `WHERE workspace_id = :ws_id` at the query level

### Negative
- Added PostgreSQL as a dependency for the ingestion service (was Redis-only)
- Dual database access patterns (async + sync) add complexity for RQ workers
- No Alembic migrations yet — schema changes require manual `create_all` coordination

### Neutral
- Redis remains a dependency for job queuing (RQ), caching, and conversations
- Read latency mitigated by cache-aside layer (cache hit returns in <1ms vs ~5ms for DB)

## Alternatives Considered

### Alternative 1: Keep Redis, add persistence guarantees
- Description: Enable Redis AOF with `fsync=always`, add key expiry management
- Rejected because: Still lacks query flexibility, schema enforcement, and ACID guarantees. Higher operational complexity for marginal durability improvement.

### Alternative 2: Use a separate PostgreSQL database for ingestion
- Description: Dedicated PostgreSQL instance for ingestion tables
- Rejected because: Added infrastructure complexity. The shared PostgreSQL instance has sufficient capacity, and table namespacing provides adequate isolation.

### Alternative 3: Add Alembic migrations
- Description: Use Alembic for ingestion schema management like the pipeline service
- Rejected because: The ingestion schema is new and still evolving. `create_all` is simpler during rapid development. Alembic can be adopted later when the schema stabilizes.

## Implementation Notes

- Models defined in `rrag-ingestion/src/rrag_ingestion/db/models.py`
- Session factory in `rrag-ingestion/src/rrag_ingestion/db/session.py`
- CRUD operations with cache-aside in `rrag-ingestion/src/rrag_ingestion/db/stores.py`
- Cache utilities in `rrag-ingestion/src/rrag_ingestion/cache.py`
- Environment variable: `RRAG_DATABASE_URL` (asyncpg format)
