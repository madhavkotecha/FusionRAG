# 09 — Data Flow Diagrams

> End-to-end data flows for authentication, document ingestion, RAG query, pipeline management, and chat.

---

## 1. Authentication Flow (OIDC + PKCE)

```mermaid
sequenceDiagram
    actor User
    participant Browser
    participant Frontend
    participant Traefik
    participant AuthServer
    participant Keycloak
    participant PostgreSQL

    User->>Browser: Navigate to /login
    Browser->>Frontend: Load LoginPage
    Frontend->>AuthServer: GET /auth/oidc/config
    AuthServer-->>Frontend: {authEndpoint, tokenEndpoint, clientId}

    Note over Frontend: Generate PKCE verifier + challenge<br/>Store verifier in sessionStorage

    Frontend->>Keycloak: Redirect to authEndpoint<br/>response_type=code, code_challenge
    User->>Keycloak: Enter credentials
    Keycloak-->>Browser: Redirect to /oidc/callback?code=ABC

    Browser->>Frontend: Load OidcCallbackPage
    Frontend->>Keycloak: POST tokenEndpoint<br/>grant_type=authorization_code<br/>code=ABC, code_verifier=XYZ
    Keycloak-->>Frontend: {access_token, refresh_token, id_token}

    Note over Frontend: Store KC tokens in localStorage

    Frontend->>Traefik: GET /auth/me<br/>Authorization: Bearer {access_token}
    Traefik->>AuthServer: GET /auth/me (passthrough)
    AuthServer->>AuthServer: Validate KC JWT (JWKS)
    AuthServer->>PostgreSQL: Find/create user by email (auto-provision)
    AuthServer->>AuthServer: Sync isPlatformAdmin from KC roles
    AuthServer->>PostgreSQL: Resolve workspace memberships
    AuthServer-->>Frontend: {user, workspaces, orgRole, isPlatformAdmin}

    Note over Frontend: Store user in Zustand auth store<br/>Navigate to Dashboard
```

---

## 2. Request Authentication (ForwardAuth)

```mermaid
sequenceDiagram
    participant Client
    participant Traefik
    participant AuthServer
    participant Redis
    participant Upstream

    Client->>Traefik: GET /api/v1/pipelines<br/>Authorization: Bearer {token}
    Traefik->>AuthServer: GET /auth/verify<br/>(forward all headers)

    alt Bearer Token
        AuthServer->>AuthServer: Validate KC JWT (JWKS cache)
        AuthServer->>Redis: Check rate limit (sliding window)
        Redis-->>AuthServer: {remaining: 298}
    else API Key
        AuthServer->>AuthServer: Hash X-API-Key (SHA256)
        AuthServer->>AuthServer: Lookup key_hash in DB
        AuthServer->>Redis: Check rate limit (key tier)
    end

    AuthServer-->>Traefik: 200 OK<br/>X-Auth-User-Id: uuid<br/>X-Auth-Org-Id: uuid<br/>X-Auth-Org-Role: member<br/>X-Auth-Email: user@example.com<br/>X-Auth-Workspace-Roles: {"ws1":"developer"}<br/>X-Auth-Platform-Admin: false

    Traefik->>Upstream: GET /api/v1/pipelines<br/>+ X-Auth-* headers
    Upstream->>Upstream: Parse AuthContext from headers<br/>(including isPlatformAdmin)
    Upstream-->>Traefik: 200 {pipelines: [...]}
    Traefik-->>Client: 200 {pipelines: [...]}
```

---

## 3. Document Ingestion Flow

