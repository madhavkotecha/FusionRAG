# Architecture Decision Records (ADRs)

This directory contains Architecture Decision Records for the Agentic RAG System.

Status legend: **Accepted** = decision applied in code. **Partial** = some sub-decisions shipped, others pending. **Deferred** = ADR's design not yet implemented; entry kept for future reference. **Superseded** = replaced by a later ADR.

## Index

### Foundation

| ADR | Title | Status |
|-----|-------|--------|
| [ADR-0001](./0001-microservices-architecture.md) | Microservices Architecture with API Gateway | Accepted |
| [ADR-0002](./0002-forwardauth-pattern.md) | Traefik ForwardAuth for Service Authentication | Accepted |
| [ADR-0003](./0003-multi-tenant-workspace-model.md) | Multi-Tenant Workspace Data Model | Accepted |
| [ADR-0004](./0004-visual-pipeline-builder.md) | Visual Pipeline Builder with XYFlow | Accepted |
| [ADR-0005](./0005-async-ingestion-with-rq.md) | Async Document Ingestion with RQ | Accepted |
| [ADR-0006](./0006-technology-choices.md) | Technology Stack Selection | Accepted |

### FusionRAG Research Decisions

Based on the [Agentic RAG Research Survey](../../AGENTIC_RAG_RESEARCH.md). Implementation Status sections in each ADR describe what's actually wired up as of 2026-05-12.

| ADR | Title | Status |
|-----|-------|--------|
| [ADR-0007](./0007-three-engine-fusion-architecture.md) | Three-Engine Fusion RAG (LightRAG + CoRAG + KAG) | Accepted — Partial |
| [ADR-0008](./0008-adaptive-complexity-routing.md) | Adaptive Complexity-Based Query Routing | Deferred |
| [ADR-0009](./0009-unified-knowledge-infrastructure.md) | Unified Knowledge Infrastructure | Accepted (with substitutions) |
| [ADR-0010](./0010-mutual-index-provenance.md) | Mutual Index for Provenance and Citation Tracking | Deferred |
| [ADR-0011](./0011-incremental-update-protocol.md) | Incremental Update Protocol (7-Step) | Deferred |
| [ADR-0012](./0012-yaml-first-pipeline-definition.md) | YAML-First Pipeline Definition with Visual Sync | Accepted |
| [ADR-0013](./0013-agentic-state-machine-orchestration.md) | Agentic State Machine Orchestration | Accepted — Partial |
| [ADR-0014](./0014-multi-level-caching-strategy.md) | Multi-Level Caching Strategy (L1–L4) | Partial — L2 via ADR-0024 |
| [ADR-0015](./0015-hallucination-guard.md) | Hallucination Guard with Claim Verification | Deferred |
| [ADR-0016](./0016-component-registry-pattern.md) | Component Registry with Factory Pattern and Lazy Loading | Accepted |
| [ADR-0017](./0017-sse-streaming-responses.md) | Server-Sent Events for Streaming Responses | Accepted |
| [ADR-0018](./0018-vllm-inference-server.md) | vLLM for LLM Inference | Accepted |
| [ADR-0019](./0019-semantic-chunking-strategy.md) | Semantic Chunking Strategy (1200 Tokens, 100-Token Overlap) | Accepted |
| [ADR-0020](./0020-phased-delivery-strategy.md) | Phased Delivery Strategy (5 Phases, 24 Weeks) | Superseded |
| [ADR-0021](./0021-generation-synthesis-architecture.md) | Generation & Synthesis Layer Architecture | Accepted — Partial |

### Infrastructure & Data

| ADR | Title | Status |
|-----|-------|--------|
| [ADR-0023](./0023-ingestion-persistence-migration.md) | Ingestion Service Persistence Migration to PostgreSQL | Accepted |
| [ADR-0024](./0024-redis-cache-aside-pattern.md) | Redis Cache-Aside Pattern Across All Services | Accepted |
| [ADR-0025](./0025-production-security-hardening.md) | Production Security Hardening | Accepted |

### Platform & Component Architecture

| ADR | Title | Status |
|-----|-------|--------|
| [ADR-0026](./0026-hierarchical-composite-components.md) | Hierarchical Composite Components | Accepted |
| [ADR-0027](./0027-llm-provider-abstraction.md) | LLM Provider Abstraction via LiteLLM | Accepted |
| [ADR-0028](./0028-knowledge-base-domain-model.md) | Knowledge Base as First-Class Domain Object | Accepted |
| [ADR-0029](./0029-published-query-endpoints.md) | Published Query Endpoints with API-Key Authentication | Accepted |
| [ADR-0030](./0030-admin-component-management.md) | Admin Component Management with Append-Only Versioning | Accepted |

### Process & Governance

| ADR | Title | Status |
|-----|-------|--------|
| [ADR-0022](./0022-adr-template-and-process.md) | ADR Template and Process | Accepted |

## ADR Template

See [ADR-0022](./0022-adr-template-and-process.md) for the full template, review process, and maintenance procedures.

Quick template:

```markdown
# ADR-NNNN: Title

- **Status:** Proposed | Accepted | Rejected | Deprecated | Superseded by [ADR-NNNN]
- **Date:** YYYY-MM-DD
- **Deciders:** [names or roles]

## Context
What is the issue that motivates this decision?

## Decision
What is the change that we are proposing or have agreed to implement?

## Consequences
### Positive
### Negative

## Alternatives Considered

## References
```
