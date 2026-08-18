# ADR-0024: Redis Cache-Aside Pattern Across All Services

- **Status:** Accepted
- **Date:** 2026-03-07
- **Deciders:** Architecture Team
- **Relates to:** ADR-0014 (Multi-Level Caching Strategy), ADR-0023 (Ingestion Persistence Migration)

## Context

With the ingestion service migrating persistent state to PostgreSQL (ADR-0023), all three backend services now rely on PostgreSQL as their primary data store. PostgreSQL queries for workspace-scoped entity lookups and list operations are fast (~5ms), but under load the cumulative cost of repeated identical queries impacts response times and database connection pool utilization.

ADR-0014 proposed a multi-level caching strategy (L1–L4) for the research-backed RAG pipeline. This ADR implements the L2 (Redis) layer for the existing application services as a practical first step.

## Decision

Implement a **cache-aside** (lazy-loading) pattern with Redis across all three backend services: auth server, pipeline service, and ingestion service.

### Pattern

```
Read:  Cache → miss → DB → populate cache (TTL)
Write: DB → invalidate cache (entity + list)
Error: Log → continue (non-fatal)
```

### Key Schema

All cache keys follow a consistent namespace convention:

| Service | Prefix | Example |
|---------|--------|---------|
| Auth Server | `rrag:auth:{entity}:{scope}:{suffix}` | `rrag:auth:user:org1:list` |
| Pipeline Service | `rrag:ps:{entity}:{workspace_id}:{suffix}` | `rrag:ps:pipeline:ws1:abc123` |
| Ingestion Service | `rrag:ing:{entity}:{workspace_id}:{suffix}` | `rrag:ing:ds:ws1:list` |

### TTL Tiers

| Tier | Auth (s) | Pipeline (s) | Ingestion (s) | Use Case |
|------|----------|-------------|---------------|----------|
| SHORT | 60 | 60 | 30 | High-churn data (jobs, runs) |
| MEDIUM | 180 | 120 | 120 | List queries |
| LONG | 300 | 300 | 300 | Individual entity lookups |
| STATIC | 1800 | 1800 | 1800 | Near-static data (components, templates) |

### Invalidation Strategy

On every mutation (create, update, delete):
1. Write to PostgreSQL first (source of truth)
2. Delete the specific entity cache key
3. Delete the corresponding list cache key for the workspace

This ensures stale data is never served after a write, while allowing the next read to repopulate the cache.

### API Surface (per service)

Each service implements four functions with identical signatures:

| Function | Purpose |
|----------|---------|
| `cache_get(redis, entity, scope, suffix)` | Fetch cached JSON value |
| `cache_set(redis, entity, scope, value, suffix, ttl)` | Store JSON value with TTL |
| `cache_delete(redis, entity, scope, suffix)` | Delete specific cache key |
| `cache_invalidate_entity(redis, entity, scope, entity_id)` | Delete entity + list keys |

## Consequences

### Positive
- Reduced PostgreSQL query load for read-heavy workloads (list pages, entity lookups)
- Sub-millisecond cache hits vs ~5ms database round-trips
- Consistent caching pattern across all services — easier to reason about and debug
- Non-fatal cache errors ensure system availability even if Redis is temporarily unavailable
- Workspace-scoped keys maintain multi-tenant isolation in the cache layer

### Negative
- Added complexity in every CRUD operation (cache check + invalidation)
- Short window of stale reads possible (TTL-based expiry, not event-driven)
- Redis memory usage grows proportionally with active workspaces and entities

### Neutral
- No change to external API contracts — caching is transparent to clients
- Cache warm-up happens lazily on first access, not proactively

## Alternatives Considered

### Alternative 1: Write-through cache
- Description: Populate cache on every write, not just reads
- Rejected because: Increases write latency and caches data that may never be read. Cache-aside is more memory-efficient.

### Alternative 2: Event-driven invalidation (pub/sub)
- Description: Use Redis pub/sub or PostgreSQL LISTEN/NOTIFY for real-time cache invalidation
- Rejected because: Adds infrastructure complexity. TTL-based expiry with write-through invalidation provides adequate freshness for this workload.

### Alternative 3: In-process caching (LRU)
- Description: Use in-memory LRU caches within each service process
- Rejected because: Does not work across horizontal scaling (multiple instances). Redis provides a shared cache layer.

## Implementation Notes

- Auth server: `rrag-auth-server/src/cache/cache.ts` (TypeScript, generic `cacheGet<T>`)
- Pipeline service: `rrag-pipeline-service/src/pipeline_service/cache.py`
- Ingestion service: `rrag-ingestion/src/rrag_ingestion/cache.py`
- All implementations use `JSON.stringify`/`json.dumps` for serialization