```mermaid
sequenceDiagram
    actor User
    participant Frontend
    participant Traefik
    participant Ingestion as Ingestion API
    participant PG as PostgreSQL
    participant Redis
    participant MinIO
    participant RQWorker as RQ Worker
    participant Neo4j
    participant VDB as Qdrant/OpenSearch

    User->>Frontend: Upload documents
    Frontend->>Traefik: POST /api/v1/ingestion/documents/upload?workspace_id=ws1<br/>(multipart/form-data)
    Traefik->>Ingestion: (after ForwardAuth)

    Note over Ingestion: Validate workspace_id via AuthContext<br/>require_workspace_role("developer")<br/>Sanitize filenames, enforce size limits

    Ingestion->>MinIO: Store file in rrag-documents bucket
    Ingestion->>PG: INSERT INTO documents (metadata)
    Ingestion-->>Frontend: {documents: [{id, filename, ...}]}

    User->>Frontend: Start ingestion pipeline
    Frontend->>Traefik: POST /api/v1/ingestion/jobs?workspace_id=ws1
    Traefik->>Ingestion: {pipeline_name, document_ids, datastore_id}
    Ingestion->>PG: INSERT INTO jobs (status: queued)
    Ingestion->>Redis: RQ enqueue(run_pipeline_job, job_id)
    Ingestion-->>Frontend: {job_id, status: "queued"}

    Frontend->>Traefik: GET /api/v1/ingestion/jobs/{id}/stream?workspace_id=ws1
    Note over Frontend: SSE connection established

    RQWorker->>Redis: Dequeue job
    RQWorker->>PG: Load job record (find_job_by_id_sync)
    RQWorker->>PG: Update job status → running
    RQWorker->>MinIO: Read document files from rrag-documents bucket

    loop For each pipeline step
        RQWorker->>RQWorker: Execute component<br/>(parse → chunk → embed → index)
        RQWorker->>Redis: Update live progress %
        Redis-->>Frontend: SSE: {progress, current_step}
    end

    RQWorker->>Neo4j: Store knowledge graph (if graph builder step)
    RQWorker->>VDB: Index embeddings (Qdrant/OpenSearch)
    RQWorker->>PG: Create/update DataStore record
    RQWorker->>PG: Update job → completed (with step_results)

    Redis-->>Frontend: SSE: {status: "completed", datastore_id}
```

---

## 4. RAG Query Flow

```mermaid
sequenceDiagram
    actor User
    participant Frontend
    participant Traefik
    participant Ingestion as Ingestion API
    participant PG as PostgreSQL
    participant Cache as Redis Cache
    participant VDB as Qdrant/OpenSearch
    participant Neo4j
    participant LLM as OpenAI API

    User->>Frontend: Enter query in ChatPage
    Frontend->>Traefik: POST /api/v1/ingestion/chat/stream?workspace_id=ws1<br/>{query, pipeline_ids, conversation_id}

    Note over Frontend: SSE connection for streaming

    Traefik->>Ingestion: (after ForwardAuth)
    Note over Ingestion: require_workspace_role("developer")
    Ingestion->>Cache: Check cache for QueryPipeline configs
    alt Cache miss
        Ingestion->>PG: SELECT FROM query_pipelines WHERE workspace_id = ws1
        Ingestion->>Cache: Populate cache (TTL 300s)
    end
    Ingestion->>Cache: Load conversation history (rrag:conv:{ws1}:{id})

    Ingestion->>LLM: Chat completion with tools<br/>(query pipelines as function definitions)
    LLM-->>Ingestion: tool_call: {pipeline_id, query}

    Note over Ingestion: Execute query pipeline

    Ingestion->>PG: Load DataStore config (with cache-aside)
    alt Vector Retrieval
        Ingestion->>VDB: Embed query → similarity search (Qdrant)
        VDB-->>Ingestion: Top-K chunks with scores
    else Graph Retrieval
        Ingestion->>Neo4j: Cypher query (entities + relations)
        Neo4j-->>Ingestion: Subgraph results
    else Hybrid
        Ingestion->>VDB: BM25 + vector search (OpenSearch)
        Note over Ingestion: Merge + deduplicate results
    end

    opt Reranking enabled
        Ingestion->>LLM: Rerank results (cross-encoder/listwise)
        LLM-->>Ingestion: Reranked results
    end

    Ingestion->>LLM: Generate answer with context<br/>(tool response with retrieved chunks)

    loop Token streaming
        LLM-->>Ingestion: Token chunk
        Ingestion-->>Frontend: SSE: {type: "token", content: "..."}
    end

    Ingestion->>Cache: Save conversation turn (rrag:conv:{ws1}:{id})
    Ingestion-->>Frontend: SSE: {type: "done", traces: [...]}
```

