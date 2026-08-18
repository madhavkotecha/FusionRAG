from __future__ import annotations

import logging
import os

import httpx

from rrag_ingestion.components.generators.base import BaseGenerator
from rrag_ingestion.core.base import ComponentResult, register_component

logger = logging.getLogger(__name__)


@register_component
class OllamaGenerator(BaseGenerator):
    """LLM generator using Ollama — runs on host with MPS acceleration."""

    name = "ollama_generator"
    version = "0.1.0"
    description = "Local LLM generation via Ollama (MPS-accelerated on Apple Silicon)"
    config_schema = {
        "model": {"type": "string", "default": "llama3.2"},
        "base_url": {"type": "string", "default": ""},
        "temperature": {"type": "number", "default": 0.7},
        "max_tokens": {"type": "integer", "default": 2048},
        "system_prompt": {
            "type": "string",
            "default": "You are a helpful assistant. Answer based on the provided context.",
        },
    }

    async def invoke(self, input_data: ComponentResult, config: dict) -> ComponentResult:
        query = input_data.data.get("query", "")
        retrieved = input_data.data.get("retrieved", [])

        if not query:
            return ComponentResult(data=input_data.data, errors=["No query for generation"])

        from rrag_ingestion.config import settings

        model = config.get("model", "llama3.2")
        base_url = (
            config.get("base_url")
            or settings.ollama_base_url
            or os.environ.get("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
        )
        temperature = config.get("temperature", 0.7)
        max_tokens = config.get("max_tokens", 2048)
        system_prompt = config.get(
            "system_prompt",
            "You are a helpful assistant. Answer based on the provided context.",
        )

        # Build context from retrieved documents
        context_parts = []
        for i, doc in enumerate(retrieved):
            content = doc.content if hasattr(doc, "content") else doc.get("content", "")
            if content:
                context_parts.append(f"[Document {i + 1}]\n{content}")

        context = "\n\n".join(context_parts)
        user_prompt = f"Context:\n{context}\n\nQuestion: {query}" if context else query

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{base_url}/api/chat",
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "stream": False,
                        "options": {
                            "temperature": temperature,
                            "num_predict": max_tokens,
                        },
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            answer = data.get("message", {}).get("content", "")
            tokens_used = data.get("eval_count", 0) + data.get("prompt_eval_count", 0)

            return ComponentResult(
                data={**input_data.data, "answer": answer},
                metadata={
                    "model": model,
                    "provider": "ollama",
                    "tokens_used": tokens_used,
                    "context_docs": len(context_parts),
                },
            )

        except Exception as e:
            return ComponentResult(
                data=input_data.data,
                errors=[f"Ollama generation failed: {e}"],
            )
