# ADR-0021: Generation & Synthesis Layer Architecture

## Status

Accepted — Partial implementation

## Implementation Status (as of 2026-05-12)

Generator components built in `rrag-ingestion/src/rrag_ingestion/components/generators/`:

- `llm_generator.py` — generic chat-completion synthesizer
- `corag_chain.py` — chain-of-retrieval synthesis
- `kag_executor.py` — `KAGMathExecutor` (Python sandbox) + `KAGDeduceExecutor` (logical deduction)
- `ollama_generator.py`, `vllm_generator.py` — local-model variants

SSE streaming generation is wired end-to-end (ADR-0017): `rrag-pipeline-service/src/pipeline_service/api/pipeline_run_stream.py` and frontend `usePipelineRunStream` hook. Per-step progress events stream over `/api/v1/runs/{id}/stream`.

What's **not** built: explicit "synthesis layer" that fuses multi-engine outputs into a single answer with cross-engine citation. Today's generators consume a single retrieved-context block and emit a single answer.

## Context

After retrieval from one or more engines, the system must aggregate evidence, generate a coherent response, verify its accuracy, and provide citations. This layer sits between retrieval and the user, making it critical for both quality and latency.

Key challenges:
- Multiple engines may return overlapping or contradictory evidence
- Context windows are limited — not all retrieved evidence can be included
- Generated responses must be grounded in evidence (no hallucination)
- Every claim should be traceable to source documents
- Cost must be managed through model routing

## Decision

Implement a four-component synthesis pipeline:

### 1. Context Aggregation Agent
- **Entity-level deduplication**: Merge same entities from different engines using name + embedding similarity
- **Chunk-level deduplication**: Deduplicate by chunk ID from mutual index
- **Confidence-weighted ranking**: Score each evidence piece by:
  - Retrieval confidence (engine's relevance score)
  - Engine reliability (per-engine historical accuracy)
  - Freshness (document timestamp)
  - Cross-engine corroboration (evidence supported by multiple engines scores higher)
- **Context window optimization**: Greedy selection of top-ranked evidence with diversity preservation (avoid over-representing one source)

### 2. Response Synthesizer
- **LLM routing by complexity**:
  - Simple queries → fast/cheap model (Haiku-class): ~60% of queries
  - Complex queries → capable model (Opus-class): ~40% of queries
- **Adaptive synthesis**: Prompt structure varies by evidence type:
  - Entity context → structured fact presentation
  - Reasoning chains (CoRAG) → step-by-step explanation
  - Proof chains (KAG) → logical argument with computation results
- **Cost target**: 60–70% reduction via tiered model routing

### 3. Hallucination Guard (see ADR-0015)
- Claim extraction → evidence matching → classification → iterative revision
- Max 2 iterations to prevent loops
- Quality score drives escalation decisions

### 4. Citation Linker
- Traces claims through evidence → KG nodes/chunks → source documents via mutual index (ADR-0010)
- **Multi-level provenance**: Claim → Evidence → KG Node/Chunk → Source Doc → Section/Page
- **Inline citations**: Expandable references in generated text
- **Citation format**: `[1]`, `[2]` with footnote-style source list

### Quality Score Computation

| Dimension | Weight | Description |
|-----------|--------|-------------|
| Evidence coverage | 30% | % of response claims supported by evidence |
| Citation completeness | 20% | % of claims with source citations |
| Source diversity | 15% | Number of distinct source documents |
| Reasoning coherence | 20% | Logical flow for multi-hop queries |
| Confidence score | 15% | Average confidence of supporting evidence |

Score < threshold triggers retry/escalation (ADR-0013).

## Consequences

**Positive:**
- Evidence from multiple engines is deduplicated and ranked, preventing redundancy
- Model routing reduces cost by 60–70% without quality loss on simple queries
- Every claim is verified and cited before delivery
- Quality score provides objective measure for monitoring and improvement
- Cross-engine corroboration increases confidence in well-supported answers

**Negative:**
- Four-component pipeline adds 200–800ms to response time
- LLM routing decisions may occasionally assign complex queries to cheap models
- Deduplication by embedding similarity may incorrectly merge distinct entities
- Quality score weights need empirical tuning per deployment
- Citation linking adds ~5–20ms per claim for provenance lookup

## Alternatives Considered

1. **Pass-through (raw retrieval → LLM)**: Fastest — but no dedup, no verification, no citations
2. **Single LLM call for everything**: Simpler — but no quality control, no cost optimization
3. **Human review pipeline**: Most accurate — but doesn't scale
4. **Separate synthesis per engine, then merge**: Cleaner isolation — but 3x generation cost
