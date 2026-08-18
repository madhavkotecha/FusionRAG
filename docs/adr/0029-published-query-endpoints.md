# ADR-0029: Published Query Endpoints with API-Key Authentication

- **Status:** Accepted
- **Date:** 2026-04-21 (publish API + UI), 2026-04-24 (DB-backed persistence)
- **Deciders:** Architecture Team
- **Relates to:** ADR-0002 (ForwardAuth Pattern), ADR-0028 (Knowledge Base Domain Model), ADR-0017 (SSE Streaming Responses)

## Context

The pipeline builder produces working RAG pipelines, but consuming them required a session-authenticated request from the frontend or a manually-crafted JWT — neither is acceptable for server-to-server integrations (a customer's backend calling our RAG endpoint, an external chatbot, scheduled jobs).

We needed:
1. A way to "publish" a (KnowledgeBase × QueryPipeline) pair as a stable URL with a stable identifier
2. Authentication that doesn't depend on Keycloak sessions — i.e., an API key the publisher hands to consumers
3. Traefik routing that bypasses ForwardAuth for published-endpoint requests, while keeping all other traffic gated

## Decision

Introduce a `PublishedEndpoint` entity persisted in Postgres, plus a Traefik route that exempts published query paths from JWT auth.

### Data model (`PublishedEndpointRow`)

| Field | Purpose |
|-------|---------|
| `id` (uuid) | Internal id |
| `workspace_id` | Tenancy |
| `slug` (unique, globally) | URL-stable identifier |
| `name`, `description` | Human metadata |
| `datastore_id` | FK to KnowledgeBase (ADR-0028) |
| `query_pipeline_id` | FK to query pipeline |
| `api_key` (`rrag_<28-hex>`) | Bearer credential for callers |
| `status` (`active` / `disabled`) | Soft-disable toggle |
| `created_at` | Audit |

### API surface (`rrag-ingestion/src/rrag_ingestion/api/publish.py`)

- `POST   /api/v1/ingestion/publish` — create (workspace developer role required)
- `GET    /api/v1/ingestion/publish` — list (workspace viewer)
- `PATCH  /api/v1/ingestion/publish/{id}` — toggle status
- `DELETE /api/v1/ingestion/publish/{id}` — remove

### Consumer-facing route

```
POST /api/v1/ingestion/publish/{slug}/query
Headers: Authorization: Bearer rrag_<api_key>
Body:    { "query": "...", "top_k": 5 }
```

Traefik label (in `docker-compose.yml`, see `ingestion-public` router):
```
PathPrefix(`/api/v1/ingestion/publish/`) && PathRegexp(`/api/v1/ingestion/publish/.+/query`)
priority=210 (higher than the auth-gated ingestion-api router at 200)
middlewares: (none — JWT ForwardAuth skipped)
```

The query handler validates the API key against the row and rejects if `status != active`.

### Frontend

`rrag-frontend/src/pages/PublishPage.tsx` — create / list / copy-key / disable.

## Consequences

**Positive:**
- Customers integrate against a stable slug-based URL, decoupled from internal pipeline UUIDs
- API keys are workspace-scoped and revocable without touching Keycloak
- The standard ForwardAuth path (ADR-0002) remains untouched for all internal/UI traffic
- Disabling an endpoint is a single PATCH, instant

**Negative:**
- API keys stored hashed-equivalent (as `rrag_<hex>`) — currently stored in plaintext; should move to per-key salted hashes (TODO)
- Rate-limiting on published endpoints is not yet differentiated from internal — needs per-key quotas
- No usage analytics (request count, latency) per endpoint — only Traefik access logs

## Alternatives Considered

1. **Use Keycloak service accounts** — heavy: requires realm changes per consumer, OIDC client provisioning.
2. **Long-lived JWTs** — would still need ForwardAuth on the path; rotation harder.
3. **Per-workspace single API key** — simpler but couples all integrations together; one leak kills all of them.

## References

- Commits: `8e75e49` (initial Publish page + APIs), `d5012ad` (publish API + resume retry + checkpoints), `8f34cdc` (DB-backed published endpoints + UI), `f2e31d0` (Publish button in toolbar)
- Files: `rrag-ingestion/src/rrag_ingestion/api/publish.py`, `rrag-ingestion/src/rrag_ingestion/db/models.py` (`PublishedEndpointRow`), `rrag-frontend/src/pages/PublishPage.tsx`, `docker-compose.yml` (Traefik `ingestion-public` router)
