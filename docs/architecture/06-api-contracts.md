# 6. API Contracts

## Auth Server API

Base path: gateway port `:8000`

### Authentication (Keycloak OIDC)

Authentication is handled by Keycloak. The auth server provides OIDC configuration and user provisioning.

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/auth/oidc/config` | No | Get Keycloak OIDC configuration |
| `GET` | `/auth/me` | Bearer (KC JWT) | Get current user profile + auto-provision |
| `ALL` | `/auth/verify` | Bearer/API Key | ForwardAuth validation (internal) |
| `POST` | `/auth/logout` | Bearer | Log audit event (KC handles session) |
| `POST` | `/auth/logout/all` | Bearer | Revoke all user sessions |
| `GET` | `/auth/sessions` | Bearer | List active sessions |
| `DELETE` | `/auth/sessions/:id` | Bearer | Revoke specific session |

#### GET /auth/oidc/config

```jsonc
// Response 200
{
  "enabled": true,
  "realmUrl": "http://localhost:8000/kc/realms/rrag",
  "clientId": "rrag-frontend",
  "authEndpoint": "http://localhost:8000/kc/realms/rrag/protocol/openid-connect/auth",
  "tokenEndpoint": "http://localhost:8000/kc/realms/rrag/protocol/openid-connect/token",
  "logoutEndpoint": "http://localhost:8000/kc/realms/rrag/protocol/openid-connect/logout"
}
```

#### GET /auth/me

```jsonc
// Response 200
{
  "id": "uuid",
  "email": "user@example.com",
  "name": "John Doe",
  "orgId": "uuid",
  "orgRole": "org_admin",
  "isPlatformAdmin": false,
  "workspaces": [
    { "id": "ws-uuid", "name": "My Workspace", "role": "admin" }
  ]
}
```

#### ALL /auth/verify (ForwardAuth)

Returns headers to Traefik:
- `X-Auth-User-Id`, `X-Auth-Org-Id`, `X-Auth-Org-Role`, `X-Auth-Email`
- `X-Auth-Workspace-Roles` (JSON: `{"ws-id": "role", ...}`)
- `X-Auth-Platform-Admin` (`"true"` or `"false"`)

### User Management (requires org_admin)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/users` | Bearer (org_admin) | List org users |
| `POST` | `/users/invite` | Bearer (org_admin) | Invite user |
| `PUT` | `/users/:id/role` | Bearer (org_admin) | Change user org role |
| `PUT` | `/users/:id/status` | Bearer (org_admin) | Suspend/activate user |

### Workspace Management

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/workspaces` | Bearer | Create workspace |
| `GET` | `/workspaces` | Bearer | List accessible workspaces |
| `GET` | `/workspaces/:wsId/members` | Bearer (ws member) | List workspace members |
| `POST` | `/workspaces/:wsId/members` | Bearer (ws admin) | Add member |
| `PUT` | `/workspaces/:wsId/members/:userId` | Bearer (ws admin) | Change member role |
| `DELETE` | `/workspaces/:wsId/members/:userId` | Bearer (ws admin) | Remove member |

### Team Management

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/teams` | Bearer (org_admin) | Create team |
| `GET` | `/teams` | Bearer | List org teams |
| `GET` | `/teams/:teamId` | Bearer | Get team details |
| `PUT` | `/teams/:teamId` | Bearer (org_admin/lead) | Update team |
| `DELETE` | `/teams/:teamId` | Bearer (org_admin) | Delete team |
| `GET` | `/teams/:teamId/members` | Bearer | List team members |
| `POST` | `/teams/:teamId/members` | Bearer (org_admin/lead) | Add member |
| `PUT` | `/teams/:teamId/members/:userId` | Bearer (org_admin/lead) | Update member role |
| `DELETE` | `/teams/:teamId/members/:userId` | Bearer (org_admin/lead) | Remove member |

### API Keys

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/workspaces/:wsId/api-keys` | Bearer (ws member) | List API keys |
| `POST` | `/workspaces/:wsId/api-keys` | Bearer (ws admin) | Create API key |
| `DELETE` | `/workspaces/:wsId/api-keys/:keyId` | Bearer (ws admin) | Revoke API key |

#### POST /workspaces/:wsId/api-keys

```jsonc
// Request
{ "name": "CI Pipeline Key", "role": "developer", "rateLimitRpm": 600, "expiresAt": "2025-12-31T00:00:00Z" }

