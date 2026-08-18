# ADR-0026: Hierarchical Composite Components

- **Status:** Accepted
- **Date:** 2026-03-16
- **Deciders:** Architecture Team
- **Relates to:** ADR-0004 (Visual Pipeline Builder), ADR-0016 (Component Registry Pattern), ADR-0017 (SSE Streaming Responses)

## Context

The pipeline builder system (ADR-0004) supports atomic components — single-purpose units with one `execute()` method. However, real-world RAG patterns like LightRAG ingestion, LightRAG retrieval, and agentic RAG loops require multiple coordinated steps that share intermediate state:

- **LightRAG Ingestion** needs 5 sequential steps: chunk documents, extract entities, merge knowledge graph, store graph in Neo4j, store vectors in Qdrant.
- **LightRAG Retrieval** needs 5 steps with a conditional back-edge: extract keywords, graph search, vector search, assemble context, generate — with the option to loop back from assembly to keywords when confidence is low.
- **Agentic RAG Retrieval** needs 6 steps with an agent loop: analyze query, plan retrieval, execute tools, assemble evidence, evaluate & decide, generate — where evaluation can loop back to planning.

Expressing these as flat sequences of atomic nodes in the pipeline canvas creates visual clutter, loses the semantic grouping, and makes it difficult to reuse a multi-step pattern across pipelines. Users also need the ability to create and upload their own composite components without modifying the service codebase.

### Forces

- Components must remain easy to author — a Python developer should be able to define one without learning a framework DSL
- User-uploaded code must be registered safely without arbitrary code execution during scanning
- The pipeline editor must visualize composite components as expandable/collapsible nodes
- Real-time step progress must be visible during execution
- The system must support back-edge routing for iterative patterns (agent loops, retry-on-low-confidence)

## Decision

Implement a **decorator-based composite component framework** with the following architecture:

### 1. Decorator API

Two Python decorators define composite components:

- `@component(name, category, description, config_schema, input_ports, output_ports)` — Class-level decorator that attaches component metadata
- `@step(name, order, retry=0, route_to=None)` — Method-level decorator that marks a method as an execution step

Steps execute in `order` sequence. Each step receives the previous step's output as input. The `retry` parameter enables automatic retry with exponential backoff. The `route_to` parameter names a step to jump to (back-edge), enabling loops.

### 2. AST Scanner

A static analysis scanner parses uploaded `.py` files into Python AST and extracts `@component` and `@step` decorator metadata **without importing or executing the file**. This is the security boundary: user code is never run during registration.

The scanner extracts only literal values (strings, numbers, booleans, dicts, lists) from decorator keyword arguments. Dynamic expressions are ignored and flagged as warnings.

### 3. CompositeComponent Base Class

All composite components inherit from `CompositeComponent`, which provides:

- Step discovery from `@step` annotations
- Sequential step execution with input/output chaining
- Configurable retry per step (exponential backoff: base 2s, max 30s)
- Back-edge routing: when a step sets `route_to` in its return value, execution jumps to the named step (with a configurable max loop count to prevent infinite loops)
- SSE progress publishing after each step via Redis pub/sub

### 4. Component Upload API

- `POST /api/v1/components/upload` accepts a `.py` file (multipart form data)
- The file is AST-scanned to extract metadata
- The file is stored in a MinIO bucket (`rrag-components`) at path `{workspace_id}/{component_type}/{file_hash}.py`
- A record is inserted into the `components` table with `source="custom"`, `is_composite=true`, step metadata as JSON, and the MinIO file path and SHA-256 hash
- `DELETE /api/v1/components/custom/{type}` removes both the DB record and the MinIO file

### 5. ComponentLoader

At pipeline execution time, the `ComponentLoader`:

1. Reads the component record from the database to get `file_path` and `file_hash`
2. Checks a local file cache (keyed by `file_hash`)
3. On cache miss, downloads the `.py` file from MinIO to the local cache
4. Uses `importlib.util.spec_from_file_location()` to load the module
5. Instantiates the component class and returns it to the pipeline executor

### 6. SSE Step Progress

During composite component execution, each step transition publishes an event to Redis channel `rrag:run:{run_id}:steps`. The pipeline service exposes `GET /api/v1/pipelines/{id}/runs/{run_id}/stream` as an SSE endpoint that subscribes to this channel and forwards events to the frontend.

### 7. Frontend Integration

- **CompositeNode**: An expandable React Flow node that shows internal steps with status indicators (idle/running/completed/failed/retrying)
- **ComponentManager**: A page for uploading `.py` files, viewing custom components, and deleting them
- **useStepProgress hook**: Subscribes to the SSE endpoint and provides real-time step state to `CompositeNode`

### 8. Database Changes

Six new columns added to the `components` table:

| Column | Type | Description |
|--------|------|-------------|
| `source` | `varchar` | `"built_in"` or `"custom"` |
| `is_composite` | `boolean` | Whether the component has multiple steps |
| `steps` | `json` | Ordered array of step metadata |
| `workspace_id` | `varchar` | Workspace scope (null for built-in) |
| `file_path` | `varchar` | MinIO object path |
| `file_hash` | `varchar` | SHA-256 of the uploaded file |

