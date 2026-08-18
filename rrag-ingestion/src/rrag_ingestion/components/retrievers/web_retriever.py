from __future__ import annotations

import logging

from rrag_ingestion.components.retrievers.base import BaseRetriever
from rrag_ingestion.core.base import ComponentResult, register_component
from rrag_ingestion.models.document import RetrievalResult

logger = logging.getLogger(__name__)


@register_component
class UltraRAGWebRetriever(BaseRetriever):
    """Web search retriever using Tavily or similar APIs, from UltraRAG."""

    name = "ultrarag.web_retriever"
    version = "0.1.0"
    description = "Web search retrieval via Tavily/Exa APIs (from UltraRAG)"
    config_schema = {
        "backend": {"type": "string", "default": "tavily", "enum": ["tavily", "exa"]},
        "api_key": {"type": "string", "default": ""},
        "top_k": {"type": "integer", "default": 5},
    }

    async def invoke(self, input_data: ComponentResult, config: dict) -> ComponentResult:
        query = input_data.data.get("query", "")
        subqueries = input_data.data.get("subqueries", [])
        queries = subqueries if subqueries else [query] if query else []

        if not queries:
            return ComponentResult(data=input_data.data, errors=["No query provided"])

        backend = config.get("backend", "tavily")
        api_key = config.get("api_key", "")
        top_k = config.get("top_k", 5)

        all_results = []
        errors = []

        for q in queries:
            try:
                if backend == "tavily":
                    results = await self._tavily_search(q, api_key, top_k)
                else:
                    results = await self._exa_search(q, api_key, top_k)
                all_results.extend(results)
            except Exception as e:
                errors.append(f"Web search failed for '{q}': {e}")

        return ComponentResult(
            data={**input_data.data, "retrieved": all_results},
            metadata={"result_count": len(all_results), "backend": backend},
            errors=errors,
        )

    async def _tavily_search(self, query: str, api_key: str, top_k: int) -> list[RetrievalResult]:
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.tavily.com/search",
                json={"query": query, "max_results": top_k, "api_key": api_key},
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

        results = []
        for i, item in enumerate(data.get("results", [])):
            results.append(RetrievalResult(
                id=f"web_{i}",
                content=item.get("content", item.get("snippet", "")),
                score=item.get("score", 1.0 - i * 0.1),
                metadata={"url": item.get("url", ""), "title": item.get("title", ""), "source": "tavily"},
            ))
        return results

    async def _exa_search(self, query: str, api_key: str, top_k: int) -> list[RetrievalResult]:
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.exa.ai/search",
                json={"query": query, "numResults": top_k, "contents": {"text": True}},
                headers={"x-api-key": api_key},
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

        results = []
        for i, item in enumerate(data.get("results", [])):
            results.append(RetrievalResult(
                id=f"web_{i}",
                content=item.get("text", ""),
                score=item.get("score", 1.0 - i * 0.1),
                metadata={"url": item.get("url", ""), "title": item.get("title", ""), "source": "exa"},
            ))
        return results
