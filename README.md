# Agentic RAG System

Multi-tenant RAG platform with a visual pipeline builder, plus a research testbed comparing four upstream RAG frameworks. Supports OpenAI, self-hosted vLLM (Qwen3.5-9B), and Ollama — switchable at runtime via the admin UI (ADR-0027).

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- One of: OpenAI API key, a vLLM-served model on a GPU host, or Ollama on localhost

**Development** — copy the dev template:

```bash
cp .env.dev.example .env
```

**Production** — copy the prod template and fill in all values:

```bash
cp .env.prod.example .env.prod
# Edit .env.prod — set all REQUIRED values (passwords, domain, ACME email, API keys)
```

## Platform features

The `rrag-*` services together provide:

- **Visual pipeline builder** (XYFlow, ADR-0004) with typed nodes, group nodes, loop edges, and live SSE per-step progress
- **Composite component framework** (ADR-0026) — `@component`/`@step` decorators, AST-based discovery, MinIO-backed user-uploaded components
- **Admin component management** with append-only versioning (ADR-0030)
- **Knowledge Bases** as first-class entities (ADR-0028) — workspace-scoped document collections with their own ingestion config
- **Published query endpoints** with API-key auth (ADR-0029) — turn a (KB × query pipeline) into a stable URL that external systems can call
- **LightRAG / CoRAG / KAG components** ported and registered (ADR-0007 — components present, fusion orchestration partial)
- **Multi-provider LLM** via LiteLLM (ADR-0027) — OpenAI, vLLM, Ollama

See `docs/adr/README.md` for the full ADR index with implementation status, and `docs/architecture/` for the C4 documents.

## Research frameworks

All upstream RAG frameworks live under `existing_frameworks/`.

### LightRAG

Graph-based RAG with a web UI. Uses OpenAI for both LLM and embeddings.

```bash
cd existing_frameworks/LightRAG
cp env.example .env
# edit .env — set LLM_BINDING=openai, add your API keys
uv pip install -e .
lightrag-server
```

Server runs at http://localhost:9621 with a built-in web UI.

### KAG

Knowledge graph construction + QA from OpenSPG. Runs in memory mode (no Docker needed).

```bash
cd existing_frameworks/KAG
uv pip install -e .
uv pip install torch --index-url https://download.pytorch.org/whl/cpu
uv pip install igraph
python test_quick.py
```

The test script monkey-patches OpenSPG client classes so KAG works without the server. It builds a knowledge graph from sample text and answers questions against it.

Config: `kag_config.yaml` — uses `gpt-4o-mini`, `text-embedding-3-small`, memory-based graph storage.

### CoRAG

Microsoft's multi-hop retrieval agent from LMOps. Adapted to run with OpenAI directly (originally needs vLLM + GPU).

```bash
cd existing_frameworks/corag_repo
uv pip install -e .
python corag/test_openai.py
```

Runs a multi-hop QA demo with an in-memory corpus. No external search server needed.

### UltraRAG

Modular RAG toolkit from OpenBMB. Supports multiple retrieval strategies.

```bash
cd existing_frameworks/UltraRAG
cp .env.example .env   # or create .env with your OPENAI_API_KEY
uv pip install -e .
```

See `examples/` for YAML configs covering different RAG pipelines (BM25, vector search, reranking, etc).

## Running the Stack

### Development

```bash
cp .env.dev.example .env
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

Services available at **`https://localhost:8000`** (Traefik with self-signed TLS — click through the browser warning). Traefik dashboard at `http://localhost:8888`. Infrastructure ports are exposed for local debugging:
- Postgres `5433` · Redis `6381` · Neo4j `7474` (browser) / `7687` (Bolt) · MinIO `9000` (S3) / `9001` (console) · OpenSearch `9200` · Qdrant `6333` · Keycloak `8180`

Default dev users (seeded in `keycloak/rrag-realm.json`):
- `admin@rrag.io` / `AdminPassword@1234` (platform admin)
- `testuser@rrag.io` / `TestPassword@1234` (regular user)

### Production

```bash
cp .env.prod.example .env.prod
# Edit .env.prod — fill in all REQUIRED values (passwords, domain, ACME email)
docker compose --env-file .env.prod up -d --build
```

Only ports 80 and 443 are exposed. TLS is provisioned automatically via Let's Encrypt. All containers run with a read-only filesystem, `no-new-privileges`, and dropped capabilities.

## Project Structure

```
.
├── .env.prod.example             # Production environment template
├── .env.dev.example              # Development environment template
├── docker-compose.yml            # 15-container production stack
├── docker-compose.dev.yml        # Development overlay (ports, relaxed security)
├── keycloak/                     # Keycloak realm config (rrag-realm.json)
├── rrag-auth-server/             # Auth + RBAC (Node.js/Hono)
├── rrag-pipeline-service/        # Pipeline CRUD + visual builder (Python/FastAPI)
├── rrag-ingestion/               # Document ingestion + RAG query (Python/FastAPI)
├── rrag-frontend/                # React SPA (Vite + Tailwind + XYFlow)
├── docs/                         # Architecture docs + ADRs
│   ├── architecture/             # 10 C4 architecture documents
│   ├── adr/                      # 30 Architecture Decision Records (see adr/README.md)
│   └── diagrams/                 # Rendered architecture diagrams (PNG/PDF) + Mermaid sources
├── existing_frameworks/          # Research frameworks
│   ├── LightRAG/                 # graph RAG + web UI
│   ├── KAG/                      # knowledge graph QA (memory mode)
│   ├── corag_repo/               # multi-hop retrieval agent
│   └── UltraRAG/                 # modular RAG toolkit
└── AGENTIC_RAG_RESEARCH.md       # 40+ paper survey
```