---

## 5. Pipeline Builder Flow

```mermaid
sequenceDiagram
    actor User
    participant Frontend
    participant Traefik
    participant PipelineSvc as Pipeline Service
    participant PostgreSQL
    participant Ingestion as Ingestion API

    User->>Frontend: Open Dashboard
    Frontend->>Traefik: GET /api/v1/pipelines?workspace_id=ws1
    Traefik->>PipelineSvc: (after ForwardAuth + X-Auth headers)
    PipelineSvc->>PostgreSQL: SELECT * FROM pipelines WHERE workspace_id = 'ws1'
    PostgreSQL-->>PipelineSvc: [pipeline1, pipeline2, ...]
    PipelineSvc-->>Frontend: {pipelines: [...]}

    User->>Frontend: Create new pipeline (from template or blank)
    Frontend->>Traefik: POST /api/v1/pipelines<br/>{name, workspace_id, definition, pipeline_type}
    PipelineSvc->>PostgreSQL: INSERT INTO pipelines

    alt pipeline_type == "query"
        PipelineSvc->>PipelineSvc: compile_query_pipeline()<br/>Extract retriever/reranker/generator config
        PipelineSvc->>Ingestion: PUT /api/v1/ingestion/query-pipelines/{id}<br/>{compiled config}
    end

    PipelineSvc-->>Frontend: {pipeline: {id, ...}}

    User->>Frontend: Edit pipeline in visual editor<br/>(drag components, connect edges)

    Note over Frontend: React Flow canvas<br/>ComponentPalette → drag → PipelineCanvas<br/>PropertyInspector edits node config<br/>YamlEditor shows/edits YAML representation

    User->>Frontend: Save pipeline
    Frontend->>Traefik: PUT /api/v1/pipelines/{id}<br/>{definition: {nodes, edges, viewport}}
    PipelineSvc->>PostgreSQL: UPDATE pipelines SET definition = ...

    User->>Frontend: Create version snapshot
    Frontend->>Traefik: POST /api/v1/pipelines/{id}/versions
    PipelineSvc->>PostgreSQL: INSERT INTO pipeline_versions<br/>(auto-increment version number)

    User->>Frontend: Run pipeline
    Frontend->>Traefik: POST /api/v1/pipelines/{id}/run
    PipelineSvc->>PostgreSQL: INSERT INTO pipeline_runs (status: pending)
    PipelineSvc->>PipelineSvc: execute_pipeline()<br/>Topological sort → execute nodes
    PipelineSvc->>PostgreSQL: UPDATE pipeline_runs (status: completed, result: {...})
    PipelineSvc-->>Frontend: {run: {id, status, result}}
```

---

## 6. Multi-Tenant Data Isolation

```mermaid
graph TD
    subgraph Organization [Organization: Acme Corp]
        subgraph WS1 [Workspace: Engineering]
            P1[Pipeline: QA Bot]
            P2[Pipeline: Code Search]
            D1[DataStore: Docs Index]
            M1[Members: alice=admin, bob=developer]
        end
        subgraph WS2 [Workspace: Marketing]
            P3[Pipeline: Content RAG]
            D2[DataStore: Blog Index]
            M2[Members: carol=admin, dave=viewer]
        end
        subgraph WS3 [Personal: alice]
            P4[Pipeline: Sandbox]
        end
        T1[Team: Platform]
        T2[Team: Growth]
    end

    style Organization fill:#f0f0ff,stroke:#333
    style WS1 fill:#e8f5e9,stroke:#4caf50
    style WS2 fill:#fff3e0,stroke:#ff9800
    style WS3 fill:#e3f2fd,stroke:#2196f3
```

