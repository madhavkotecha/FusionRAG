"""Centralized OpenAI client factory that respects runtime settings."""
from __future__ import annotations

import os

from openai import AsyncOpenAI

from rrag_ingestion.config import settings


def get_openai_client(
    api_key: str | None = None,
    base_url: str | None = None,
) -> AsyncOpenAI:
    """Create an AsyncOpenAI client using runtime settings with fallbacks.

    Priority for api_key:  explicit param > settings.openai_api_key > OPENAI_API_KEY env var
    Priority for base_url: explicit param > settings.openai_base_url > None (OpenAI default)
    """
    resolved_key = api_key or settings.openai_api_key or os.environ.get("OPENAI_API_KEY")
    resolved_base_url = base_url or settings.openai_base_url or None

    kwargs: dict[str, str] = {}
    if resolved_key:
        kwargs["api_key"] = resolved_key
    if resolved_base_url:
        kwargs["base_url"] = resolved_base_url

    return AsyncOpenAI(**kwargs)


def get_vllm_client(
    api_key: str | None = None,
    base_url: str | None = None,
) -> AsyncOpenAI:
    """Create an AsyncOpenAI client configured for a vLLM server.

    vLLM serves an OpenAI-compatible API, so AsyncOpenAI works directly.
    """
    resolved_base_url = base_url or settings.vllm_base_url or "http://host.docker.internal:8100"
    resolved_key = api_key or settings.vllm_api_key or "EMPTY"

    return AsyncOpenAI(api_key=resolved_key, base_url=resolved_base_url)