// Response 201
{ "id": "uuid", "name": "CI Pipeline Key", "key": "rrag_abc123...", "keyPrefix": "rrag_abc", "role": "developer", "rateLimitRpm": 600, "expiresAt": "2025-12-31T00:00:00Z" }
```

### Audit Logs

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/audit-logs` | Bearer (admin) | Query audit events |

Query params: `orgId`, `action`, `resourceType`, `status`, `startDate`, `endDate`, `limit`

### Health

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/health` | No | `{ "status": "ok" }` |

---

## Pipeline Service API

Base path: `/api/v1`

### Pipelines

| Method | Path | Auth | Min Role | Description |
|--------|------|------|----------|-------------|
| `GET` | `/api/v1/pipelines?workspace_id=` | ForwardAuth | viewer | List workspace pipelines |
| `POST` | `/api/v1/pipelines` | ForwardAuth | developer | Create pipeline |
| `GET` | `/api/v1/pipelines/:id?workspace_id=` | ForwardAuth | viewer | Get pipeline |
| `PUT` | `/api/v1/pipelines/:id?workspace_id=` | ForwardAuth | developer | Update pipeline |
| `DELETE` | `/api/v1/pipelines/:id?workspace_id=` | ForwardAuth | developer | Delete pipeline |

#### POST /api/v1/pipelines

```jsonc
// Request
{
  "name": "My RAG Pipeline",
  "description": "Vanilla RAG with reranking",
  "workspace_id": "ws-uuid",
  "definition": {
    "nodes": [
      { "id": "n1", "type": "data_source", "data": { "label": "Upload", "componentType": "file_upload", "category": "data_source", "config": {} } }
    ],
    "edges": [
      { "id": "e1", "source": "n1", "target": "n2" }
    ]
  }
}

// Response 201
{ "id": "uuid", "workspace_id": "ws-uuid", "name": "My RAG Pipeline", "status": "draft", "created_by": "user-uuid", "created_at": "...", "updated_at": "..." }
```

### Pipeline Versions

| Method | Path | Auth | Min Role | Description |
|--------|------|------|----------|-------------|
| `POST` | `/api/v1/pipelines/:id/versions?workspace_id=` | ForwardAuth | developer | Create version snapshot |
| `GET` | `/api/v1/pipelines/:id/versions?workspace_id=` | ForwardAuth | viewer | List versions |

### Pipeline Runs

| Method | Path | Auth | Min Role | Description |
|--------|------|------|----------|-------------|
| `POST` | `/api/v1/pipelines/:id/run?workspace_id=` | ForwardAuth | developer | Execute pipeline |
| `GET` | `/api/v1/runs/:runId` | ForwardAuth | viewer | Get run status |
| `GET` | `/api/v1/pipelines/:id/runs?workspace_id=` | ForwardAuth | viewer | List runs |

#### POST /api/v1/pipelines/:id/run

```jsonc
// Request
{ "input_params": { "query": "What is RAG?" } }

// Response 201
{ "id": "run-uuid", "pipeline_id": "pipe-uuid", "status": "pending", "input_params": { "query": "What is RAG?" }, "created_by": "user-uuid", "created_at": "..." }
```

### Templates & Components

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/templates` | ForwardAuth | List all templates |
| `GET` | `/api/v1/templates/:id` | ForwardAuth | Get template definition |
| `GET` | `/api/v1/components` | ForwardAuth | List registered components |

### Custom Component Upload

| Method | Path | Auth | Min Role | Description |
|--------|------|------|----------|-------------|
| `POST` | `/api/v1/components/upload?workspace_id=` | ForwardAuth | developer | Upload a `.py` composite component file |
| `DELETE` | `/api/v1/components/custom/:type?workspace_id=` | ForwardAuth | developer | Delete a custom component |

#### POST /api/v1/components/upload

