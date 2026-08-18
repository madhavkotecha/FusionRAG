# 3. Component Architecture

## Auth Server Components (C4 Level 3)

```mermaid
graph TB
    subgraph "Auth Server (Node.js + Hono)"
        subgraph "Middleware"
            ReqId["Request ID"]
            Timing["Timing"]
            RateLimit["Rate Limiter<br/><i>Redis sliding window</i>"]
            AuthMW["Auth Middleware<br/><i>KC JWT + API Key</i>"]
            ErrorHandler["Error Handler"]
        end

        subgraph "Routes"
            AuthRoutes["Auth Routes<br/>/auth/*"]
            OIDCRoutes["OIDC Routes<br/>/auth/oidc/*"]
            UserRoutes["User Routes<br/>/users/*"]
            WsRoutes["Workspace Routes<br/>/workspaces/*"]
            TeamRoutes["Team Routes<br/>/teams/*"]
            ApiKeyRoutes["API Key Routes<br/>/workspaces/:id/api-keys/*"]
            AuditRoutes["Audit Routes<br/>/audit-logs/*"]
        end

        subgraph "Services"
            UserProv["UserProvisioning<br/><i>Auto-provision from KC claims,<br/>sync isPlatformAdmin</i>"]
            AuthSvc["AuthService<br/><i>Verify, resolve workspace roles</i>"]
            TokenSvc["TokenService<br/><i>SHA256 hashing</i>"]
            AuditSvc["AuditService<br/><i>Event logging</i>"]
            KcJwt["KC JWT Validator<br/><i>JWKS, dual-issuer</i>"]
        end

        subgraph "Data"
            DrizzleSchema["Drizzle Schema<br/><i>12 tables</i>"]
            RedisClient["Redis Client<br/><i>ioredis</i>"]
        end
    end

    ReqId --> Timing --> RateLimit --> AuthMW --> ErrorHandler
    AuthMW --> KcJwt
    AuthMW --> UserProv
    AuthRoutes --> AuthSvc
    AuthRoutes --> AuditSvc
    OIDCRoutes --> KcJwt
    UserRoutes --> AuthSvc
    TeamRoutes --> AuthSvc
    ApiKeyRoutes --> AuditSvc
    AuthSvc --> DrizzleSchema
    UserProv --> DrizzleSchema
    TokenSvc --> RedisClient
    RateLimit --> RedisClient
```

### Middleware Stack (execution order)

1. **Inject DB/Redis** — Sets `db` and `redis` on request context
2. **CORS** — Allow all origins (configurable), expose rate limit headers
3. **Request ID** — Generates unique ID, sets `X-Request-ID` header
4. **Timing** — Tracks response time, sets `X-Process-Time` header
5. **Rate Limiter** — Redis sorted-set sliding window; three tiers (unauthenticated/authenticated/API key)
6. **Auth** — Validates Keycloak JWT (JWKS, dual-issuer) or X-API-Key, auto-provisions user via `resolveOrProvision()`, populates `AuthContext` with `isPlatformAdmin`
7. **Error Handler** — Catches errors, returns standardized JSON responses

### Key Services

| Service | Responsibility |
|---------|---------------|
| `UserProvisioning` | Auto-provision users from Keycloak claims (create org + user + personal workspace), sync `isPlatformAdmin` on every auth |
| `AuthService` | Verify endpoints, resolve workspace roles (direct + personal + team-derived), build AuthContext |
| `KC JWT Validator` | JWKS-based RS256 signature verification with dual-issuer support (internal Docker URL + public proxy URL) |
| `TokenService` | SHA256 token hashing for API keys and refresh tokens |
| `AuditService` | Writes audit events to `audit_logs` table with full context |

---

## Pipeline Service Components (C4 Level 3)

