# 4. Data Architecture

## Database Topology

```mermaid
graph LR
    subgraph "PostgreSQL 16"
        AuthDB["Auth Tables<br/><i>12 tables (Drizzle)</i>"]
        PipeDB["Pipeline Tables<br/><i>5 tables (SQLAlchemy)</i>"]
        IngDB["Ingestion Tables<br/><i>4 tables (SQLAlchemy)</i>"]
        KCDB["Keycloak DB<br/><i>Separate instance</i>"]
    end

    subgraph "Redis 7"
        DB0["DB 0<br/><i>Auth: sessions, rate limits,<br/>token blacklist, entity cache</i>"]
        DB1["DB 1<br/><i>Ingestion: job queue, live progress,<br/>conversations, entity cache</i>"]
    end

    subgraph "Neo4j 5"
        Neo4jDB["Knowledge Graph<br/><i>Entities + Relations</i>"]
    end

    subgraph "MinIO (S3)"
        MinioBucket["rrag-documents bucket<br/><i>Uploaded files</i>"]
        MinioCompBucket["rrag-components bucket<br/><i>Custom component .py files</i>"]
    end

    subgraph "Qdrant v1.13"
        QdrantColl["Vector Collections<br/><i>Per-datastore embeddings</i>"]
    end

    subgraph "OpenSearch 2.17"
        OSIndex["Search Indexes<br/><i>BM25 + vector hybrid</i>"]
    end

    Auth["Auth Server"] --> AuthDB & DB0
    Pipeline["Pipeline Service"] --> PipeDB
    Ingestion["Ingestion Service"] --> IngDB & DB1 & MinioBucket & QdrantColl & OSIndex & Neo4jDB
    RQ["RQ Worker"] --> IngDB & MinioBucket & QdrantColl & OSIndex & Neo4jDB
    Keycloak["Keycloak"] --> KCDB
```

## PostgreSQL Schema

### Auth Server Tables (Drizzle ORM)

#### Entity Relationship Diagram

```mermaid
erDiagram
    organizations ||--o{ users : "has many"
    organizations ||--o{ workspaces : "has many"
    organizations ||--o{ teams : "has many"
    organizations ||--o| sso_configs : "has one"
    users ||--o{ sessions : "has many"
    users ||--o{ workspace_members : "member of"
    users ||--o{ team_members : "member of"
    teams ||--o{ team_members : "has members"
    workspaces ||--o{ workspace_members : "has members"
    workspaces ||--o{ api_keys : "has keys"
    workspaces ||--o{ workspace_access_grants : "grants access"

    organizations {
        uuid id PK
        varchar name
        varchar slug UK
        varchar plan
        timestamp created_at
        timestamp updated_at
    }

    users {
        uuid id PK
        uuid org_id FK
        varchar email
        varchar name
        varchar password_hash
        varchar status
        varchar org_role
        boolean is_platform_admin
        int failed_login_attempts
        timestamp locked_until
        timestamp last_login_at
        timestamp created_at
        timestamp updated_at
    }

    teams {
        uuid id PK
        uuid org_id FK
        varchar name
        varchar slug
        varchar description
        uuid created_by FK
        timestamp created_at
        timestamp updated_at
    }

    team_members {
        uuid id PK
        uuid team_id FK
        uuid user_id FK
        varchar role
        timestamp created_at
    }

    workspaces {
        uuid id PK
        uuid org_id FK
        varchar name
        varchar slug
        varchar scope
        uuid owner_user_id FK
        uuid owner_team_id FK
        timestamp created_at
        timestamp updated_at
    }

    workspace_members {
        uuid id PK
        uuid workspace_id FK
        uuid user_id FK
        varchar role
        timestamp created_at
    }

    sessions {
        uuid id PK
        uuid user_id FK
        varchar refresh_token_hash UK
        jsonb device_info
        timestamp last_active_at
        timestamp expires_at
        timestamp revoked_at
        timestamp created_at
    }

    api_keys {
        uuid id PK
        uuid workspace_id FK
        varchar name
        varchar key_prefix
        varchar key_hash UK
        varchar role
        int rate_limit_rpm
        timestamp last_used_at
        timestamp expires_at
        varchar status
        uuid created_by
        timestamp created_at
        timestamp revoked_at
    }

    audit_logs {
        uuid id PK
        uuid org_id
        uuid user_id
        varchar action
        varchar resource_type
        uuid resource_id
        uuid workspace_id
        jsonb details
        varchar ip_address
        varchar user_agent
        uuid request_id
        varchar status
        timestamp timestamp
    }

    sso_configs {
        uuid id PK
        uuid org_id FK
        varchar protocol
        varchar provider_name
        varchar metadata_url
        varchar client_id
        bytea client_secret_encrypted
        jsonb group_mapping
        boolean auto_provision
        boolean enforce_sso
        timestamp created_at
        timestamp updated_at
    }

    user_invitations {
        uuid id PK
        uuid org_id
        varchar email
        uuid workspace_id
        varchar role
        varchar token_hash UK
        varchar status
        uuid invited_by
        timestamp expires_at
        timestamp accepted_at
        timestamp created_at
    }

    workspace_access_grants {
        uuid id PK
        uuid source_ws_id
        uuid target_ws_id
        varchar resource_type
        uuid resource_id
        varchar permission
        uuid granted_by
        timestamp expires_at
        timestamp created_at
    }
```

