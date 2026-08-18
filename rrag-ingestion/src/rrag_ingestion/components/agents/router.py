from __future__ import annotations

import json
import logging

from rrag_ingestion.components.agents.base import BaseAgent
from rrag_ingestion.core.base import ComponentResult, register_component

logger = logging.getLogger(__name__)

ROUTING_PROMPT = """You are a query router. Classify the query and select the best retrieval strategy.

Available strategies:
{strategies}

Query: {query}

Output a JSON object:
{{
  "strategy": "<strategy_name>",
  "reasoning": "<brief explanation>",
  "query_type": "<factual|analytical|comparative|procedural|creative>"
}}"""


@register_component
class QueryRouter(BaseAgent):
    """Routes queries to the most appropriate retrieval/generation pipeline."""

    name = "agent.router"
    version = "0.1.0"
    description = "Intelligent query router that selects optimal RAG strategy based on query type"
    config_schema = {
        "llm_model": {"type": "string", "default": "gpt-4o-mini"},
        "strategies": {
            "type": "object",
            "default": {
                "naive_vector": "Simple vector similarity search, best for factual lookups",
                "graph_local": "Knowledge graph local retrieval, best for entity-specific questions",
                "graph_hybrid": "Combined graph + vector, best for complex multi-entity questions",
                "multi_hop": "Iterative multi-hop retrieval, best for reasoning chains",
                "web_search": "Web search, best for current events or missing knowledge",
            },
        },
    }

    async def invoke(self, input_data: ComponentResult, config: dict) -> ComponentResult:
        query = input_data.data.get("query", "")
        if not query:
            return ComponentResult(data=input_data.data, errors=["No query for routing"])

        model = config.get("llm_model", "gpt-4o-mini")
        strategies = config.get("strategies", {})

        try:
            from rrag_ingestion.services.openai_client import get_openai_client
            client = get_openai_client()

            strategies_desc = "\n".join(f"- {k}: {v}" for k, v in strategies.items())
            prompt = ROUTING_PROMPT.format(strategies=strategies_desc, query=query)

            response = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
            )

            raw = response.choices[0].message.content or ""
            if "```" in raw:
                raw = raw.split("```json")[-1].split("```")[0] if "```json" in raw else raw.split("```")[1].split("```")[0]

            routing = json.loads(raw.strip())

            return ComponentResult(
                data={
                    **input_data.data,
                    "routing": routing,
                    "selected_strategy": routing.get("strategy", "naive_vector"),
                },
                metadata={
                    "strategy": routing.get("strategy"),
                    "query_type": routing.get("query_type"),
                },
            )

        except Exception as e:
            # Fallback to naive vector
            return ComponentResult(
                data={
                    **input_data.data,
                    "routing": {"strategy": "naive_vector", "reasoning": "fallback"},
                    "selected_strategy": "naive_vector",
                },
                errors=[f"Routing failed, using fallback: {e}"],
            )


@register_component
class AdaptiveRAGAgent(BaseAgent):
    """Adaptive RAG agent that adjusts strategy based on intermediate results."""

    name = "agent.adaptive_rag"
    version = "0.1.0"
    description = "Adaptive RAG that adjusts retrieval/generation strategy based on quality signals"
    config_schema = {
        "llm_model": {"type": "string", "default": "gpt-4o-mini"},
        "confidence_threshold": {"type": "number", "default": 0.7},
        "max_adaptations": {"type": "integer", "default": 3},
    }

    async def invoke(self, input_data: ComponentResult, config: dict) -> ComponentResult:
        query = input_data.data.get("query", "")
        answer = input_data.data.get("answer", "")
        reflection = input_data.data.get("reflection", {})
        current_strategy = input_data.data.get("selected_strategy", "naive_vector")

        score = reflection.get("score", 10)
        needs_retry = input_data.data.get("needs_retry", False)
        threshold = config.get("confidence_threshold", 0.7)
        max_adaptations = config.get("max_adaptations", 3)
        adaptations = input_data.data.get("adaptation_count", 0)

        if not needs_retry or adaptations >= max_adaptations or score / 10.0 >= threshold:
            return ComponentResult(
                data={**input_data.data, "adaptation_complete": True},
                metadata={"adaptations": adaptations, "final_score": score},
            )

        # Suggest next strategy based on issues
        strategy_escalation = {
            "naive_vector": "graph_hybrid",
            "graph_local": "graph_hybrid",
            "graph_hybrid": "multi_hop",
            "multi_hop": "web_search",
            "web_search": "multi_hop",
        }
        next_strategy = strategy_escalation.get(current_strategy, "graph_hybrid")

        return ComponentResult(
            data={
                **input_data.data,
                "selected_strategy": next_strategy,
                "adaptation_count": adaptations + 1,
                "adaptation_complete": False,
            },
            metadata={
                "adapted_from": current_strategy,
                "adapted_to": next_strategy,
                "adaptations": adaptations + 1,
            },
        )