```mermaid
graph TB
    subgraph "Pipeline Service (Python + FastAPI)"
        subgraph "API Layer"
            PipelineAPI["Pipeline Routes<br/>/api/v1/pipelines/*"]
            RunAPI["Run Routes<br/>/api/v1/runs/*"]
            CompAPI["Component Routes<br/>/api/v1/components/"]
            TplAPI["Template Routes<br/>/api/v1/templates/"]
        end

        subgraph "Dependencies"
            AuthDep["get_current_user()<br/><i>Extract X-Auth-* headers<br/>+ X-Auth-Platform-Admin</i>"]
            DBDep["get_db()<br/><i>AsyncSession provider</i>"]
            RBAC["AuthContext<br/><i>require_workspace_role()<br/>ROLE_HIERARCHY</i>"]
        end

        subgraph "Services"
            PipelineSvc["PipelineService<br/><i>CRUD + versioning</i>"]
            ExecSvc["ExecutionService<br/><i>Pipeline runner</i>"]
        end

        subgraph "Components"
            Chunkers["Chunkers<br/><i>Fixed, Semantic</i>"]
            Embedders["Embedders<br/><i>OpenAI, SentenceTransformer</i>"]
            Retrievers["Retrievers<br/><i>Vector, Hybrid</i>"]
            Generators["Generators<br/><i>LLM generation</i>"]
            Rerankers["Rerankers<br/><i>Result reranking</i>"]
            DataSources["Data Sources<br/><i>Input adapters</i>"]
        end

        subgraph "Data"
            Models["SQLAlchemy Models<br/><i>Pipeline, Version, Run</i>"]
            Templates["Template Definitions<br/><i>14 built-in templates</i>"]
        end
    end

    PipelineAPI --> AuthDep --> DBDep
    PipelineAPI --> PipelineSvc
    RunAPI --> ExecSvc
    ExecSvc --> Chunkers & Embedders & Retrievers & Generators & Rerankers & DataSources
    PipelineSvc --> Models
    TplAPI --> Templates
```

### Pipeline Component System

All components inherit from `BaseComponent`:

```python
class BaseComponent(ABC):
    async def execute(self, input_data: dict, config: dict) -> dict: ...
```

| Category | Count | Examples |
|----------|-------|---------|
| **Agents** | 9 | query_router, reflection_agent, deep_rag_agent, adaptive_retrieval_controller, rag_evaluator, self_cognition_gate |
| **Chunkers** | 8 | recursive_chunker, semantic_chunker, token_chunker, proposition_chunker, hierarchical_chunker, document_structure_chunker |
| **Embedders** | 9 | openai_embedder, sentence_transformer, bge_m3, multimodal_embedder |
| **Extractors** | 4 | entity_extractor, schema_free_extractor, subquery_decomposer |
| **Generators** | 3 | llm_generator, speculative_generator, vision_generator |
| **Graph Builders** | 2 | lightrag_graph_builder, kag_subgraph_builder |
| **Indexers** | 2 | faiss_indexer, milvus_indexer |
| **Parsers** | 3 | file_loader, multi_parser, web_scraper |
| **Planners** | 3 | corag_planner, mcts_planner, kag_planner |
| **Rerankers** | 5 | cross_encoder_reranker, cohere_reranker, llm_listwise_reranker, context_compressor |
| **Retrievers** | 7 | dense_retriever, hybrid_retriever, graph_retriever, streaming_retriever, table_retriever |
| **Storage** | 3 | kv_store, vector_store, graph_store |
| **Total** | **58** | — |

### Composite Component Framework

In addition to atomic components (single `execute()` method), the system supports **composite components** — multi-step components that encapsulate an entire sub-pipeline within a single node. This enables complex patterns like LightRAG ingestion/retrieval and agentic RAG loops to be packaged as reusable, self-contained units.

#### Architecture Overview