Uploads a Python file containing a composite component (decorated with `@component` and `@step`). The file is stored in MinIO, AST-scanned for decorator metadata, and registered in the components table.

```jsonc
// Request: multipart/form-data
// Field "file": the .py file
// Query param "workspace_id": target workspace

// Response 201
{
  "id": "uuid",
  "type": "lightrag_ingestion",
  "category": "composite",
  "name": "LightRAG Ingestion",
  "description": "LightRAG 5-step ingestion pipeline",
  "source": "custom",
  "is_composite": true,
  "steps": [
    {"name": "chunk", "order": 1, "retry": 2},
    {"name": "extract_entities", "order": 2, "retry": 1},
    {"name": "merge_graph", "order": 3, "retry": 0},
    {"name": "store_graph", "order": 4, "retry": 0},
    {"name": "store_vectors", "order": 5, "retry": 0}
  ],
  "config_schema": {"chunk_size": {"type": "integer", "default": 1200}},
  "workspace_id": "ws-uuid",
  "file_path": "ws-uuid/lightrag_ingestion/abc123.py",
  "file_hash": "sha256:abc123...",
  "created_at": "..."
}
```

#### DELETE /api/v1/components/custom/:type

Deletes a custom component. Removes the record from PostgreSQL and the `.py` file from MinIO.

```jsonc
// Response 200
{ "deleted": true, "type": "lightrag_ingestion" }
```

### Pipeline Run SSE Streaming

| Method | Path | Auth | Min Role | Description |
|--------|------|------|----------|-------------|
| `GET` | `/api/v1/pipelines/:id/runs/:runId/stream?workspace_id=` | ForwardAuth | viewer | SSE: real-time step progress for composite components |

#### SSE Event Types (runs/:runId/stream)

| Event | Payload | Description |
|-------|---------|-------------|
| `step_start` | `{"step": "chunk", "order": 1, "total": 5}` | A composite step has started |
| `step_complete` | `{"step": "chunk", "order": 1, "total": 5, "status": "completed", "duration_ms": 450}` | A composite step completed successfully |
| `step_retry` | `{"step": "extract_entities", "order": 2, "attempt": 2, "max_retries": 3, "error": "..."}` | A step failed and is being retried |
| `step_failed` | `{"step": "extract_entities", "order": 2, "error": "..."}` | A step failed after all retries |
| `run_complete` | `{"status": "completed", "result": {...}}` | The pipeline run completed |
| `run_failed` | `{"status": "failed", "error": "..."}` | The pipeline run failed |

