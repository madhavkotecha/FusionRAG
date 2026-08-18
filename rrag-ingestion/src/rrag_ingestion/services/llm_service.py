"""LLM service using LiteLLM for unified provider access."""
from __future__ import annotations

import logging
import os
from typing import Any, AsyncGenerator

import litellm

from rrag_ingestion.config import settings

logger = logging.getLogger(__name__)

# Suppress litellm's verbose logs
litellm.suppress_debug_info = True


def _resolve_credentials(provider: str | None = None) -> dict[str, str]:
    """Resolve API key and base URL for a provider, with env var fallback.

    Defaults to the configured provider; an explicit provider lets the
    OpenAI fallback path resolve OpenAI credentials independently.
    """
    provider = provider or settings.llm_provider
    creds: dict[str, str] = {}

    if provider == "vllm":
        creds["api_key"] = settings.vllm_api_key or "EMPTY"
        creds["api_base"] = settings.vllm_base_url or "http://host.docker.internal:8000"
    elif provider == "ollama":
        creds["api_base"] = settings.ollama_base_url or "http://host.docker.internal:11434"
        creds["api_key"] = "ollama"  # LiteLLM requires a non-empty api_key
    else:
        key = settings.openai_api_key or os.environ.get("OPENAI_API_KEY", "")
        if key:
            creds["api_key"] = key
        base = settings.openai_base_url or None
        if base:
            creds["api_base"] = base

    return creds


def _coerce_model_for_provider(model: str, provider: str | None = None) -> str:
    """Ensure the model name is one the target provider can actually serve.

    Callers commonly default to an OpenAI model name (e.g. "gpt-4o-mini"). Under
    a vLLM provider that name produces a 400 *model-not-found* — which is NOT a
    connection error, so it would not trigger the OpenAI fallback and would surface
    as a hard error. When the provider is vLLM and an OpenAI-style name leaks
    through, substitute the configured vLLM-served model (ADR-0018 model routing).

    A model name already matching the vLLM-served model, or any non-OpenAI-style
    name (e.g. "Qwen/..."), is left untouched.
    """
    provider = provider or settings.llm_provider
    if provider == "vllm" and model.startswith(("gpt-", "o1", "o3", "chatgpt-")):
        return settings.vllm_model
    return model


def _maybe_prefix_model(model: str, provider: str | None = None) -> str:
    """Prefix model name for LiteLLM routing when using vLLM or Ollama provider."""
    provider = provider or settings.llm_provider
    if provider == "vllm" and not model.startswith(("openai/", "vllm/")):
        return f"openai/{model}"
    if provider == "ollama" and not model.startswith("ollama/"):
        return f"ollama/{model}"
    return model


def select_model(tier: str | None) -> str:
    """Map a complexity tier to a concrete model name (ADR-0018 model routing).

    "fast"    -> simple queries / claim verification (cheap, low latency)
    "capable" -> complex / multi-hop queries
    anything else / None -> the configured default model
    """
    if tier == "fast":
        return settings.llm_model_fast
    if tier == "capable":
        return settings.llm_model_capable
    return settings.default_llm_model


def _is_connection_error(exc: Exception) -> bool:
    """True when an exception indicates the LLM endpoint was unreachable.

    Used to decide whether to fall back from vLLM to OpenAI. We match on
    exception type names (robust across litellm versions) and httpx transport
    errors, but NOT on request-level errors like 400/401 — those should surface.
    """
    type_name = type(exc).__name__
    if type_name in (
        "APIConnectionError",
        "APITimeoutError",
        "Timeout",
        "ServiceUnavailableError",
        "InternalServerError",
    ):
        return True
    try:
        import httpx

        if isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout)):
            return True
    except ImportError:
        pass
    msg = str(exc).lower()
    return any(s in msg for s in ("connection refused", "connection error", "timed out", "max retries", "failed to establish"))


def _openai_fallback_model(requested: str) -> str:
    """Pick an OpenAI-recognizable model for the fallback path.

    If the caller already asked for an OpenAI model, keep it; otherwise (e.g. a
    vLLM-served model name like 'Qwen/...') use the configured OpenAI fallback.
    """
    if requested.startswith(("gpt-", "o1", "o3", "chatgpt-")):
        return requested
    return settings.openai_fallback_model


def _build_params(
    *,
    messages: list[dict[str, Any]],
    model: str,
    provider: str,
    temperature: float,
    max_tokens: int,
    stream: bool,
    tools: list[dict] | None,
    tool_choice: str | dict | None,
    api_key: str | None,
    api_base: str | None,
    extra: dict[str, Any],
) -> dict[str, Any]:
    """Assemble litellm params for a given provider, injecting credentials."""
    params: dict[str, Any] = {
        "model": _maybe_prefix_model(_coerce_model_for_provider(model, provider), provider),
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": stream,
        "timeout": settings.llm_request_timeout,
    }
    if tools:
        params["tools"] = tools
    if tool_choice is not None:
        params["tool_choice"] = tool_choice

    creds = _resolve_credentials(provider)
    if api_key:
        creds["api_key"] = api_key
    if api_base:
        creds["api_base"] = api_base
    params.update(creds)
    params.update(extra)
    return params


