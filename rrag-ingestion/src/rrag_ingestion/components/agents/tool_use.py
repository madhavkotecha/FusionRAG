from __future__ import annotations

import json
import logging

from rrag_ingestion.components.agents.base import BaseAgent
from rrag_ingestion.core.base import ComponentResult, register_component

logger = logging.getLogger(__name__)


TOOL_USE_PROMPT = """You have access to the following tools:

{tool_definitions}

Based on the query and context, decide which tool to call and with what arguments.
Output a JSON object with "tool" and "arguments" fields.
If no tool is needed, output {{"tool": "none", "arguments": {{}}}}.

Query: {query}
Context: {context}

Tool call:"""


@register_component
class ToolUseAgent(BaseAgent):
    """Agent that selects and calls tools based on the query."""

    name = "agent.tool_use"
    version = "0.1.0"
    description = "Tool-calling agent that selects and invokes appropriate tools/APIs"
    config_schema = {
        "llm_model": {"type": "string", "default": "gpt-4o-mini"},
        "tools": {
            "type": "object",
            "default": {
                "search": {"description": "Search the knowledge base", "params": ["query", "top_k"]},
                "web_search": {"description": "Search the web", "params": ["query"]},
                "calculate": {"description": "Perform calculations", "params": ["expression"]},
                "lookup": {"description": "Look up a specific entity", "params": ["entity_name"]},
            },
        },
    }

    async def invoke(self, input_data: ComponentResult, config: dict) -> ComponentResult:
        query = input_data.data.get("query", "")
        if not query:
            return ComponentResult(data=input_data.data, errors=["No query for tool use"])

        model = config.get("llm_model", "gpt-4o-mini")
        tools = config.get("tools", {})

        try:
            from rrag_ingestion.services.openai_client import get_openai_client
            client = get_openai_client()

            tool_defs = json.dumps(tools, indent=2)
            context = str({k: str(v)[:100] for k, v in input_data.data.items() if k != "embeddings"})

            prompt = TOOL_USE_PROMPT.format(
                tool_definitions=tool_defs, query=query, context=context
            )

            response = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
            )

            raw = response.choices[0].message.content or ""
            if "```" in raw:
                raw = raw.split("```json")[-1].split("```")[0] if "```json" in raw else raw.split("```")[1].split("```")[0]

            tool_call = json.loads(raw.strip())

            return ComponentResult(
                data={
                    **input_data.data,
                    "tool_call": tool_call,
                    "agent_type": "tool_use",
                },
                metadata={"tool": tool_call.get("tool", "none")},
            )

        except Exception as e:
            return ComponentResult(data=input_data.data, errors=[f"Tool use agent failed: {e}"])
