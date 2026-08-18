# ADR-0009: Unified Knowledge Infrastructure

## Status

Accepted — implemented with substitutions

## Implementation Status (as of 2026-05-12)

| Component | Designed | As built | Notes |
|-----------|----------|----------|-------|
| Knowledge Graph | Neo4j Causal Cluster | Neo4j 5 Community single-node | Causal clustering not yet provisioned; ADR-0007's LightRAG framework uses `framework/lightrag/storage/neo4j_ops.py` for workspace-scoped ops. |
| Vector Store | Milvus Distributed | **Qdrant v1.13** (single node) | `milvus_indexer.py` stub exists but is referenced by no pipeline. Qdrant is the live vector store — see ADR-0006 and `qdrant_indexer.py`. All 6 shipped pipelines write to Qdrant. |
| Document Store | OpenSearch | OpenSearch 2.17 (provisioned) | `opensearch_indexer.py` / `opensearch_retriever.py` exist with kNN + BM25 + RRF support but **no shipped pipeline references them**. Mutual index (ADR-0010) is deferred. |
| Cache | Redis Cluster, L2–L4 | Redis 7 single-node, L2 only | Cache-aside L2 implemented per ADR-0024. L1 in-process, L3 semantic similarity, and L4 LLM prompt caches not built. |

The data plane is therefore **active for Qdrant + Neo4j + Redis + Postgres + MinIO**, and **dormant for OpenSearch + Milvus**.

## Context

Three retrieval engines need access to knowledge graphs, vector embeddings, full-text search, and caching. Running separate storage per engine would mean:
- 3x data duplication (graph, embeddings, documents)
- 3x ingestion cost (parse, chunk, embed, extract for each engine)
- Inconsistency between engine views of the same knowledge
- No cross-engine provenance tracking

## Decision

Implement a shared four-component knowledge layer serving all engines:

### 1. Knowledge Graph Store — Neo4j (Causal Cluster)
- Stores entities, relationships, concept hierarchies, semantic types
- Serves both LightRAG (graph traversal, community detection) and KAG (logical form execution)
- Causal clustering for horizontal read scalability
- Sharding by tenant and domain for query locality
- Target: 50,000+ queries/sec

### 2. Vector Store — Milvus (Distributed)
- Chunk embeddings, entity embeddings, relation embeddings
- HNSW indexing for sub-millisecond ANN search
- Namespace isolation per tenant
- GPU-accelerated indexing and search
- Target: 100,000+ queries/sec

### 3. Document Store — OpenSearch
- Original text chunks with full-text search (BM25)
- Mutual index mappings (KG node ↔ source chunk bidirectional links)
- Faceted search (domain, entity type, date range, tenant)
- Hybrid search (BM25 + kNN) for CoRAG's retrieval needs
- Target: 50,000+ queries/sec

### 4. Cache Layer — Redis (Cluster)
- **L2**: Query result cache (exact match, 1-hour TTL)
- **L3**: Semantic cache (cosine similarity > 0.95, 30-min TTL)
- **L4**: LLM prompt cache (system prompts and knowledge contexts)
- Session state for multi-turn conversations
- Target: 500,000+ operations/sec

### Mutual Index (Cross-Store Provenance)
Bidirectional links between KG nodes and source text chunks, stored in OpenSearch:
- KG node → chunk IDs that contributed to its extraction
- Chunk → KG nodes extracted from it
- Enables drill-down from thematic results to specific evidence
- Critical for citation generation and hallucination verification

## Consequences

**Positive:**
- Single ingestion pipeline serves all engines (parse once, store once)
- Consistent view of knowledge across engines
- Mutual index enables cross-engine provenance (e.g., LightRAG entity → source chunk → KAG logical form)
- Incremental updates propagate to all engines atomically
- Operational simplicity: fewer data stores to manage

**Negative:**
- Shared stores are single points of failure (mitigated by clustering)
- Schema must accommodate all three engines' requirements
- Cross-store consistency requires coordination (eventual consistency window: seconds to minutes)
- Neo4j Community Edition has limited clustering (Enterprise needed for causal cluster)

## Alternatives Considered

1. **Per-engine storage**: Simpler per engine — but 3x duplication, no cross-engine provenance
2. **Single unified database (PostgreSQL + pgvector)**: Simpler ops — but inferior graph traversal, vector search, and full-text performance at scale
3. **Managed cloud services (Neptune, Pinecone, etc.)**: Lower ops burden — but vendor lock-in, cost at scale, harder self-hosting