def _openai_fallback_available() -> bool:
    """True when the OpenAI fallback is enabled and a key is configured."""
    return bool(
        settings.llm_fallback_to_openai
        and (settings.openai_api_key or os.environ.get("OPENAI_API_KEY"))
    )


async def completion(
    messages: list[dict[str, Any]],
    model: str | None = None,
    tier: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    tools: list[dict] | None = None,
    tool_choice: str | dict | None = None,
    stream: bool = False,
    api_key: str | None = None,
    api_base: str | None = None,
    **kwargs: Any,
) -> Any:
    """Call LLM via LiteLLM. Returns a response (or async generator if stream=True).

    Model selection: explicit ``model`` wins; otherwise ``tier`` ("fast"/"capable")
    maps to a configured model (ADR-0018 routing); otherwise the default model.
    When the provider is vLLM and the server is unreachable, transparently falls
    back to OpenAI if configured (ADR-0018 fallback).
    """
    resolved_model = model or select_model(tier)
    provider = settings.llm_provider
    params = _build_params(
        messages=messages, model=resolved_model, provider=provider,
        temperature=temperature, max_tokens=max_tokens, stream=stream,
        tools=tools, tool_choice=tool_choice, api_key=api_key, api_base=api_base, extra=kwargs,
    )

    try:
        return await litellm.acompletion(**params)
    except Exception as exc:
        if provider == "vllm" and _openai_fallback_available() and _is_connection_error(exc):
            logger.warning("vLLM unreachable (%s); falling back to OpenAI", exc)
            fb_params = _build_params(
                messages=messages, model=_openai_fallback_model(resolved_model), provider="openai",
                temperature=temperature, max_tokens=max_tokens, stream=stream,
                tools=tools, tool_choice=tool_choice, api_key=api_key, api_base=api_base, extra=kwargs,
            )
            return await litellm.acompletion(**fb_params)
        raise


async def stream_completion(
    messages: list[dict[str, Any]],
    model: str | None = None,
    tier: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    tools: list[dict] | None = None,
    tool_choice: str | dict | None = None,
    api_key: str | None = None,
    api_base: str | None = None,
    **kwargs: Any,
) -> AsyncGenerator[Any, None]:
    """Stream LLM response tokens via LiteLLM, with the same routing + vLLM->OpenAI fallback."""
    resolved_model = model or select_model(tier)
    provider = settings.llm_provider
    params = _build_params(
        messages=messages, model=resolved_model, provider=provider,
        temperature=temperature, max_tokens=max_tokens, stream=True,
        tools=tools, tool_choice=tool_choice, api_key=api_key, api_base=api_base, extra=kwargs,
    )

    try:
        response = await litellm.acompletion(**params)
    except Exception as exc:
        if provider == "vllm" and _openai_fallback_available() and _is_connection_error(exc):
            logger.warning("vLLM unreachable (%s); streaming via OpenAI fallback", exc)
            fb_params = _build_params(
                messages=messages, model=_openai_fallback_model(resolved_model), provider="openai",
                temperature=temperature, max_tokens=max_tokens, stream=True,
                tools=tools, tool_choice=tool_choice, api_key=api_key, api_base=api_base, extra=kwargs,
            )
            response = await litellm.acompletion(**fb_params)
        else:
            raise

    async for chunk in response:
        yield chunk


async def check_llm_health() -> dict[str, Any]:
    """Probe the configured LLM backend for real connectivity (ADR-0018).

    For vLLM/Ollama this makes a live HTTP request to the server; for OpenAI it
    reports whether a key is configured (a live call would incur cost).
    """
    provider = settings.llm_provider
    info: dict[str, Any] = {"provider": provider, "fallback_to_openai": settings.llm_fallback_to_openai}

    try:
        if provider == "vllm":
            import httpx

            base = (settings.vllm_base_url or "").rstrip("/")
            root = base[:-3].rstrip("/") if base.endswith("/v1") else base
            url = f"{root}/health"
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(url)
            info["endpoint"] = url
            info["model"] = settings.vllm_model
            info["status"] = "ok" if resp.status_code == 200 else f"unhealthy (HTTP {resp.status_code})"
        elif provider == "ollama":
            import httpx

            base = (settings.ollama_base_url or "").rstrip("/")
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{base}/api/tags")
            info["endpoint"] = base
            info["status"] = "ok" if resp.status_code == 200 else f"unhealthy (HTTP {resp.status_code})"
        else:  # openai
            has_key = bool(settings.openai_api_key or os.environ.get("OPENAI_API_KEY"))
            info["status"] = "configured" if has_key else "no api key"
    except Exception as e:
        info["status"] = f"error: {e}"

    return info


async def embedding(
    input_text: str | list[str],
    model: str = "text-embedding-3-small",
    api_key: str | None = None,
    api_base: str | None = None,
) -> list[list[float]]:
    """Generate embeddings via LiteLLM."""
    model = _maybe_prefix_model(model)
    if isinstance(input_text, str):
        input_text = [input_text]

    params: dict[str, Any] = {"model": model, "input": input_text}
    creds = _resolve_credentials()
    if api_key:
        creds["api_key"] = api_key
    if api_base:
        creds["api_base"] = api_base
    params.update(creds)

    response = await litellm.aembedding(**params)
    return [item["embedding"] for item in response.data]
