# ADR-0008: Adaptive Complexity-Based Query Routing

## Status

Deferred — not implemented as of 2026-05-12

## Implementation Status

A generic `ToolUseAgent` router exists in `rrag-ingestion/src/rrag_ingestion/components/agents/router.py`, but it routes between tools, not between engines based on query complexity. No complexity classifier, no engine-selection policy, no metric collection for routing accuracy. All shipped pipelines (`*_default.yaml`) invoke a single engine explicitly.

## Context

With three retrieval engines available, every query must be routed to the optimal engine(s). Static routing (e.g., always use all engines) wastes compute on simple queries. Manual routing is impractical at scale. The system needs an automated strategy that balances quality against latency and cost.

## Decision

Implement a four-agent orchestration pipeline that analyzes each query and selects a retrieval strategy:

### Agent 1: Query Router
- **Intent classification**: Factual, Analytical, Comparative, Exploratory
- **Entity extraction**: NER for people, organizations, locations, dates, domain-specific terms
- **Domain detection**: Healthcare, Legal, Finance, General

### Agent 2: Complexity Analyzer
Scores queries on a 0.0–1.0 scale using weighted features:

| Feature | Weight | Rationale |
|---------|--------|-----------|
| Entity count | High | More entities → more graph traversals |
| Temporal/numerical constraints | High | Requires KAG's Math operators |
| Multi-hop indicators | High | Signals need for CoRAG chains |
| Domain specificity | Medium | Professional domains need KAG rules |
| Query length/structure | Low | Proxy for complexity |
| Intent type | Medium | Comparative/analytical harder than factual |

### Agent 3: Strategy Selector
Maps complexity score to concrete routing:

| Complexity | Strategy | Expected Latency |
|-----------|----------|-------------------|
| < 0.3 | LightRAG low-level only | 50–200ms |
| 0.3–0.5 | LightRAG high-level only | 100–500ms |
| 0.5–0.7 | CoRAG greedy + LightRAG fallback | 500ms–2s |
| ≥ 0.7 | Full parallel dispatch (all engines) | 2–5s |

**Domain override**: Always include KAG for healthcare, legal, and finance domains regardless of complexity score.

### Agent 4: Retry & Escalation
- If quality score < threshold after synthesis, escalate to next complexity tier
- Max 2 retries before graceful degradation
- Escalation hierarchy: Simple → Moderate → Complex → Full Parallel

## Consequences

**Positive:**
- Simple queries served in <200ms (LightRAG only), no wasted compute
- Complex queries get full engine coverage without manual intervention
- Domain override catches hidden complexity (e.g., drug interactions appear simple but need KAG)
- Self-correcting via escalation — initial misclassification is recoverable
- 60–70% of queries expected to be low-complexity, saving significant compute

**Negative:**
- Complexity scoring weights need empirical tuning per deployment
- Additional latency from analysis step (~10–50ms) on every query
- Escalation adds latency for initially misrouted queries
- Domain detection accuracy affects KAG override (false positives waste compute)

## Alternatives Considered

1. **Always use all engines**: Simplest — but 3–5x compute cost for simple queries
2. **User-selected strategy**: Explicit — but poor UX, requires RAG knowledge
3. **LLM-based routing (single call)**: Flexible — but adds LLM latency and cost to every query
4. **Rule-based routing only**: Predictable — but brittle, doesn't adapt to novel query patterns