**Isolation enforced at:**
1. **Gateway**: Traefik ForwardAuth → Auth Server validates token and resolves workspace roles
2. **Auth Server**: `X-Auth-Workspace-Roles` header contains JSON map of `{workspace_id: role}`, `X-Auth-Platform-Admin` flag
3. **Upstream services**: `AuthContext.require_workspace_role(workspace_id, min_role)` checks membership with hierarchical RBAC (viewer < developer < admin)
4. **Pipeline service**: `WHERE workspace_id = :ws_id` on all SQL queries
5. **Ingestion service**: `WHERE workspace_id = :ws_id` on all PostgreSQL queries, workspace-scoped cache keys (`rrag:ing:{entity}:{ws_id}:{id}`), workspace-scoped file paths (`/data/documents/{ws_id}/`), datastore-scoped Neo4j graph queries
6. **Platform admin / Org admin bypass**: Resolves to "admin" role for any workspace

---

## 7. Token Refresh Flow

```mermaid
sequenceDiagram
    participant Frontend
    participant Traefik
    participant Service
    participant Keycloak

    Frontend->>Traefik: API request (expired access token)
    Traefik->>Service: ForwardAuth → 401

    Note over Frontend: Axios 401 interceptor triggers

    Frontend->>Keycloak: POST tokenEndpoint<br/>grant_type=refresh_token<br/>refresh_token={stored_token}
    Keycloak-->>Frontend: {new_access_token, new_refresh_token}

    Note over Frontend: Update localStorage + Zustand store<br/>Retry original request with new token

    Frontend->>Traefik: Retry API request (new token)
    Traefik->>Service: ForwardAuth → 200 ✓
    Service-->>Frontend: Response
```

**Concurrency handling:** The frontend queues concurrent 401 responses and only refreshes once, then replays all queued requests.

---

## 8. Component Pipeline Execution (Ingestion Worker)

```mermaid
graph LR
    subgraph Input
        DOC[Documents<br/>PDF, DOCX, TXT]
    end

    subgraph Pipeline Steps
        PARSE[Parser<br/>file_loader]
        CHUNK[Chunker<br/>recursive_chunker]
        EMBED[Embedder<br/>openai_embedder]
        EXTRACT[Extractor<br/>entity_extractor]
        GRAPH[Graph Builder<br/>lightrag_graph_builder]
        INDEX[Indexer<br/>faiss_indexer]
    end

    subgraph Storage
        QD[(Qdrant Vectors)]
        OS[(OpenSearch Index)]
        NEO[(Neo4j Graph)]
        PG2[(PostgreSQL Metadata)]
    end

    DOC --> PARSE
    PARSE -->|documents| CHUNK
    CHUNK -->|chunks| EMBED
    CHUNK -->|chunks| EXTRACT
    EMBED -->|embeddings| INDEX
    EXTRACT -->|entities, relations| GRAPH
    INDEX --> QD
    INDEX --> OS
    GRAPH --> NEO
    INDEX --> PG2
    GRAPH --> PG2

    style Input fill:#e3f2fd
    style Storage fill:#e8f5e9
```

---

## 9. Custom Component Upload Flow

```mermaid
sequenceDiagram
    actor User
    participant Frontend
    participant Traefik
    participant PipelineSvc as Pipeline Service
    participant Scanner as AST Scanner
    participant MinIO
    participant PostgreSQL

    User->>Frontend: Open ComponentManager, select .py file
    Frontend->>Traefik: POST /api/v1/components/upload?workspace_id=ws1<br/>(multipart/form-data)
    Traefik->>PipelineSvc: (after ForwardAuth)

    Note over PipelineSvc: require_workspace_role("developer")

    PipelineSvc->>Scanner: Parse file AST (no code execution)
    Scanner->>Scanner: Walk AST tree<br/>Find @component decorator → extract class metadata<br/>Find @step decorators → extract step metadata

    alt Valid composite component
        Scanner-->>PipelineSvc: {name, category, steps[], config_schema, ports}
    else No decorators or invalid syntax
        Scanner-->>PipelineSvc: Error: invalid component file
        PipelineSvc-->>Frontend: 400 {error: "No @component decorator found"}
    end

    PipelineSvc->>PipelineSvc: Compute SHA-256 file hash
    PipelineSvc->>MinIO: PUT rrag-components/{ws1}/{type}/{hash}.py
    PipelineSvc->>PostgreSQL: INSERT INTO components<br/>(source=custom, is_composite=true, steps=JSON,<br/>workspace_id, file_path, file_hash)
    PipelineSvc-->>Frontend: 201 {component metadata}

    Note over Frontend: Component appears in palette<br/>with "Custom" badge
```

