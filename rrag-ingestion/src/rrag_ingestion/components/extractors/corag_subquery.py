from __future__ import annotations

import logging
import uuid

from rrag_ingestion.components.extractors.base import BaseExtractor
from rrag_ingestion.core.base import ComponentResult, register_component

logger = logging.getLogger(__name__)

SUBQUERY_PROMPT = """You are decomposing a complex query into simpler sub-queries for iterative retrieval.

Given the main query and any previous sub-queries with their answers, generate the next follow-up question that would help answer the main query.

{history}

Main query: {query}

Output only the next sub-query, nothing else."""


@register_component
class CoRAGSubQueryDecomposer(BaseExtractor):
    """Iterative sub-query decomposition extracted from CoRAG."""

    name = "corag.subquery_decomposer"
    version = "0.1.0"
    description = "Iterative sub-query decomposition for multi-hop reasoning (from CoRAG)"
    config_schema = {
        "llm_model": {"type": "string", "default": "gpt-4o-mini"},
        "max_hops": {"type": "integer", "default": 3},
        "temperature": {"type": "number", "default": 0.7},
    }

    async def invoke(self, input_data: ComponentResult, config: dict) -> ComponentResult:
        query = input_data.data.get("query", "")
        if not query:
            return ComponentResult(data=input_data.data, errors=["No query provided"])

        model = config.get("llm_model", "gpt-4o-mini")
        max_hops = config.get("max_hops", 3)
        temperature = config.get("temperature", 0.7)

        subqueries = []
        subanswers = input_data.data.get("subanswers", [])
        errors = []

        try:
            from rrag_ingestion.services.openai_client import get_openai_client
            client = get_openai_client()

            for hop in range(max_hops):
                history = ""
                for i, (sq, sa) in enumerate(zip(subqueries, subanswers)):
                    history += f"Sub-query {i + 1}: {sq}\nAnswer {i + 1}: {sa}\n\n"

                prompt = SUBQUERY_PROMPT.format(history=history, query=query)
                response = await client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                )
                subquery = response.choices[0].message.content.strip()
                subqueries.append(subquery)

                # If we have fewer subanswers than subqueries, stop generating
                if len(subanswers) <= hop:
                    break

        except Exception as e:
            errors.append(f"Sub-query decomposition failed: {e}")

        return ComponentResult(
            data={
                **input_data.data,
                "subqueries": subqueries,
                "query": query,
            },
            metadata={"hop_count": len(subqueries)},
            errors=errors,
        )
