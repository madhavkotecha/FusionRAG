from __future__ import annotations

import logging
from typing import Any

from rrag_ingestion.components.agents.base import BaseAgent
from rrag_ingestion.core.base import ComponentResult, register_component

logger = logging.getLogger(__name__)

ORCHESTRATION_PROMPT = """You are an orchestration agent for a RAG system. Given a user query and available tools, decide the sequence of actions to take.

Available tools:
{tools}

Current context:
{context}

User query: {query}

Output a JSON array of steps, each with "tool" and "config" fields. Example:
[
  {{"tool": "retrieval", "config": {{"mode": "hybrid", "top_k": 10}}}},
  {{"tool": "generate", "config": {{"temperature": 0.7}}}}
]

Only output the JSON array, nothing else."""


@register_component
class AgentOrchestrator(BaseAgent):
    """Multi-step agent that dynamically selects and chains components."""

    name = "agent.orchestrator"
    version = "0.1.0"
    description = "Agentic orchestrator that dynamically plans and executes RAG component chains"
    config_schema = {
        "llm_model": {"type": "string", "default": "gpt-4o-mini"},
        "max_steps": {"type": "integer", "default": 10},
        "available_tools": {
            "type": "array",
            "default": ["retrieval", "web_search", "extract_entities", "generate", "math", "deduce"],
        },
    }

    async def invoke(self, input_data: ComponentResult, config: dict) -> ComponentResult:
        query = input_data.data.get("query", "")
        if not query:
            return ComponentResult(data=input_data.data, errors=["No query for orchestration"])

        model = config.get("llm_model", "gpt-4o-mini")
        max_steps = config.get("max_steps", 10)
        tools = config.get("available_tools", ["retrieval", "generate"])

        try:
            import json
            from rrag_ingestion.services.openai_client import get_openai_client
            client = get_openai_client()

            tools_desc = "\n".join(f"- {t}" for t in tools)
            context = json.dumps({
                k: str(v)[:200] for k, v in input_data.data.items()
                if k not in ("embeddings",)
            }, default=str)

            prompt = ORCHESTRATION_PROMPT.format(
                tools=tools_desc, context=context, query=query
            )

            response = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
            )

            raw = response.choices[0].message.content or ""
            # Parse JSON from response
            if "```" in raw:
                raw = raw.split("```")[1] if "```json" not in raw else raw.split("```json")[1].split("```")[0]

            plan = json.loads(raw.strip())
            if not isinstance(plan, list):
                plan = [plan]

            return ComponentResult(
                data={
                    **input_data.data,
                    "agent_plan": plan[:max_steps],
                    "agent_type": "orchestrator",
                },
                metadata={"planned_steps": len(plan[:max_steps])},
            )

        except Exception as e:
            return ComponentResult(data=input_data.data, errors=[f"Orchestration failed: {e}"])
