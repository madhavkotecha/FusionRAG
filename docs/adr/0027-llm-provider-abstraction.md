# ADR-0027: LLM Provider Abstraction via LiteLLM

- **Status:** Accepted
- **Date:** 2026-03-26 (initial), 2026-04-01 (local-embeddings migration)
- **Deciders:** Architecture Team
- **Relates to:** ADR-0006 (Technology Choices), ADR-0018 (vLLM for LLM Inference), ADR-0016 (Component Registry Pattern)

## Context

Early generators and embedders called `openai.AsyncClient` directly. As the system added local-inference paths (vLLM with Qwen3.5-9B, Ollama on developer laptops), every component needed parallel implementations and `if provider == "openai" else …` branches kept multiplying. Switching the model used by an entire pipeline required editing every component's config block.

Additionally, the product needed an **admin UI to switch LLM providers at runtime** — pointing the whole system at OpenAI, a self-hosted vLLM instance, or Ollama without redeploying.

## Decision

Introduce a single LLM service module (`rrag-ingestion/src/rrag_ingestion/services/llm_service.py`) wrapping **LiteLLM**, with the active provider selected via the `LLM_PROVIDER` setting (env or admin UI). All generation and embedding components consume this service.

### Provider routing

```
LLM_PROVIDER=openai → litellm calls api.openai.com
LLM_PROVIDER=vllm   → litellm calls VLLM_BASE_URL (default host.docker.internal:8100)
                      with model name prefixed "openai/<model>" (OpenAI-compatible API)
LLM_PROVIDER=ollama → litellm calls OLLAMA_BASE_URL with model "ollama/<model>"
```

Credential resolution (`_resolve_credentials()`) picks `api_key` / `api_base` per provider, with env-var fallback. Model prefixing (`_maybe_prefix_model()`) ensures LiteLLM routes to the correct backend.

### Admin UI

`rrag-frontend/src/pages/admin/SystemSettingsPage.tsx` exposes provider/model selection. Backend: `rrag-ingestion/src/rrag_ingestion/api/admin.py` exposes `/admin/config` GET/PUT for runtime configuration.

### Per-component overrides

Components (`vllm_embedder`, `vllm_generator`, `ollama_embedder`, `ollama_generator`, `openai_embedder`, `llm_generator`) still exist for cases where a single pipeline step needs a different provider than the system default — e.g., embeddings on local Ollama for cost, generation on OpenAI for quality.

## Consequences

**Positive:**
- One-line provider switch for the whole platform
- Admin can change provider without code deploy
- New providers (Anthropic, Bedrock, etc.) require only adding the LiteLLM model prefix + credential resolution, not new component classes
- Streaming, function-calling, and tool-use semantics stay consistent (LiteLLM normalizes responses)
- Production migration to local Qwen3.5-9B (commits `ea16a9a`, `94c0cf1`, `58f3ca1`) was a single env-var flip across all components

**Negative:**
- LiteLLM adds a dependency layer; subtle behavioural differences between providers may leak through (e.g., temperature semantics, tool-call formats)
- Local vLLM is currently **host-network only** (`host.docker.internal:8100`) — the compose stack does not run vLLM as a container, so production deployment requires a separate GPU host
- Debugging LiteLLM-wrapped calls is one stack-frame removed from raw provider SDKs

## Alternatives Considered

1. **Direct provider SDKs in each component** — what we started with. Doubles code per provider added.
2. **OpenAI-compatible-only routing** — works for vLLM but not Ollama, which has its own API.
3. **LangChain LLM abstraction** — heavier dependency, more abstractions than needed.

## References

- Commits: `831d0eb` (admin UI), `c643f7d` (vLLM integration), `94c0cf1` (component migration), `85ff359` (query/embedding/streaming routing), `175f462` (local embeddings)
- Files: `rrag-ingestion/src/rrag_ingestion/services/llm_service.py`, `rrag-ingestion/src/rrag_ingestion/api/admin.py`, `rrag-frontend/src/pages/admin/SystemSettingsPage.tsx`
