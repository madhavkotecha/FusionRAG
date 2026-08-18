# ADR-0014: Multi-Level Caching Strategy (L1–L4)

## Status

Partial — superseded for L2 by ADR-0024; L1/L3/L4 deferred

## Implementation Status (as of 2026-05-12)

| Level | Designed | Status |
|-------|----------|--------|
| **L1** in-process | Per-request memoization | Not built — no `functools.lru_cache` or per-request scoping |
| **L2** Redis exact-match | Query/result cache, 1h TTL | **Built** per ADR-0024 — `rrag-ingestion/src/rrag_ingestion/cache.py`, `rrag-pipeline-service/src/pipeline_service/cache.py`, `rrag-auth-server/src/cache/cache.ts`. Cache-aside pattern across all 3 backend services. |
| **L3** semantic similarity | Cosine > 0.95 hit, 30min TTL | Not built — no embedding-based cache lookup |
| **L4** LLM prompt cache | System prompts and contexts | Not built — relies on provider-side caching (OpenAI) where available |

## Context

RAG queries involve expensive operations: embedding generation, vector search, graph traversal, and LLM inference. Many queries are repeated or near-duplicates. Without caching:
- Identical queries hit the full pipeline every time
- Paraphrased questions ("What is X?" vs. "Explain X") bypass exact-match caches
- LLM prompt prefixes (system prompts, knowledge contexts) are re-tokenized on every call
- FAQ-type queries from multiple users all trigger full retrieval

## Decision

Implement a four-level caching hierarchy:

### L1: Edge Cache (Traefik/Nginx)
- **Scope**: Static and semi-static responses
- **TTL**: 5 minutes
- **Use case**: FAQ-type queries, health checks, component metadata
- **Key**: URL + query hash
- **Technology**: Traefik response cache or Nginx proxy_cache

### L2: Query Result Cache (Redis)
- **Scope**: Exact query match
- **TTL**: 1 hour
- **Use case**: Repeated identical queries across users
- **Key**: SHA256(normalized_query + tenant_id)
- **Technology**: Redis with JSON value storage

### L3: Semantic Cache (Redis + Embedding)
- **Scope**: Semantically similar queries (cosine similarity > 0.95)
- **TTL**: 30 minutes
- **Use case**: Paraphrased questions returning equivalent answers
- **Key**: Query embedding → nearest neighbor in cache index
- **Threshold**: 0.95 (intentionally high to minimize false positives)
- **Technology**: Redis + small in-memory FAISS index of cached query embeddings

### L4: LLM Prompt Cache (vLLM Prefix Cache)
- **Scope**: System prompts and knowledge context prefixes
- **TTL**: Provider-managed
- **Use case**: Token cost reduction for shared prompt prefixes
- **Savings**: Up to 90% token reduction for cached portions
- **Technology**: vLLM's built-in prefix caching (PagedAttention)

### Cache Invalidation
- Triggered by incremental update protocol (ADR-0011, Step 7)
- **Selective**: Only invalidate entries whose entities overlap with updated knowledge
- **Preserve**: Cache hits for unrelated queries remain valid
- **Mechanism**: Entity overlap check between cached query metadata and updated entity set

### Lookup Order
```
Query → L1 (edge) → L2 (exact) → L3 (semantic) → Full Pipeline → L4 (prompt prefix)
```

## Consequences

**Positive:**
- 60–70% of production queries expected to hit L2 or L3 cache
- L4 reduces LLM token cost by up to 90% for common prompt prefixes
- Selective invalidation preserves cache value during updates
- Each level is independent — can be enabled/disabled per deployment

**Negative:**
- L3 semantic cache threshold (0.95) may miss valid paraphrases (false negatives)
- Lowering threshold risks returning wrong cached answers (false positives)
- Cache invalidation logic adds complexity to update pipeline
- Stale cache entries during eventual consistency window may return outdated answers
- Four cache levels increase debugging complexity

## Alternatives Considered

1. **No caching**: Simplest — but unacceptable latency and cost at scale
2. **L2 only (exact match)**: Simple — but misses paraphrased queries (significant portion)
3. **L3 with lower threshold (0.85)**: More cache hits — but unacceptable false positive rate
4. **Application-level LRU cache**: Simple — but no cross-instance sharing, no semantic matching
