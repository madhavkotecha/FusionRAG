# ADR-0019: Semantic Chunking Strategy (1200 Tokens, 100-Token Overlap)

## Status

Accepted

## Implementation Status (as of 2026-05-12)

Four chunker components ship today in `rrag-ingestion/src/rrag_ingestion/components/chunkers/`:

- `semantic_chunker.py` — implements the strategy described in this ADR
- `recursive_chunker.py` — LangChain-style recursive split
- `sentence_chunker.py` — UltraRAG sentence-level
- `token_chunker.py` — LightRAG token-window with overlap

Pipelines select a chunker via the `chunker` component name in YAML. Default chunk size and overlap are pipeline-configurable; the LightRAG path uses `token_chunker` with the ADR-specified 1200/100 defaults.

## Context

Chunking — splitting documents into retrievable segments — is foundational to RAG quality. Chunks too small lose context; chunks too large dilute relevance and waste LLM context window. The chunking strategy must balance:
- **Retrieval precision**: Smaller chunks match specific queries better
- **Context completeness**: Larger chunks preserve surrounding context
- **LLM context window**: Chunks must fit within generation prompt alongside system instructions

## Decision

Use **semantic chunking** with the following parameters:

### Primary Strategy: Embedding-Based Boundary Detection
1. Split document into sentences
2. Compute embeddings for sliding windows of sentences
3. Detect topic boundaries where embedding similarity drops below threshold
4. Group consecutive sentences between boundaries into chunks
5. Enforce hard limits: target 1200 tokens, max 1500 tokens

### Parameters

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Target chunk size | 1200 tokens | Fits ~8 chunks in typical 8K context window with room for instructions |
| Max chunk size | 1500 tokens | Hard cap prevents runaway chunks on uniform content |
| Overlap | 100 tokens | Preserves context at boundaries without excessive duplication |
| Boundary threshold | Configurable | Embedding similarity drop that triggers a split |

### Specialized Chunkers (Pipeline Components)
The default semantic chunker is supplemented by specialized alternatives:

| Chunker | Use Case |
|---------|----------|
| **TokenChunker** | Fixed-size fallback for uniform content |
| **SentenceChunker** | Sentence-boundary-aware splitting |
| **RecursiveChunker** | Hierarchical splitting (heading → paragraph → sentence) |
| **SemanticChunker** | Embedding-based boundary detection (default) |
| **TableChunker** | Preserves table structure as atomic chunks |
| **ParentChildChunker** | Hierarchical: small chunks for retrieval, parent chunks for context |

### Single Pipeline, Multiple Engines
Chunking is performed once during ingestion. The resulting chunks are shared across all three retrieval engines (LightRAG, CoRAG, KAG) via the unified knowledge layer.

## Consequences

**Positive:**
- Semantic boundaries produce more coherent chunks than fixed-size splitting
- 1200-token size balances precision and context for most use cases
- 100-token overlap prevents information loss at boundaries
- Single chunking pipeline eliminates duplicate processing
- Specialized chunkers available for edge cases (tables, hierarchical documents)

**Negative:**
- Semantic chunking requires embedding computation during ingestion (added cost)
- Fixed parameters (1200/100) may not be optimal for all document types
- Very short documents may produce a single chunk with low retrieval precision
- Table and code blocks may be split incorrectly by embedding-based boundaries
- Overlap tokens are stored/embedded twice (2x storage for 8% of content)

## Alternatives Considered

1. **Fixed-size (512 tokens)**: Simple — but splits mid-sentence, poor context
2. **Fixed-size (2000+ tokens)**: More context — but lower retrieval precision, fewer chunks per context window
3. **Paragraph-based**: Natural boundaries — but paragraph sizes vary wildly
4. **No overlap**: Less storage — but boundary context loss degrades retrieval
5. **Document-level (no chunking)**: Simplest — but exceeds LLM context windows, poor retrieval