### Health

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/health` | No | `{ "status": "ok", "service": "pipeline-service", "version": "0.1.0" }` |

---

## Ingestion Service API

Base path: `/api/v1/ingestion`

All ingestion endpoints require `workspace_id` as a **mandatory query parameter** for multi-tenant data isolation. Auth headers (`X-Auth-*`) are parsed into an `AuthContext` with role-based access control.

### Documents

| Method | Path | Auth | Min Role | Description |
|--------|------|------|----------|-------------|
| `POST` | `/api/v1/ingestion/documents/upload?workspace_id=` | ForwardAuth | developer | Upload files (multipart) |
| `GET` | `/api/v1/ingestion/documents?workspace_id=` | ForwardAuth | viewer | List documents |
| `GET` | `/api/v1/ingestion/documents/:id?workspace_id=` | ForwardAuth | viewer | Get document metadata |
| `DELETE` | `/api/v1/ingestion/documents/:id?workspace_id=` | ForwardAuth | developer | Delete document |

### Jobs

| Method | Path | Auth | Min Role | Description |
|--------|------|------|----------|-------------|
| `POST` | `/api/v1/ingestion/jobs?workspace_id=` | ForwardAuth | developer | Create ingestion job |
| `GET` | `/api/v1/ingestion/jobs?workspace_id=` | ForwardAuth | viewer | List jobs |
| `GET` | `/api/v1/ingestion/jobs/:id?workspace_id=` | ForwardAuth | viewer | Get job status |
| `DELETE` | `/api/v1/ingestion/jobs/:id?workspace_id=` | ForwardAuth | developer | Cancel job |
| `GET` | `/api/v1/ingestion/jobs/stream?workspace_id=` | ForwardAuth | viewer | SSE: real-time job updates |

#### SSE Event Types (jobs/stream)

| Event | Payload | Description |
|-------|---------|-------------|
| `jobs` | `[{id, status, progress, ...}]` | Job list snapshot |
| `idle` | `{}` | No active jobs |

### RAG Query

| Method | Path | Auth | Min Role | Description |
|--------|------|------|----------|-------------|
| `POST` | `/api/v1/ingestion/query?workspace_id=` | ForwardAuth | developer | Synchronous RAG query |
| `POST` | `/api/v1/ingestion/query/stream?workspace_id=` | ForwardAuth | developer | Streaming RAG query (SSE) |
| `GET` | `/api/v1/ingestion/query/conversations/:id?workspace_id=` | ForwardAuth | viewer | Get conversation history |
| `DELETE` | `/api/v1/ingestion/query/conversations/:id?workspace_id=` | ForwardAuth | developer | Delete conversation |

### Chat

| Method | Path | Auth | Min Role | Description |
|--------|------|------|----------|-------------|
| `POST` | `/api/v1/ingestion/chat?workspace_id=` | ForwardAuth | developer | Chat with query pipelines as tools |
| `POST` | `/api/v1/ingestion/chat/stream?workspace_id=` | ForwardAuth | developer | Streaming chat via SSE |
| `GET` | `/api/v1/ingestion/chat/conversations/:id?workspace_id=` | ForwardAuth | viewer | Get chat conversation |
| `DELETE` | `/api/v1/ingestion/chat/conversations/:id?workspace_id=` | ForwardAuth | developer | Delete chat conversation |

### DataStores

| Method | Path | Auth | Min Role | Description |
|--------|------|------|----------|-------------|
| `POST` | `/api/v1/ingestion/datastores?workspace_id=` | ForwardAuth | developer | Create datastore |
| `GET` | `/api/v1/ingestion/datastores?workspace_id=` | ForwardAuth | viewer | List datastores |
| `GET` | `/api/v1/ingestion/datastores/:id?workspace_id=` | ForwardAuth | viewer | Get datastore |
| `GET` | `/api/v1/ingestion/datastores/:id/strategies?workspace_id=` | ForwardAuth | viewer | Get retrieval strategies |
| `DELETE` | `/api/v1/ingestion/datastores/:id?workspace_id=` | ForwardAuth | developer | Delete datastore |

### Query Pipelines

| Method | Path | Auth | Min Role | Description |
|--------|------|------|----------|-------------|
| `POST` | `/api/v1/ingestion/query-pipelines?workspace_id=` | ForwardAuth | developer | Create query pipeline |
| `GET` | `/api/v1/ingestion/query-pipelines?workspace_id=` | ForwardAuth | viewer | List query pipelines |
| `GET` | `/api/v1/ingestion/query-pipelines/:id?workspace_id=` | ForwardAuth | viewer | Get query pipeline |
| `GET` | `/api/v1/ingestion/query-pipelines/:id/tool-schema?workspace_id=` | ForwardAuth | viewer | Get OpenAI tool schema |
| `PUT` | `/api/v1/ingestion/query-pipelines/:id?workspace_id=` | ForwardAuth | developer | Update query pipeline |
| `DELETE` | `/api/v1/ingestion/query-pipelines/:id?workspace_id=` | ForwardAuth | developer | Delete query pipeline |

### Admin (requires org_admin or platform_admin)

| Method | Path | Auth | Min Role | Description |
|--------|------|------|----------|-------------|
| `GET` | `/api/v1/ingestion/admin/stats` | ForwardAuth | org_admin | System statistics |
| `GET` | `/api/v1/ingestion/admin/queue/stats` | ForwardAuth | org_admin | Queue metrics |
| `POST` | `/api/v1/ingestion/admin/queue/actions` | ForwardAuth | org_admin | Queue operations (purge, retry) |
| `GET` | `/api/v1/ingestion/admin/health` | ForwardAuth | org_admin | Service health check |
| `GET` | `/api/v1/ingestion/admin/config` | ForwardAuth | org_admin | Get system config |
| `PUT` | `/api/v1/ingestion/admin/config` | ForwardAuth | org_admin | Update system config |
| `GET` | `/api/v1/ingestion/admin/queue/timeline` | ForwardAuth | org_admin | Job timeline for charts |

#### POST /api/v1/ingestion/query

```jsonc
// Request
{
  "query": "What is retrieval augmented generation?",
  "model": "gpt-4o-mini",
  "temperature": 0.7,
  "max_tokens": 2048,
  "top_k": 10,
  "conversation_id": null,
  "stream": false
}