### Pipeline Service Tables (SQLAlchemy)

```mermaid
erDiagram
    pipelines ||--o{ pipeline_versions : "has versions"
    pipelines ||--o{ pipeline_runs : "has runs"

    pipelines {
        varchar id PK
        varchar workspace_id
        varchar name
        varchar description
        json definition
        enum status
        enum pipeline_type
        varchar datastore_id
        varchar created_by
        timestamp created_at
        timestamp updated_at
    }

    pipeline_versions {
        varchar id PK
        varchar pipeline_id FK
        int version
        json definition
        varchar change_message
        varchar created_by
        timestamp created_at
        timestamp updated_at
    }

    pipeline_runs {
        uuid id PK
        varchar pipeline_id FK
        varchar version_id
        enum status
        json input_params
        json result
        varchar error
        timestamp started_at
        timestamp completed_at
        varchar created_by
        timestamp created_at
        timestamp updated_at
    }

    components {
        varchar id PK
        varchar type UK
        varchar category
        varchar name
        varchar description
        json config_schema
        json input_ports
        json output_ports
        varchar source "built_in | custom"
        boolean is_composite "false for atomic"
        json steps "ordered step metadata (composite only)"
        varchar workspace_id "null for built-in"
        varchar file_path "MinIO path (custom only)"
        varchar file_hash "SHA256 of .py file (custom only)"
        timestamp created_at
        timestamp updated_at
    }

    pipeline_templates {
        varchar id PK
        varchar template_id UK
        varchar name
        varchar description
        varchar category
        json definition
        timestamp created_at
        timestamp updated_at
    }
```

### Ingestion Service Tables (SQLAlchemy)

```mermaid
erDiagram
    documents {
        varchar_36 id PK
        varchar_255 workspace_id "Indexed"
        varchar_1024 filename
        varchar_255 content_type
        text file_path
        jsonb metadata
        timestamptz created_at
    }

    datastores {
        varchar_36 id PK
        varchar_255 workspace_id "Indexed"
        varchar_255 name
        text description
        varchar_255 pipeline_name
        jsonb source_document_ids "Array of doc UUIDs"
        varchar_36 created_by_job_id
        varchar_50 status "empty | ready | processing"
        jsonb targets "Vector/hybrid/graph backend configs"
        timestamptz created_at
        timestamptz updated_at
    }

    jobs {
        varchar_36 id PK
        varchar_255 workspace_id "Indexed"
        varchar_255 pipeline_name
        jsonb document_ids
        jsonb config_overrides
        varchar_50 status "Indexed: queued | running | completed | failed"
        integer progress "0-100"
        varchar_255 current_step
        integer total_steps
        jsonb errors
        jsonb step_results
        jsonb pipeline_steps
        float total_duration_ms
        varchar_36 datastore_id
        timestamptz created_at
        timestamptz started_at
        timestamptz completed_at
    }

    query_pipelines {
        varchar_36 id PK
        varchar_255 workspace_id "Indexed"
        varchar_255 name
        text description
        varchar_36 datastore_id
        varchar_50 retrieval_strategy "auto | hybrid | dense | sparse"
        jsonb retriever
        jsonb reranker
        jsonb generator
        jsonb planner
        jsonb agent
        jsonb definition
        timestamptz created_at
        timestamptz updated_at
    }
```

**DataStore targets** encode backend-specific configuration:
```json
[
  {"type": "vector", "backend": "qdrant", "config": {"url": "...", "collection_name": "..."}, "stats": {"records_stored": 1200}},
  {"type": "hybrid", "backend": "opensearch", "config": {"host": "...", "index_name": "..."}, "stats": {}},
  {"type": "graph", "backend": "neo4j", "config": {"uri": "...", "label_prefix": "..."}, "stats": {}}
]
```

**Component model — new fields for composite components:**

| Field | Type | Description |
|-------|------|-------------|
| `source` | `varchar` | `"built_in"` for registry components, `"custom"` for user-uploaded `.py` files |
| `is_composite` | `boolean` | `true` for multi-step composite components, `false` for atomic components |
| `steps` | `json` | Ordered array of step metadata extracted by AST scanner (composite only): `[{"name": "chunk", "order": 1, "retry": 2}, ...]` |
| `workspace_id` | `varchar` | Workspace scope for custom components; `null` for built-in components |
| `file_path` | `varchar` | MinIO object path for the uploaded `.py` file (custom only): `{workspace_id}/{type}/{hash}.py` |
| `file_hash` | `varchar` | SHA-256 hash of the `.py` file; used by `ComponentLoader` to detect changes and invalidate local cache |

