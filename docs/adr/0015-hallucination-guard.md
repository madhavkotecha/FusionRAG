# ADR-0015: Hallucination Guard with Claim Verification

## Status

Deferred — not implemented as of 2026-05-12

## Implementation Status

No claim extractor, no evidence matcher, no citation injector exists in the codebase. Grep for `hallucination`, `HallucinationGuard`, `fact_check`, `claim_verification` returns no implementation hits. Generators (`llm_generator`, `corag_chain`, `kag_executor.KAGDeduceExecutor`, `ollama_generator`, `vllm_generator`) emit answers without post-hoc verification. Implementing this is downstream of the mutual index (ADR-0010, also deferred).

## Context

LLMs generate plausible but sometimes unfounded text. In a RAG system, the generated response should be grounded in retrieved evidence. Without verification:
- Users may trust incorrect information
- Regulated domains (healthcare, legal, finance) face compliance risk
- Citation links may point to evidence that doesn't actually support the claim

## Decision

Implement a **hallucination guard** as a post-generation verification step with iterative revision:

### Process

1. **Claim Extraction**: Parse generated response into discrete factual claims
2. **Evidence Matching**: For each claim, search retrieved evidence for supporting passages
3. **Classification**: Label each claim as:
   - **Supported**: Evidence directly supports the claim
   - **Partially Supported**: Evidence partially supports, some extrapolation
   - **Unsupported**: No evidence found for this claim
4. **Iterative Revision**: If unsupported claims exist:
   - Regenerate with explicit instruction to only use provided evidence
   - Max 2 revision iterations (prevents infinite loops)
   - If still unsupported after 2 iterations, flag claim with confidence warning
5. **Quality Score**: Compute overall quality based on:
   - Evidence coverage (30%): % of response supported by evidence
   - Citation completeness (20%): % of claims with source citations
   - Source diversity (15%): Number of distinct source documents
   - Reasoning coherence (20%): Logical flow for multi-hop queries
   - Confidence score (15%): Average confidence of supporting evidence

### Quality Threshold
- Score < threshold triggers escalation (see ADR-0013, Retry & Escalation)
- Threshold configurable per tenant and domain
- Default: 0.7 for general, 0.85 for healthcare/legal/finance

### LLM Routing for Verification
- Simple claims: Use fast/cheap model (Haiku-class)
- Complex claims (multi-hop, numerical): Use capable model (Sonnet/Opus-class)
- Cost optimization: ~60–70% of claims are simple

## Consequences

**Positive:**
- Reduces hallucination in generated responses
- Provides quantitative quality score for every response
- Quality threshold drives automatic escalation for poor answers
- Iterative revision improves answer grounding without user intervention
- Meets compliance requirements for regulated domains

**Negative:**
- Additional LLM calls per response (claim extraction + evidence matching + potential revision)
- Adds 200–500ms latency for verification
- Claim extraction itself can be imperfect (may miss implicit claims)
- Max 2 iterations may not resolve all hallucinations
- Evidence matching relies on embedding similarity — may miss semantic equivalences

## Alternatives Considered

1. **No verification**: Fastest — but unacceptable for enterprise/regulated use
2. **Prompt engineering only ("only use provided context")**: Zero overhead — but unreliable, LLMs still hallucinate
3. **NLI-based verification (entailment model)**: Faster than LLM — but less accurate for complex claims
4. **Human-in-the-loop review**: Most accurate — but doesn't scale, adds significant latency
5. **Confidence score only (no revision)**: Cheaper — but doesn't improve the answer, just flags it