```mermaid
graph TB
    subgraph "Composite Component Framework"
        subgraph "Decorator API"
            CompDec["@component(name, category, ...)<br/><i>Class-level metadata</i>"]
            StepDec["@step(name, order, retry, ...)<br/><i>Method-level metadata</i>"]
        end

        subgraph "Scanning & Registration"
            Scanner["ASTScanner<br/><i>Extract decorators without executing code</i>"]
            Loader["ComponentLoader<br/><i>Load classes from MinIO-cached .py files</i>"]
            Upload["Upload API<br/><i>POST /components/upload → MinIO → scan → DB</i>"]
        end

        subgraph "Execution"
            Base["CompositeComponent<br/><i>Base class with step runner</i>"]
            StepExec["Step Executor<br/><i>Retry loops, back-edge routing</i>"]
            SSE["SSE Progress<br/><i>Redis pub/sub → real-time step events</i>"]
        end

        subgraph "Frontend"
            CompNode["CompositeNode<br/><i>Expandable visual node showing steps</i>"]
            CompMgr["ComponentManager<br/><i>Upload UI for .py files</i>"]
            SSEHook["useStepProgress hook<br/><i>Subscribe to SSE step events</i>"]
        end
    end

    CompDec --> Scanner
    StepDec --> Scanner
    Scanner --> Upload
    Upload -->|"Store .py"| MinIO[(MinIO)]
    Upload -->|"Register metadata"| DB[(PostgreSQL)]
    Loader -->|"Load .py at runtime"| MinIO
    Base --> StepExec
    StepExec --> SSE
    SSE -->|"Redis pub/sub"| SSEHook
    CompNode --> SSEHook
```

#### Decorator API

Composite components are defined using two decorators that attach metadata to Python classes and methods:

```python
from rrag_pipeline.decorators import component, step

@component(
    name="lightrag_ingestion",
    category="composite",
    description="LightRAG 5-step ingestion pipeline",
    config_schema={"chunk_size": {"type": "integer", "default": 1200}},
)
class LightRAGIngestion(CompositeComponent):

    @step(name="chunk", order=1, retry=2)
    async def chunk_documents(self, input_data, config):
        ...

    @step(name="extract_entities", order=2, retry=1)
    async def extract_entities(self, input_data, config):
        ...

    @step(name="merge_graph", order=3)
    async def merge_graph(self, input_data, config):
        ...

    @step(name="store_graph", order=4)
    async def store_graph(self, input_data, config):
        ...

    @step(name="store_vectors", order=5)
    async def store_vectors(self, input_data, config):
        ...
```

The `@component` decorator captures class-level metadata (name, category, description, config schema, input/output ports). The `@step` decorator captures method-level metadata (step name, execution order, retry count, optional routing back-edges).

#### AST Scanner

The AST scanner extracts decorator metadata **without executing user code**. It parses the `.py` file into an abstract syntax tree and walks the tree to find `@component` and `@step` decorators, extracting their keyword arguments as static metadata.

This approach is critical for security: user-uploaded component files are never imported or executed during the registration phase. Only the decorator metadata is read.

**Limitations:** The scanner can only extract literal values (strings, numbers, dicts, lists) from decorator arguments. Dynamic expressions or variable references in decorator arguments are not captured.

#### CompositeComponent Base Class

All composite components inherit from `CompositeComponent`, which provides:

- **Step discovery** — Reads `@step`-annotated methods and sorts them by `order`
- **Step execution loop** — Runs steps sequentially, passing output of one step as input to the next
- **Retry logic** — Retries failed steps up to the configured `retry` count with exponential backoff
- **Back-edge routing** — Steps can declare routing targets (e.g., "go back to step 2"), enabling loops such as agentic evaluate-and-retry cycles
- **SSE progress publishing** — After each step completes, publishes a progress event to Redis pub/sub

#### Component Upload and Loading

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant API as Pipeline Service API
    participant MinIO
    participant Scanner as AST Scanner
    participant DB as PostgreSQL

    User->>Frontend: Select .py file in ComponentManager
    Frontend->>API: POST /api/v1/components/upload<br/>(multipart file + workspace_id)
    API->>Scanner: Parse file AST, extract decorators
    Scanner-->>API: {name, category, steps[], config_schema, ...}
    API->>MinIO: Store .py in rrag-components bucket<br/>(workspace_id/name/hash.py)
    API->>DB: INSERT INTO components<br/>(source="custom", is_composite=true, steps=JSON, file_path, file_hash)
    API-->>Frontend: {component metadata}

    Note over API: At pipeline execution time:
    API->>MinIO: Download .py to local cache
    API->>API: importlib.util.spec_from_file_location()
    API->>API: Instantiate component class
    API->>API: Execute steps with CompositeComponent runner