---

## 10. Composite Component Execution Flow

```mermaid
sequenceDiagram
    actor User
    participant Frontend
    participant Traefik
    participant PipelineSvc as Pipeline Service
    participant Loader as ComponentLoader
    participant MinIO
    participant Runner as CompositeComponent Runner
    participant Redis
    participant Neo4j
    participant Qdrant

    User->>Frontend: Run pipeline containing composite node
    Frontend->>Traefik: POST /api/v1/pipelines/{id}/run?workspace_id=ws1
    Traefik->>PipelineSvc: (after ForwardAuth)

    PipelineSvc->>PipelineSvc: Topological sort of pipeline DAG
    Note over PipelineSvc: Reach composite node (e.g., LightRAG Ingestion)

    PipelineSvc->>Loader: Load component class for "lightrag_ingestion"
    Loader->>Loader: Check local file cache (by file_hash)
    alt Cache miss
        Loader->>MinIO: GET rrag-components/{ws1}/lightrag_ingestion/{hash}.py
        MinIO-->>Loader: .py file bytes
        Loader->>Loader: Write to local cache directory
    end
    Loader->>Loader: importlib.util.spec_from_file_location()<br/>Instantiate component class

    Frontend->>Traefik: GET /api/v1/pipelines/{id}/runs/{runId}/stream?workspace_id=ws1
    Note over Frontend: SSE connection established

    loop For each step (ordered by @step.order)
        Runner->>Redis: PUBLISH rrag:run:{runId}:steps<br/>{step, order, status: "running"}
        Redis-->>Frontend: SSE: step_start

        Runner->>Runner: Execute step method(input_data, config)

        alt Step succeeds
            Runner->>Redis: PUBLISH step_complete event
            Redis-->>Frontend: SSE: step_complete {duration_ms}
        else Step fails (retries remaining)
            Runner->>Redis: PUBLISH step_retry event
            Redis-->>Frontend: SSE: step_retry {attempt, error}
            Runner->>Runner: Exponential backoff → retry step
        else Step fails (no retries left)
            Runner->>Redis: PUBLISH step_failed event
            Redis-->>Frontend: SSE: step_failed {error}
        end

        opt Back-edge routing triggered
            Note over Runner: e.g., evaluate step routes back to plan step<br/>(agentic loop)
            Runner->>Runner: Jump to target step (by order)
        end
    end

    Note over Runner: Steps may interact with storage:
    Runner->>Neo4j: Store/query knowledge graph
    Runner->>Qdrant: Store/query vector embeddings
    Runner->>Redis: PUBLISH run_complete
    Redis-->>Frontend: SSE: run_complete {result}
```

**Data transformations at each step:**

| Step | Input | Output | Typical Size |
|------|-------|--------|-------------|
| Parser | Raw file bytes | `Document(raw_text, metadata)` | 1 doc → 10-500KB text |
| Chunker | Document text | `Chunk(content, tokens, order_index)` | 1 doc → 10-200 chunks |
| Embedder | Chunk text | `EmbeddingResult(vector, text)` | 1 chunk → 1536-dim float32 |
| Extractor | Chunk text | `Entity(name, type, description)` | 1 doc → 20-100 entities |
| Graph Builder | Entities + Relations | `SubGraph(nodes, edges)` | 1 doc → 50-500 edges |
| Indexer | Embeddings | Qdrant collection / OpenSearch index | N vectors × 1536 dims |
