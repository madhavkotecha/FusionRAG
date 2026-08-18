# ADR-0011: Incremental Update Protocol (7-Step)

## Status

Deferred — not implemented as of 2026-05-12

## Implementation Status

The ingestion pipeline is **full-rebuild** today. Documents are processed via async RQ jobs (ADR-0005), and a re-upload creates new chunks/vectors/graph entries — no diff/delta detection, no incremental graph patching, no chunk versioning. Re-ingestion is idempotent only insofar as document IDs are reused. Job-level resume/retry was added (commit `d5012ad` "Add publish API, resume retry & checkpoints"), but this is execution-level resume, not document-content incrementality.

## Context

Full knowledge base rebuilds (re-parse, re-chunk, re-embed, re-extract, re-index) take hours for large corpora. In production, documents are added and updated frequently. Users expect new documents to be queryable within minutes, not hours.

## Decision

Implement a 7-step incremental update protocol that adds or modifies documents without full rebuild:

### Step 1: Change Detection & Intake
- CDC (Change Data Capture) or API upload detects new/modified documents
- Content-hash deduplication prevents reprocessing unchanged documents
- Idempotent: re-uploading the same document is a no-op

### Step 2: Selective Semantic Chunking
- Only new or modified content is chunked
- Unchanged chunks from prior versions are preserved
- Significant compute reduction for partial updates

### Step 3: LightRAG Incremental Graph Update
- New entities merged into existing graph by name + embedding similarity
- New relationships linked to existing or new entity nodes
- Map-reduce description summarization for merged entities
- Per-entity keyed locks prevent concurrent merge conflicts

### Step 4: KAG Knowledge Alignment
- Synonym fusion: merge equivalent entities across new and existing knowledge
- Hierarchical placement: position new concepts in existing taxonomy
- Cross-reference establishment: link new entities to related existing entities

### Step 5: Vector Embedding Upsert
- New embeddings inserted into Milvus without index downtime
- Leverages Milvus's native upsert capability
- No rebuild of existing HNSW index

### Step 6: Mutual Index Update
- New KG-to-chunk links created for provenance accuracy
- Existing links preserved for unchanged entities/chunks

### Step 7: Cache Invalidation
- Selective invalidation for query patterns affected by changed knowledge
- Preserve cache hits for unrelated queries
- Based on entity overlap between cached queries and updated entities

### Consistency Guarantee
- **Default**: Eventual consistency across indices (seconds to minutes window)
- **Transaction mode**: Available for stronger consistency at cost of higher latency
- Every step is idempotent and resumable after failure — no full rebuild on error

## Consequences

**Positive:**
- New documents queryable in minutes instead of hours
- No downtime during updates (all upsert operations)
- Failed updates are recoverable without full rebuild
- Cache invalidation is surgical, preserving unaffected cache hits
- Compute cost proportional to change size, not corpus size

**Negative:**
- Eventual consistency window means queries during update may return stale results
- Graph merge logic (Step 3) is complex — entity disambiguation can produce errors
- KAG alignment (Step 4) requires domain-specific tuning
- Seven coordinated steps across four data stores increase operational complexity
- Edge case: large batch updates may approach full-rebuild cost

## Alternatives Considered

1. **Full rebuild on every update**: Simple — but hours of downtime, unacceptable for production
2. **Append-only (no merge)**: Fast — but creates duplicate entities, degrades graph quality
3. **Scheduled batch rebuild (nightly)**: Predictable — but 24-hour staleness unacceptable for many use cases
4. **Event-sourced with materialized views**: Elegant — but significant infrastructure overhead