```

The `ComponentLoader` caches downloaded `.py` files locally and uses `file_hash` to detect changes. Files are only re-downloaded when the hash changes.

#### SSE Step Progress

During composite component execution, each step completion publishes a progress event:

```
Channel: rrag:run:{run_id}:steps
Event data: {"step": "extract_entities", "order": 2, "total": 5, "status": "completed", "duration_ms": 1230}
```

The frontend `useStepProgress` hook subscribes to the SSE endpoint `GET /api/v1/pipelines/{id}/runs/{run_id}/stream` and updates the `CompositeNode` UI in real time, showing which step is active, completed, or failed.

#### Concrete Composite Components

| Component | Category | Steps | Back-edges | Description |
|-----------|----------|-------|------------|-------------|
| **LightRAG Ingestion** | ingestion | 5 (chunk, extract, merge, store graph, store vectors) | None | Full LightRAG ingestion: chunking, entity extraction, graph merge, dual storage |
| **LightRAG Retrieval** | retrieval | 5 (keywords, graph search, vector search, assemble, generate) | assemble → keywords (on low confidence) | Dual-mode retrieval with keyword extraction, graph + vector search, assembly, and generation |
| **Agentic RAG Retrieval** | retrieval | 6 (analyze, plan, execute tools, assemble evidence, evaluate & decide, generate) | evaluate → plan (agent loop) | Agent-driven retrieval with tool execution, evidence assembly, and iterative refinement loop |

#### Frontend: Expandable CompositeNode

Composite components render as expandable nodes in the pipeline editor canvas. When collapsed, they appear as a single node with a step count badge. When expanded, they reveal their internal steps with status indicators:

- **Idle** — Step has not started (gray)
- **Running** — Step is currently executing (blue, animated)
- **Completed** — Step finished successfully (green, with duration)
- **Failed** — Step encountered an error (red, with error message)
- **Retrying** — Step failed and is being retried (amber)

The `ComponentManager` page provides a UI for uploading custom `.py` component files, viewing registered custom components, and deleting them.

### Built-in Templates (23)

| Template | Description |
|----------|-------------|
| `vanilla_rag` | Basic retrieve-and-generate pipeline |
| `rag_with_reranker` | RAG with result reranking step |
| `knowledge_graph` | Graph-based retrieval |
| `agentic_rag` | Agent-driven multi-step RAG |
| `kag_three_layer` | Three-layer knowledge augmented generation |
| `deep_research` | Multi-hop research pipeline |
| `e2e_vanilla_rag` | End-to-end vanilla RAG with ingestion |
| `e2e_hybrid_search` | End-to-end with hybrid (vector + BM25) search |
| `e2e_graphrag` | End-to-end graph RAG |
| `e2e_agentic_rag` | End-to-end agentic RAG |
| `parent_child_chunking` | Hierarchical chunking strategy |
| `multimodal_ingestion` | Multi-format document ingestion |
| `corrective_rag` | RAG with self-correction loop |
| `self_rag` | Self-reflective RAG |
| `deep_rag_reasoning` | Deep reasoning with iterative retrieval |
| `speculative_rag` | Speculative generation with parallel drafts |
| `adaptive_retrieval` | Complexity-based adaptive retrieval routing |
| `streaming_rag` | Real-time streaming RAG pipeline |
| `table_qa` | Table-aware question answering |
| `vision_rag` | Vision-augmented RAG for image+text |
| `mcts_deep_research` | Monte Carlo tree search research pipeline |
| `contextual_ingestion` | Context-enriched document ingestion |
| `proposition_ingestion` | Proposition-based chunking ingestion |

---

## Ingestion Service Components (C4 Level 3)

```mermaid
graph TB
    subgraph "Ingestion Service (Python + FastAPI)"
        subgraph "API Layer"
            DocAPI["Document Routes<br/>/api/v1/ingestion/documents/*"]
            JobAPI["Job Routes<br/>/api/v1/ingestion/jobs/*"]
            QueryAPI["Query Routes<br/>/api/v1/ingestion/query/*"]
            ChatAPI["Chat Routes<br/>/api/v1/ingestion/chat/*"]
            PipeAPI["Pipeline Routes<br/>/api/v1/ingestion/pipelines/*"]
            DSAPI["DataStore Routes<br/>/api/v1/ingestion/datastores/*"]
            QPAPI["QueryPipeline Routes<br/>/api/v1/ingestion/query-pipelines/*"]
            CompRegAPI["Component Routes<br/>/api/v1/ingestion/components/*"]
            AdminAPI["Admin Routes<br/>/api/v1/ingestion/admin/*"]
        end

        subgraph "Dependencies"
            IngAuthDep["get_current_user()<br/><i>AuthContext from X-Auth-*</i>"]
            IngRBAC["AuthContext<br/><i>require_workspace_role()<br/>ROLE_HIERARCHY</i>"]
        end

        subgraph "Core"
            Registry["ComponentRegistry<br/><i>Auto-discovery</i>"]
            Queue["Queue System<br/><i>RQ + Redis</i>"]
            PipeEngine["PipelineEngine<br/><i>Step execution</i>"]
            FAISS["FAISS Index<br/><i>Vector search</i>"]
        end

        subgraph "Services"
            QPStore["QueryPipelineStore<br/><i>PostgreSQL CRUD (workspace-scoped)</i>"]
            QueryExec["QueryExecutor<br/><i>Retrieve + rerank + generate</i>"]
            LLMSvc["LLM Service<br/><i>OpenAI, function-calling</i>"]
        end

        subgraph "Cache"
            CacheLayer["Cache-Aside Layer<br/><i>Redis TTL 30s–300s<br/>rrag:ing:{entity}:{ws_id}:{id}</i>"]
        end

        subgraph "SSE"
            JobStream["Job Stream<br/><i>GET /jobs/stream</i>"]
            QueryStream["Query Stream<br/><i>POST /query/stream</i>"]
            ChatStream["Chat Stream<br/><i>POST /chat/stream</i>"]
        end

        subgraph "Storage"
            PGStore["PostgreSQL<br/><i>documents, datastores,<br/>jobs, query_pipelines</i>"]
            RedisStore["Redis<br/><i>Queue, live progress,<br/>conversations</i>"]
            MinIOStore["MinIO<br/><i>S3 bucket: rrag-documents</i>"]
            QdrantStore["Qdrant<br/><i>Vector collections</i>"]
            OSStore["OpenSearch<br/><i>Hybrid search indexes</i>"]
            Neo4jStore["Neo4j<br/><i>Knowledge graph</i>"]
        end
    end

    subgraph "RQ Worker (separate container)"
        Worker["Worker Process<br/><i>Dequeue & execute</i>"]
    end

    IngAuthDep --> IngRBAC
    DocAPI --> IngRBAC
    JobAPI --> IngRBAC
    ChatAPI --> IngRBAC
    AdminAPI --> IngRBAC
    DocAPI --> MinIOStore & PGStore
    JobAPI --> Queue
    QueryAPI --> QueryExec
    ChatAPI --> LLMSvc --> QueryExec
    QPAPI --> QPStore
    DSAPI --> PGStore
    QPStore --> PGStore
    Queue --> RedisStore
    PGStore -.->|"cache-aside"| CacheLayer
    Worker --> PGStore & Neo4jStore & QdrantStore & OSStore & MinIOStore
    Worker -->|"Process pipeline"| PipeEngine --> Registry
    JobStream -.->|"SSE"| RedisStore
    QueryStream -.->|"SSE tokens"| QueryAPI
    ChatStream -.->|"SSE tokens"| ChatAPI