// Response 200
{
  "id": "uuid",
  "conversation_id": "conv-uuid",
  "query": "What is retrieval augmented generation?",
  "answer": "RAG is a technique that...",
  "sources": [
    { "id": "chunk-uuid", "content": "...", "score": 0.92, "metadata": {} }
  ],
  "model": "gpt-4o-mini",
  "tokens_used": 847,
  "duration_ms": 1230,
  "strategy": "rag"
}
```

#### SSE Event Types (query/stream)

| Event | Payload | Description |
|-------|---------|-------------|
| `start` | `{ "query_id": "..." }` | Query initiated |
| `sources` | `[{ "id", "content", "score" }]` | Retrieved documents |
| `token` | `{ "text": "..." }` | Streamed response token |
| `done` | `{ "id", "answer", "tokens_used", ... }` | Complete response |
| `error` | `{ "message": "..." }` | Error occurred |

### Ingestion Pipelines

| Method | Path | Auth | Min Role | Description |
|--------|------|------|----------|-------------|
| `GET` | `/api/v1/ingestion/pipelines?workspace_id=` | ForwardAuth | viewer | List pipelines |
| `GET` | `/api/v1/ingestion/pipelines/:name?workspace_id=` | ForwardAuth | viewer | Get pipeline config |
| `POST` | `/api/v1/ingestion/pipelines?workspace_id=` | ForwardAuth | developer | Create pipeline |
| `PUT` | `/api/v1/ingestion/pipelines/:name?workspace_id=` | ForwardAuth | developer | Update pipeline |
| `DELETE` | `/api/v1/ingestion/pipelines/:name?workspace_id=` | ForwardAuth | developer | Delete pipeline |
| `POST` | `/api/v1/ingestion/pipelines/:name/validate?workspace_id=` | ForwardAuth | developer | Validate pipeline config |

### Components

| Method | Path | Auth | Min Role | Description |
|--------|------|------|----------|-------------|
| `GET` | `/api/v1/ingestion/components` | ForwardAuth | viewer | List all components |
| `GET` | `/api/v1/ingestion/components/types/:type` | ForwardAuth | viewer | Components by type |
| `GET` | `/api/v1/ingestion/components/:name` | ForwardAuth | viewer | Component details |

### Health

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/health` | No | `{ "status": "healthy", "service": "rrag-ingestion" }` |

---

## Error Response Format

All services return errors in a consistent format:

```jsonc
// Standard error
{ "error": "Human-readable message" }

// Error with code
{ "error": "Rate limit exceeded", "code": "RATE_LIMIT_EXCEEDED" }
```

### Common HTTP Status Codes

| Code | Meaning | Common Causes |
|------|---------|---------------|
| 400 | Bad Request | Validation failure, malformed input |
| 401 | Unauthorized | Missing/invalid/expired token |
| 403 | Forbidden | Insufficient permissions for resource |
| 404 | Not Found | Resource does not exist |
| 409 | Conflict | Duplicate email, slug, etc. |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Error | Unexpected server failure |

### Auth-Specific Error Codes

| Code | HTTP | Description |
|------|------|-------------|
| `AUTH_REQUIRED` | 401 | No token or API key provided |
| `INVALID_TOKEN` | 401 | JWT signature/expiry validation failed |
| `TOKEN_REVOKED` | 401 | Token JTI is blacklisted |
| `INVALID_API_KEY` | 401 | API key hash not found or inactive |
| `API_KEY_EXPIRED` | 401 | API key past expiration date |
| `ACCOUNT_LOCKED` | 423 | Too many failed login attempts |
| `RATE_LIMIT_EXCEEDED` | 429 | Sliding window limit hit |