### 9. Concrete Components Shipped

Three composite components are included as built-in examples:

- **LightRAG Ingestion** (5 steps): chunk, extract entities, merge graph, store graph (Neo4j), store vectors (Qdrant)
- **LightRAG Retrieval** (5 steps, 1 back-edge): extract keywords, graph search, vector search, assemble context, generate — with routing from assemble back to keywords on low confidence
- **Agentic RAG Retrieval** (6 steps, 1 back-edge): analyze query, plan retrieval, execute tools, assemble evidence, evaluate & decide, generate — with routing from evaluate back to plan (agent loop, max 3 iterations)

### 10. Storage Operations

Composite component steps interact with workspace-scoped storage backends:

- **Neo4j**: Entity and relation storage with workspace-scoped labels
- **Qdrant**: Vector embedding storage in workspace-scoped collections
- **Redis**: Intermediate step state and SSE pub/sub channels

## Consequences

### Positive

- **Code-first authoring** — Components are plain Python classes with decorators; no YAML, no config files, no framework boilerplate
- **Safe registration** — AST scanning means user-uploaded code is never executed during the upload/registration phase
- **Visual clarity** — Composite nodes collapse complex multi-step patterns into a single expandable node, reducing canvas clutter
- **Reusability** — A composite component encapsulates a complete RAG pattern (e.g., LightRAG ingestion) that can be dropped into any pipeline
- **Real-time observability** — Step-level SSE progress gives users visibility into which step is running, how long each takes, and where failures occur
- **Extensibility** — Users can upload custom composite components without modifying the service codebase or redeploying
- **Back-edge routing** — Supports iterative patterns (agent loops, confidence-gated retry) that cannot be expressed as a linear DAG

### Negative

- **AST scanning limitations** — The scanner can only extract literal values from decorator arguments. Components that compute metadata dynamically (e.g., `config_schema=build_schema()`) will have incomplete metadata at registration time. This is mitigated by documenting the limitation and requiring literal decorator arguments.
- **User code execution risk** — At pipeline execution time, user-uploaded `.py` files are imported and executed. While registration is safe (AST-only), execution is not sandboxed. Malicious code could access the service's environment, file system, and network. This is tracked as tech debt (TD-11) with sandboxed execution planned for a future phase.
- **Single-version components** — Uploading a new version of a custom component overwrites the previous one. There is no version history or rollback. This is tracked as tech debt (TD-12).
- **Step ordering is static** — Steps execute in the fixed order defined by `@step(order=N)`. Dynamic step selection based on runtime conditions (beyond back-edge routing) requires a different mechanism.

### Neutral

- Built-in components remain registered via the existing `component_registry.py` mechanism. The composite framework is additive — it does not replace the existing atomic component system.
- The `rrag-components` MinIO bucket is created automatically on service startup if it does not exist, following the same pattern as `rrag-documents`.

## Alternatives Considered

### Alternative 1: Metaclass Registry

- Description: Use Python metaclasses to auto-register component classes when they are defined (imported). The metaclass `__init_subclass__` hook would populate a global registry.
- Rejected because: Requires importing user code to trigger registration, which defeats the goal of safe scanning without code execution. Also makes the registration mechanism implicit and harder to debug.

### Alternative 2: Config + Code Split

- Description: Define component metadata in a separate YAML or JSON config file, and the component logic in a `.py` file. The config file is parsed for registration; the code file is loaded at execution time.
- Rejected because: Adds a second file that must be kept in sync with the code. Developers would need to duplicate step names, order, and config in two places. The decorator approach keeps metadata co-located with the code it describes, following the principle of locality.

### Alternative 3: Sub-pipeline Flattening

- Description: Instead of composite components, allow users to define sub-pipelines (a pipeline referenced as a node inside another pipeline). The system would flatten the sub-pipeline's nodes into the parent pipeline at execution time.
- Rejected because: Loses the encapsulation benefit — sub-pipeline nodes would clutter the parent canvas. Also makes back-edge routing more complex (edges would need to cross sub-pipeline boundaries). Composite components provide a cleaner abstraction boundary.

## Implementation Notes

- **Database migration**: Alembic migration adds 6 columns to `components` table with defaults (`source="built_in"`, `is_composite=false`, others nullable)
- **MinIO bucket**: `rrag-components` bucket created on pipeline service startup
- **File size limit**: Uploaded `.py` files are limited to 1 MB
- **Max steps**: A composite component can have at most 20 steps (enforced by the scanner)
- **Max loop iterations**: Back-edge routing is capped at a configurable maximum (default: 5) to prevent infinite loops
- **Cache directory**: `ComponentLoader` caches files in `/tmp/rrag-component-cache/` with `file_hash` as the filename

## References

- [ADR-0004: Visual Pipeline Builder with XYFlow](./0004-visual-pipeline-builder.md)
- [ADR-0016: Component Registry with Factory Pattern](./0016-component-registry-pattern.md)
- [ADR-0017: SSE Streaming Responses](./0017-sse-streaming-responses.md)
- [LightRAG: Simple and Fast Retrieval-Augmented Generation (Guo et al., 2024)](https://arxiv.org/abs/2410.05779)
