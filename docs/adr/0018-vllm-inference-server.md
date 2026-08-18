# ADR-0018: vLLM for LLM Inference

## Status

Accepted

## Implementation Status (as of 2026-05-12)

vLLM is wired in via two paths:

1. **Direct components:** `rrag-ingestion/src/rrag_ingestion/components/embedders/vllm_embedder.py` and `components/generators/vllm_generator.py` — usable directly in pipeline YAMLs.
2. **Unified LLM service:** `rrag-ingestion/src/rrag_ingestion/services/llm_service.py` routes via LiteLLM with `openai/<model>` prefix when `LLM_PROVIDER=vllm`, allowing all generators/embedders to transparently switch providers. See ADR-0027 (LLM Provider Abstraction Layer).

Production deployment uses **Qwen/Qwen3.5-9B** on a dedicated GPU host (commits `c8bf226` pin GPU 7 + TP=1, `94c0cf1` migrated ingestion components, `ea16a9a` replaced `gpt-4o-mini` references). The vLLM server itself is run **externally** to the docker-compose stack (host-network access via `host.docker.internal:8100`); the compose file does not run vLLM as a service.

## Context

The system makes heavy use of LLM calls: entity extraction during ingestion, query analysis, response generation, hallucination verification, and claim extraction. LLM inference is the most expensive operation in the pipeline — both in latency and cost. The inference server choice significantly impacts throughput, cost, and scalability.

## Decision

Use **vLLM** as the primary LLM inference server for self-hosted models.

### Key Capabilities

| Feature | Benefit |
|---------|---------|
| **PagedAttention** | Efficient GPU memory management, higher batch throughput |
| **Continuous batching** | Dynamic request batching, no wasted GPU cycles |
| **Prefix caching** | Cache common prompt prefixes (system prompts, knowledge context) — up to 90% token reduction |
| **Tensor parallelism** | Scale across multiple GPUs for large models |
| **OpenAI-compatible API** | Drop-in replacement for OpenAI SDK calls |

### Model Routing
- **Simple queries**: Fast/cheap model (e.g., Llama-3.1-8B-Instruct or Haiku-class API)
- **Complex queries**: Capable model (e.g., Llama-3.1-70B or Opus-class API)
- **Claim verification**: Fast model (most claims are simple factual checks)
- **Cost target**: 60–70% reduction via tiered routing

### Prefix Caching Strategy
System prompts and frequently-used knowledge contexts are cached at the KV-cache level:
```
[System prompt (cached)] + [Knowledge context (cached)] + [User query (new)]
```
Only the user query portion requires fresh computation.

### Fallback
For deployments without GPU infrastructure, fall back to **OpenAI API** with the same interface (vLLM's OpenAI-compatible API makes this seamless).

## Consequences

**Positive:**
- 2–4x throughput improvement over naive inference via continuous batching
- Prefix caching dramatically reduces per-query compute for repeated prompts
- OpenAI-compatible API means zero code changes between self-hosted and API fallback
- Tensor parallelism enables serving 70B+ parameter models
- Active open-source community with rapid feature development

**Negative:**
- Requires GPU infrastructure (NVIDIA GPUs with CUDA)
- Operational complexity of GPU cluster management
- Model-specific optimization (quantization, tensor parallelism config)
- vLLM updates may introduce breaking changes (fast-moving project)
- CoRAG fine-tuned model (Llama-3.1-8B) requires separate vLLM instance or model switching

## Alternatives Considered

1. **OpenAI API only**: Zero infrastructure — but vendor lock-in, per-token cost at scale, no prefix caching control
2. **TGI (Text Generation Inference)**: Mature — but less batch optimization than vLLM
3. **Ollama**: Simple setup — but no continuous batching, limited multi-GPU support
4. **TensorRT-LLM**: Fastest inference — but NVIDIA-only, complex setup, less flexible
5. **SGLang**: Promising — but newer, smaller community, less production-proven
