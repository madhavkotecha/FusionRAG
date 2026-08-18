# ADR-0010: Mutual Index for Provenance and Citation Tracking

## Status

Deferred — not implemented as of 2026-05-12

## Implementation Status

Codebase grep for `mutual_index`, `MutualIndex`, `provenance`, `reverse_link` returns zero hits. Chunks carry `document_id` / `workspace_id` metadata in Qdrant payloads and in the (unused) OpenSearch schema, but there is no bidirectional KG↔chunk mapping, no citation graph, and no hallucination-guard wiring (see ADR-0015, also deferred). Implementing this is blocked on (a) actually wiring OpenSearch into the ingestion path and (b) the hallucination guard pipeline.

## Context

Users of RAG systems need to trust generated answers. Trust requires:
1. Every claim traceable to source evidence
2. Ability to "drill down" from a high-level answer to the specific document section
3. Cross-engine provenance (e.g., a LightRAG community summary should link back to original chunks)

Without a bidirectional mapping between knowledge graph nodes and source text, citation becomes guesswork.

## Decision

Implement a **mutual index** — bidirectional links between KG nodes and source text chunks — stored in OpenSearch alongside the document store.

### Forward Links (KG → Chunks)
For every entity and relationship in the knowledge graph, store the IDs of source chunks that contributed to its extraction:
```
Entity "OpenAI" → [chunk_42, chunk_187, chunk_203]
Relation "OpenAI -[CEO]-> Sam Altman" → [chunk_42]
```

### Reverse Links (Chunks → KG)
For every chunk, store the IDs of KG nodes extracted from it:
```
chunk_42 → [entity:OpenAI, entity:SamAltman, relation:CEO]
```

### Provenance Chain
Full traceability from generated text to source:
```
Generated claim → Supporting evidence → KG node/chunk → Source document → Section/page
```

### Usage in Citation Linking
1. Hallucination guard extracts claims from generated response
2. Each claim is matched to supporting evidence (chunks or KG nodes)
3. Mutual index traces evidence to source documents
4. Citations are attached inline with expandable references

## Consequences

**Positive:**
- Every generated claim is citable with source evidence
- Users can verify answers by following provenance chain
- Hallucination guard uses mutual index to check if claims have evidence support
- Enables "drill down" from thematic/community results to specific document sections
- Supports compliance requirements in regulated domains (healthcare, legal, finance)

**Negative:**
- Storage overhead: ~2x metadata per chunk and entity
- Must be kept in sync during incremental updates (new chunks → new links)
- Adds complexity to the ingestion pipeline (link creation step)
- Query-time join between KG results and chunk provenance adds ~5–20ms latency

## Alternatives Considered

1. **Chunk IDs in KG node properties**: Simpler — but no reverse lookup, hard to maintain
2. **Separate provenance database**: Clean — but another service to manage
3. **LLM-based citation (post-hoc)**: No infrastructure — but unreliable, hallucinates citations
4. **No provenance**: Simplest — but unacceptable for enterprise/regulated use cases
