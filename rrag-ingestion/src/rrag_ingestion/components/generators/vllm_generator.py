from __future__ import annotations

import logging

from rrag_ingestion.components.generators.base import BaseGenerator
from rrag_ingestion.core.base import ComponentResult, register_component

logger = logging.getLogger(__name__)


@register_component
class VLLMGenerator(BaseGenerator):
    """LLM generator using vLLM — OpenAI-compatible API with GPU acceleration."""

    name = "vllm_generator"
    version = "0.1.0"
    description = "LLM generation via vLLM (GPU-accelerated, OpenAI-compatible)"
    config_schema = {
        "model": {"type": "string", "default": "Qwen/Qwen3.5-9B"},
        "base_url": {"type": "string", "default": ""},
        "api_key": {"type": "string", "default": ""},
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

        model = config.get("model", "Qwen/Qwen3.5-9B")
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
            from rrag_ingestion.services.openai_client import get_vllm_client

            client = get_vllm_client(
                api_key=config.get("api_key") or None,
                base_url=config.get("base_url") or None,
            )

            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )

            answer = response.choices[0].message.content or ""

            return ComponentResult(
                data={**input_data.data, "answer": answer},
                metadata={
                    "provider": "vllm",
                    "model": model,
                    "tokens_used": response.usage.total_tokens if response.usage else 0,
                    "context_docs": len(context_parts),
                },
            )

        except Exception as e:
            return ComponentResult(data=input_data.data, errors=[f"vLLM generation failed: {e}"])