```

### Real-time Features

| Feature | Mechanism | Endpoint |
|---------|-----------|----------|
| Job monitoring | SSE (polling Redis every 2s) | `GET /api/v1/ingestion/jobs/stream?workspace_id=` |
| Streaming query | SSE with token-by-token LLM output | `POST /api/v1/ingestion/query/stream?workspace_id=` |
| Streaming chat | SSE with LLM tool-calling + token streaming | `POST /api/v1/ingestion/chat/stream?workspace_id=` |
| Conversation | Multi-turn with conversation_id tracking | `GET /chat/conversations/{id}?workspace_id=` |

---

## Frontend Components (C4 Level 3)

```mermaid
graph TB
    subgraph "React SPA"
        subgraph "Pages"
            Login["LoginPage<br/><i>OIDC redirect to Keycloak</i>"]
            OIDCCallback["OidcCallbackPage<br/><i>PKCE code exchange</i>"]
            Dashboard["DashboardPage"]
            PipeEdit["PipelineEditorPage<br/><i>XYFlow + Monaco</i>"]
            PipeRuns["PipelineRunsPage"]
            QueryPipes["QueryPipelinesPage"]
            Chat["ChatPage<br/><i>SSE streaming</i>"]
            Docs["DocumentsPage"]
            IngPipes["IngestionPipelinesPage"]
            IngJobs["IngestionJobsPage"]
            DataStores["DataStoresPage"]
            NewDS["NewDataStorePage<br/><i>Create wizard</i>"]
        end

        subgraph "Admin Pages"
            AdminDash["AdminDashboardPage"]
            UserMgmt["UserManagementPage"]
            TeamMgmt["TeamManagementPage"]
            WsMgmt["WorkspaceManagementPage"]
            ApiKeys["ApiKeysPage"]
            AuditLog["AuditLogPage"]
            QueueMgmt["QueueManagementPage"]
            SvcHealth["ServiceHealthPage"]
        end

        subgraph "State (Zustand)"
            AuthStore["Auth Store<br/><i>KC tokens, user, isPlatformAdmin</i>"]
            WsStore["Workspace Store<br/><i>Active workspace selection</i>"]
            EditorStore["Pipeline Editor Store<br/><i>nodes, edges, components</i>"]
        end

        subgraph "API Client (Axios)"
            AuthAPI["auth.ts + oidc.ts"]
            PipeAPI2["pipelines.ts"]
            ChatAPI2["chat.ts"]
            IngAPI["ingestion.ts"]
            TeamsAPI["teams.ts"]
            AdminAPIClient["admin.ts"]
        end

        subgraph "Auth"
            AuthGuard["AuthGuard<br/><i>KC token refresh + session restore</i>"]
            AdminGuard["AdminGuard<br/><i>org_admin check</i>"]
            PKCE["PKCE Utils<br/><i>verifier + challenge</i>"]
        end

        subgraph "Layout"
            AppShell["AppShell<br/><i>Sidebar + Header + WorkspaceSwitcher</i>"]
        end
    end

    Login --> PKCE --> OIDCCallback --> AuthAPI --> AuthStore
    AuthGuard --> AuthStore
    AdminGuard --> AuthStore
    PipeEdit --> EditorStore --> PipeAPI2
    Chat --> ChatAPI2
    IngJobs --> IngAPI
    AdminDash --> AdminAPIClient