**MinIO buckets:**

| Bucket | Purpose | Key Pattern |
|--------|---------|-------------|
| `rrag-documents` | Uploaded user documents (PDF, DOCX, TXT, etc.) | `{workspace_id}/{document_id}/{filename}` |
| `rrag-components` | Custom composite component Python files | `{workspace_id}/{component_type}/{file_hash}.py` |

**Database access modes:**
- **Async** (FastAPI endpoints): `asyncpg` + `async_sessionmaker`, pool_size=10, max_overflow=20
- **Sync** (RQ workers): Standard `psycopg2` sessions for background job processing

### Status Enums

| Model | Values |
|-------|--------|
| `Pipeline.status` | `draft`, `published`, `archived` |
| `Pipeline.pipeline_type` | `ingestion`, `query` |
| `PipelineRun.status` | `pending`, `running`, `completed`, `failed` |
| `User.status` | `active`, `suspended`, `deactivated` |
| `ApiKey.status` | `active`, `revoked` |
| `UserInvitation.status` | `pending`, `accepted`, `expired` |
| `AuditLog.status` | `success`, `denied`, `error` |
| `DataStore.status` | `empty`, `ready`, `processing` |
| `Job.status` | `queued`, `running`, `completed`, `failed` |
| `QueryPipeline.retrieval_strategy` | `auto`, `hybrid`, `dense`, `sparse` |

## Redis Data Structures

### DB 0 — Auth Server

| Key Pattern | Type | Purpose | TTL |
|-------------|------|---------|-----|
| `ratelimit:{ip}:{window}` | Sorted Set | Sliding window rate limiting | 60s |
| `blacklist:{jti}` | String | Revoked access token JTI | Token's remaining TTL |
| `session:{token_hash}` | String | Active refresh token reference | Refresh token TTL |
| `rrag:auth:{entity}:{scope}:{suffix}` | String (JSON) | Cache-aside entity/list cache | 60–1800s |

### DB 1 — Ingestion Service

Persistent state (documents, datastores, jobs, query pipelines) has been **migrated to PostgreSQL**. Redis DB 1 now holds only ephemeral data, cache, and the job queue.

| Key Pattern | Type | Purpose | TTL |
|-------------|------|---------|-----|
| `rrag:ing:{entity}:{workspace_id}:{id}` | String (JSON) | Cache-aside entity cache | 30–300s |
| `rrag:ing:{entity}:{workspace_id}:list` | String (JSON) | Cache-aside list cache | 30–120s |
| `rrag:progress:{job_id}` | Hash | Live job progress (current_step, %) | 24h |
| `rrag:conv:{workspace_id}:{conv_id}` | Hash | Conversation history (messages, tool traces) | 24h |
| `rq:queue:ingestion` | List | Pending ingestion jobs | None |
| `rrag:run:{run_id}:steps` | Pub/Sub Channel | Composite component step progress events | N/A (pub/sub) |

### Cache-Aside Layer (All Services)

All three backend services implement a **cache-aside** (lazy-loading) pattern with Redis:

```mermaid
sequenceDiagram
    participant API as Service API
    participant Cache as Redis Cache
    participant DB as PostgreSQL

    API->>Cache: cache_get(entity, workspace_id, id)
    alt Cache Hit
        Cache-->>API: Return cached value
    else Cache Miss
        Cache-->>API: null
        API->>DB: SELECT * FROM entity WHERE ...
        DB-->>API: Row data
        API->>Cache: cache_set(entity, workspace_id, value, ttl)
        API-->>API: Return data
    end

    Note over API,DB: On Mutation (create/update/delete)
    API->>DB: INSERT/UPDATE/DELETE
    API->>Cache: cache_invalidate_entity(entity, workspace_id, id)
    Note over Cache: Deletes both entity key and list key
```

**Key patterns by service:**

| Service | Key Prefix | Example |
|---------|-----------|---------|
| Auth Server | `rrag:auth:{entity}:{scope}:{suffix}` | `rrag:auth:user:org123:list` |
| Pipeline Service | `rrag:ps:{entity}:{workspace_id}:{suffix}` | `rrag:ps:pipeline:ws1:abc123` |
| Ingestion Service | `rrag:ing:{entity}:{workspace_id}:{suffix}` | `rrag:ing:ds:ws1:list` |

**TTL configuration:**

