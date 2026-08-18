# ADR-0020: Phased Delivery Strategy (5 Phases, 24 Weeks)

## Status

Superseded — actual delivery has not followed the documented 5-phase plan

## Implementation Status

Actual shipped scope (by commit history through 2026-05-12) follows a different ordering than the ADR's 5-phase plan: infrastructure hardening + persistence migration (Mar 2026) → composite component framework + LightRAG port (Mar 2026) → admin/component management (Mar 2026) → local-LLM migration to vLLM/Qwen (Mar–Apr 2026) → knowledge bases + publishing (Apr 2026). This ADR is kept for historical context but no longer reflects current planning.

## Context

The full FusionRAG system encompasses three retrieval engines, a visual pipeline builder, enterprise auth, and production infrastructure. Building everything at once would delay the first usable system by months. Each phase must produce a working, deployable system — not an incrementally broken one.

## Decision

Deliver the system in five phases over 24 weeks, each producing a working system:

### Phase 1: Foundation (Weeks 1–4)
**Goal**: LightRAG + CoRAG working with shared knowledge infrastructure

| Component | Deliverable |
|-----------|-------------|
| Knowledge stores | Neo4j, Milvus, OpenSearch, Redis deployed |
| LightRAG engine | Graph-enhanced dual-level retrieval |
| CoRAG engine | Prompted iterative retrieval (no RL training yet) |
| Ingestion pipeline | Document parsing, chunking, embedding, entity extraction |
| API | FastAPI endpoints for ingestion and query |
| Deployment | Docker Compose |

**Key Decision**: CoRAG uses **prompted iterative retrieval** instead of fine-tuned model. This avoids GPU training infrastructure in Phase 1 while delivering multi-hop capability.

### Phase 2: Production App (Weeks 5–10)
**Goal**: Full-stack application with auth, frontend, and monitoring

| Component | Deliverable |
|-----------|-------------|
| Auth | Keycloak OIDC/OAuth2 with multi-tenant support |
| Frontend | React/Next.js with chat interface, document management |
| API Gateway | Traefik v3 with rate limiting, ForwardAuth |
| Monitoring | Prometheus + Grafana + Langfuse |
| Observability | OpenTelemetry + Jaeger tracing |

### Phase 3: KAG Engine (Weeks 11–14)
**Goal**: Logical reasoning, numerical computation, domain-specific rules

| Component | Deliverable |
|-----------|-------------|
| KAG engine | Logical form decomposition, five operator types |
| Math executor | Sandboxed numerical computation |
| Schema management | LLMFriSPG three-layer representation |
| Knowledge alignment | Disambiguation, concept linking, taxonomy |

### Phase 4: Fusion System (Weeks 15–18)
**Goal**: Unified multi-engine orchestration with quality assurance

| Component | Deliverable |
|-----------|-------------|
| Agent orchestration | Four-agent state machine (Router, Analyzer, Selector, Escalation) |
| Context aggregation | Cross-engine deduplication and confidence ranking |
| Hallucination guard | Claim verification and iterative revision |
| Citation linker | Provenance chain from claims to source documents |
| Semantic cache | L3 caching with similarity matching |

### Phase 5: RAG IDE (Weeks 19–24)
**Goal**: Visual pipeline builder with drag-and-drop editor

| Component | Deliverable |
|-----------|-------------|
| Visual editor | XYFlow/React Flow canvas with typed connectors |
| YAML sync | Bidirectional YAML ↔ canvas synchronization |
| Component palette | All component categories with property inspectors |
| Template gallery | Pre-built pipeline templates |
| Debug tooling | Step-by-step execution, trace visualization |

### Infrastructure Growth

| Phase | Deployment | New Infrastructure |
|-------|-----------|-------------------|
| 1 | Docker Compose | Neo4j, Milvus, OpenSearch, Redis |
| 2 | Docker Compose + Helm charts | Keycloak, Traefik, Prometheus, Grafana, Jaeger |
| 3 | K8s optional | Schema management tools |
| 4 | K8s optional | Multi-engine orchestration |
| 5 | Kubernetes | RAG IDE frontend + pipeline engine |

## Consequences

**Positive:**
- Each phase delivers a usable system (not broken increments)
- Phase 1 alone provides production-ready RAG (LightRAG + CoRAG)
- Phases 3–5 add power without breaking earlier functionality
- Infrastructure grows incrementally (Docker Compose → Kubernetes)
- Risk is front-loaded: hardest integration decisions in Phase 1

**Negative:**
- 24 weeks is ambitious for full system
- Phase 1 CoRAG (prompted, not fine-tuned) may underperform vs. trained model
- Phase 3 KAG requires domain expertise for schema design
- Phase 4 orchestration quality depends on all engines being stable
- Phase 5 visual editor is significant UI work

## Alternatives Considered

1. **Big bang release**: Build everything, release once — but months without usable system
2. **Engine-first (all 3 engines before any app)**: Deep before wide — but no user-facing system until very late
3. **App-first (UI before engines)**: User-facing early — but demo without substance
4. **Two phases only (MVP + full)**: Simpler planning — but Phase 2 would be massive

## Branch Mapping (Implementation Scope)

The phased roadmap is delivered through four thematic feature branches, each cut from `main`. This annotation maps the ADRs/phases onto branches so each branch has a self-contained, mergeable scope.

| Branch | ADRs | Scope vs. phases | Priority |
|--------|------|------------------|----------|
| `feat/inference-delivery` | 0018, 0020 | LLM inference backend (vLLM serving, tiered model routing, prefix caching, OpenAI fallback) + this phased plan. Pure infrastructure, no upstream deps. | 1 — start immediately |
| `feat/rag-fusion-architecture` | 0007, 0008, 0009, 0010, 0011 | Phase 1 foundation: three-engine fusion (LightRAG + CoRAG + KAG), adaptive routing, unified knowledge infra, provenance, incremental updates. | 1 — start immediately |
| `feat/generation-quality` | 0014, 0015, 0019, 0021 | Phase 4 quality: multi-level caching, hallucination guard, semantic chunking, generation/synthesis layer. | 2 — after both P1 branches merge (ADR-0019 may start early) |
| `feat/pipeline-orchestration` | 0012, 0013, 0016 | Phase 5 / orchestration: component registry, YAML↔canvas pipeline sync, agentic state machine. | 3 — after P2 merges (ADR-0016 may start early) |

**Dependency order:** `feat/inference-delivery` and `feat/rag-fusion-architecture` run in parallel (no upstream deps). `feat/generation-quality` depends on both. `feat/pipeline-orchestration` depends on `feat/generation-quality`.

vLLM is sequenced first because every generation, extraction, and verification call routes through the inference layer — establishing it (with an OpenAI fallback for non-GPU deployments) unblocks all downstream branches.