```

### Route Structure

```
/login                  → LoginPage (public, OIDC redirect)
/oidc/callback          → OidcCallbackPage (public, PKCE exchange)
/                       → DashboardPage (protected)
/chat                   → ChatPage (protected)
/query-pipelines        → QueryPipelinesPage (protected)
/query-pipelines/:id/edit → PipelineEditorPage (protected)
/pipelines/:id/edit     → PipelineEditorPage (protected)
/pipelines/:id/runs     → PipelineRunsPage (protected)
/ingestion/documents    → DocumentsPage (protected)
/ingestion/pipelines    → IngestionPipelinesPage (protected)
/ingestion/jobs         → IngestionJobsPage (protected)
/ingestion/jobs/:id     → IngestionJobDetailPage (protected)
/ingestion/datastores   → DataStoresPage (protected)
/ingestion/datastores/new → NewDataStorePage (protected)
/admin                  → AdminDashboardPage (admin only)
/admin/users            → UserManagementPage (admin only)
/admin/teams            → TeamManagementPage (admin only)
/admin/workspaces       → WorkspaceManagementPage (admin only)
/admin/api-keys         → ApiKeysPage (admin only)
/admin/audit-logs       → AuditLogPage (admin only)
/admin/queues           → QueueManagementPage (admin only)
/admin/health           → ServiceHealthPage (admin only)
/admin/settings         → SystemSettingsPage (admin only)
```

Protected routes are wrapped in `AuthGuard` + `AppShell` layout.
Admin routes add `AdminGuard` (checks `orgRole === 'org_admin'`).