| TTL Tier | Auth (s) | Pipeline (s) | Ingestion (s) | Use Case |
|----------|----------|-------------|---------------|----------|
| SHORT | 60 | 60 | 30 | Frequently changing (jobs, runs) |
| MEDIUM | 180 | 120 | 120 | List queries |
| LONG | 300 | 300 | 300 | Individual entities |
| STATIC | 1800 | 1800 | 1800 | Near-static data (components, templates) |

**Design principles:**
- All cache failures are **non-fatal** — errors are logged but requests proceed against PostgreSQL
- Invalidation is **write-through**: every mutation deletes both the entity key and the corresponding list key
- Cache is **workspace-scoped**: keys include `workspace_id` for multi-tenant isolation

## Data Flow

### Document Ingestion Pipeline

```mermaid
sequenceDiagram
    participant U as User
    participant F as Frontend
    participant T as Traefik
    participant I as Ingestion API
    participant PG as PostgreSQL
    participant R as Redis
    participant M as MinIO
    participant W as RQ Worker
    participant AI as OpenAI
    participant VDB as Qdrant/OpenSearch

    U->>F: Upload document
    F->>T: POST /api/v1/ingestion/documents/upload
    T->>I: Forward (with auth headers)
    I->>M: Store file in rrag-documents bucket
    I->>PG: INSERT INTO documents (metadata)
    I-->>F: {id, filename}

    U->>F: Create ingestion job
    F->>T: POST /api/v1/ingestion/jobs
    T->>I: Forward
    I->>PG: INSERT INTO jobs (status: queued)
    I->>R: Enqueue job (rq:queue:ingestion)
    I-->>F: {job_id, status: "queued"}

    F->>T: GET /api/v1/ingestion/jobs/stream (SSE)
    T->>I: Forward

    W->>R: Dequeue job
    W->>PG: Load job record (sync session)
    W->>PG: Update status → running
    W->>M: Read document from MinIO
    W->>W: Parse & chunk
    W->>AI: Generate embeddings
    W->>VDB: Index vectors (Qdrant/OpenSearch)
    W->>PG: Update job status + results
    W->>PG: Create/update DataStore record
    I-->>F: SSE: job status update
```

### RAG Query Flow

```mermaid
sequenceDiagram
    participant U as User
    participant F as Frontend
    participant T as Traefik
    participant I as Ingestion API
    participant VDB as Qdrant/OpenSearch
    participant Neo4j as Neo4j
    participant AI as OpenAI

    U->>F: Ask question
    F->>T: POST /api/v1/ingestion/query/stream
    T->>I: Forward

    I->>AI: Embed query
    alt Vector strategy
        I->>VDB: Vector similarity search (top_k)
        VDB-->>I: Relevant chunks + scores
    else Graph strategy
        I->>Neo4j: Cypher query (entities + relations)
        Neo4j-->>I: Subgraph results
    else Hybrid strategy
        I->>VDB: Vector + BM25 search
        VDB-->>I: Merged results
    end

    I-->>F: SSE: sources event

    I->>AI: Generate answer (query + context)
    loop Token streaming
        AI-->>I: Token
        I-->>F: SSE: token event
    end

    I-->>F: SSE: done event
```

## Migration Strategy

| Service | Tool | Location | Execution |
|---------|------|----------|-----------|
| Auth Server | Drizzle Kit | `rrag-auth-server/drizzle/migrations/` | `entrypoint.sh` on container start |
| Pipeline Service | Alembic | `rrag-pipeline-service/alembic/versions/` | `alembic upgrade head` on container start |
| Ingestion Service | SQLAlchemy `create_all` | `rrag-ingestion/src/rrag_ingestion/db/models.py` | `Base.metadata.create_all()` on FastAPI startup |

## Data Isolation

All data is scoped by organization, workspace, and optionally team:

- **Organization level**: `users`, `workspaces`, `teams`, `sso_configs`, `audit_logs`
- **Workspace level**: `pipelines`, `pipeline_runs`, `api_keys`, `documents`, `jobs`, `datastores`, `query_pipelines`, `conversations`
- **Team level**: `team_members`, team-owned workspaces (`scope='team'`, `owner_team_id`)
- **Cross-workspace**: `workspace_access_grants` enables controlled sharing

**Enforcement:**
- Pipeline service: `AuthContext.require_workspace_role(workspace_id, min_role)` on every endpoint
- Ingestion service: `workspace_id` query param required on every endpoint; PostgreSQL `WHERE workspace_id = :ws_id` on all queries; Neo4j graph queries scoped by datastore label; file paths include workspace_id
- Platform admins and org admins bypass workspace membership checks (resolve to "admin" role)

**Workspace scopes:**
| Scope | Owner | Auto-created |
|-------|-------|-------------|
| `personal` | `owner_user_id` | On user provisioning |
| `organization` | — | Manually created |
| `team` | `owner_team_id` | Manually created |
