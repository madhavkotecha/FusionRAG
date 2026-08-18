# ADR-0013: Agentic State Machine Orchestration

## Status

Accepted — Partial implementation (agent loop only, no formal state machine)

## Implementation Status (as of 2026-05-12)

The **agentic RAG retrieval composite** (`rrag-pipeline-service/src/pipeline_service/framework/lightrag/components/agentic_rag_retrieval.py` + sibling `agent/` package: `planner.py`, `evaluator.py`, `tool_executor.py`, `tools.py`, `prompts.py`, `trace.py`) implements a plan → execute → evaluate → loop control flow with conditional back-edges in the composite-component framework (ADR-0026).

The ingestion service also has agent primitives in `rrag-ingestion/src/rrag_ingestion/components/agents/`: `orchestrator.py`, `router.py`, `tool_use.py`, `reflection.py`, `memory.py`.

What's **not** built: a formal state-machine DSL with declarative transitions, guard conditions, parallel branches, or compensating actions. The current implementation is procedural Python inside composite component `@step` methods.

## Context

The query processing pipeline involves multiple decision points: intent classification, complexity analysis, engine selection, quality evaluation, and retry/escalation. These could be implemented as:
- Hardcoded if/else chains
- Rule engine
- LLM function calling
- State machine with specialized agents

## Decision

Implement query orchestration as a **state machine with four specialized agents**, each handling a distinct phase:

### State Machine

```
┌──────────┐    ┌──────────────┐    ┌────────────────┐    ┌──────────────┐
│  Query    │───→│  Complexity  │───→│   Strategy     │───→│  Retrieval   │
│  Router   │    │  Analyzer    │    │   Selector     │    │  Execution   │
└──────────┘    └──────────────┘    └────────────────┘    └──────┬───────┘
                                                                  │
                                                                  ▼
                                                          ┌──────────────┐
                                    ┌─────────────────────│  Synthesis   │
                                    │                     │  & Quality   │
                                    │                     └──────────────┘
                                    ▼
                             ┌──────────────┐
                             │   Retry &    │──→ Escalate to higher
                             │  Escalation  │    complexity tier
                             └──────────────┘
```

### Agent Responsibilities

| Agent | Input | Output | Decision |
|-------|-------|--------|----------|
| **Query Router** | Raw query | Intent, entities, domain | What kind of question is this? |
| **Complexity Analyzer** | Router output | Score (0.0–1.0) | How hard is this question? |
| **Strategy Selector** | Complexity + domain | Engine config | Which engines, what strategy? |
| **Retry & Escalation** | Quality score | Escalation decision | Is the answer good enough? |

### Self-Correction Loop
1. After synthesis, quality score is computed (evidence coverage, citation completeness, reasoning coherence)
2. If quality < threshold, Retry agent escalates to next complexity tier
3. Max 2 retries before graceful degradation (return best attempt with confidence warning)
4. Escalation hierarchy: Simple → Moderate → Complex → Full Parallel

### Observability
Every state transition is logged with:
- Agent name, input, output, duration
- Decision rationale (human-readable)
- Transition trigger (score threshold, domain override, escalation)

## Consequences

**Positive:**
- Clear separation of concerns — each agent has one job
- Self-correcting: misclassification at any stage is recoverable
- Observable: every decision is logged with rationale
- Extensible: add new agents without modifying existing ones
- Testable: each agent can be unit-tested independently

**Negative:**
- Four sequential agents add latency (~10–50ms total analysis overhead)
- State machine complexity increases with new states/transitions
- Agent quality depends on underlying LLM or scoring model
- Escalation retries add latency for initially misrouted queries (up to 2x)

## Alternatives Considered

1. **Hardcoded routing rules**: Fast — but brittle, no self-correction
2. **Single LLM call for all routing decisions**: Simpler — but monolithic, harder to debug
3. **ML classifier trained on query logs**: Data-efficient — but requires training data, cold start problem
4. **No routing (always use all engines)**: Simplest — but wasteful for simple queries
