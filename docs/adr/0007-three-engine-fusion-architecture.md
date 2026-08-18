# ADR-0007: Three-Engine Fusion RAG Architecture (LightRAG + CoRAG + KAG)

## Status

Accepted — Partial implementation (engine components built, unified orchestration pending)

## Implementation Status (as of 2026-05-12)

| Engine | What's built | What's pending |
|--------|--------------|----------------|
| **LightRAG** | Fully ported into `rrag-pipeline-service/src/pipeline_service/framework/lightrag/` — chunking, extraction, merging, context builder, prompts, workspace-scoped Neo4j/Qdrant/Redis storage ops. Three composite components: `lightrag_ingestion`, `lightrag_retrieval`, `agentic_rag_retrieval` (with planner/evaluator/tool-executor agent loop). | — |
| **CoRAG** | `corag_subquery` extractor, `corag_strategy` planner, `corag_chain` generator (chain-of-retrieval synthesizer). | Iterative sub-query decoding (greedy/best-of-N/tree search) coordination layer not wired. |
| **KAG** | `kag_schema_free` / `kag_schema_constrained` extractors, `kag_subgraph` graph builder, `kag_executor` with `KAGMathExecutor` + `KAGDeduceExecutor` generators, `kag_reader` parser. | No KGDSL logical-form parser; no end-to-end KAG retrieval composite. |
| **Adaptive routing** | `agents/router.py` generic router exists. | Complexity classifier from ADR-0008 not implemented. |

Pipeline templates that ship today (`rrag-ingestion/configs/pipelines/`): `lightrag_default`, `corag_default`, `kag_default`, `quick_ingest`, `ultrarag_default`, `agentic_rag`. Each invokes a single engine — no fusion/parallel-dispatch path yet.

## Context

No single RAG paradigm excels across all query types. Research evaluation across four major frameworks (LightRAG, CoRAG, KAG, UltraRAG) revealed complementary strengths:

| Query Type | Best Engine | Why |
|-----------|-------------|-----|
| Entity lookup | LightRAG | Graph traversal finds entities in O(1) hops |
| Thematic exploration | LightRAG | Community detection captures conceptual clusters |
| Multi-hop reasoning | CoRAG | Iterative sub-query chains accumulate evidence |
| Numerical computation | KAG | Only engine with Math operators and sandboxed execution |
| Domain-specific logic | KAG | KGDSL rules and schema-constrained ontology |
| Comparative analysis | CoRAG + KAG | Chain reasoning + logical form decomposition |

A monolithic approach would sacrifice performance on query types outside its core strength.

## Decision

Unify LightRAG, CoRAG, and KAG into a single adaptive system called **FusionRAG** with:

1. **LightRAG Engine** — Graph-enhanced dual-level retrieval (low-level entity search + high-level community/thematic retrieval)
2. **CoRAG Engine** — Chain-of-retrieval with iterative sub-query generation and three decoding strategies (greedy, best-of-N, tree search)
3. **KAG Engine** — Logical-form-guided hybrid reasoning with five operator types (Retrieval, Sort, Math, Deduce, Output)

All three engines share a unified knowledge layer (see ADR-0009) and are orchestrated by an agentic routing system (see ADR-0008).

UltraRAG was evaluated but excluded as a direct engine — its value is as a modular framework whose paradigms (IRCoT, IterRetGen, etc.) inform the pipeline builder design (see ADR-0012).

## Consequences

**Positive:**
- Covers the full spectrum of query complexity (simple entity → multi-hop + numerical)
- Each engine operates in its area of peak performance
- Engines can run in parallel for high-complexity queries, reducing latency vs. sequential fallback
- Shared knowledge infrastructure eliminates data duplication

**Negative:**
- Significant implementation and operational complexity (three distinct retrieval codebases)
- CoRAG requires fine-tuned model (Llama-3.1-8B with rejection sampling SFT) or prompted iterative retrieval as fallback
- KAG depends on OpenSPG schema and domain-specific ontology maintenance
- Orchestration layer must correctly route queries — misrouting wastes compute or degrades quality

## Alternatives Considered

1. **LightRAG only**: Fast, simple, supports incremental updates — but no multi-hop reasoning or numerical computation
2. **CoRAG only**: Excellent multi-hop — but no knowledge graph, no incremental updates, coupled to E5 retriever
3. **KAG only**: Powerful reasoning — but high latency, complex setup, schema maintenance overhead
4. **UltraRAG as framework**: Modular and extensible — but no native knowledge graph, no graph-based retrieval
5. **Sequential fallback (single engine → escalate)**: Simpler — but slower for complex queries that benefit from parallel dispatch
