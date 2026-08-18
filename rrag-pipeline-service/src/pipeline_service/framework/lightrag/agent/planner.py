"""LLM-based retrieval strategy planner.

The planner inspects the user query and any evidence gathered so far, then
decides which tools to call next.  Its output is a list of :class:`ToolCall`
objects.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from .tools import ToolCall, TOOL_REGISTRY
from .prompts import PLANNER_SYSTEM_PROMPT, PLANNER_USER_PROMPT

logger = logging.getLogger(__name__)


async def plan_retrieval_strategy(
    query: str,
    evidence_summary: str = "",
    model: str = "gpt-4o-mini",
) -> list[ToolCall]:
    """Ask the LLM to plan the next retrieval tools to invoke.

    Parameters
    ----------
    query:
        The original user query.
    evidence_summary:
        A textual summary of evidence collected so far (empty on first pass).
    model:
        OpenAI-compatible model identifier.

    Returns
    -------
    A list of :class:`ToolCall` objects.  Returns a sensible default plan if
    the LLM is unavailable or produces unparseable output.
    """
    from ..extraction import _call_llm

    # Build tool descriptions for the system prompt
    tool_descs = "\n".join(
        f"- **{td.name}**: {td.description}  Parameters: {json.dumps(td.parameters)}"
        for td in TOOL_REGISTRY.values()
    )

    system_prompt = PLANNER_SYSTEM_PROMPT.format(tool_descriptions=tool_descs)
    user_prompt = PLANNER_USER_PROMPT.format(
        query=query, evidence_summary=evidence_summary or "(none)"
    )

    raw = await _call_llm(user_prompt, model, system_prompt=system_prompt)

    if raw:
        try:
            calls_raw = json.loads(raw)
            if isinstance(calls_raw, list):
                return [
                    ToolCall(
                        tool_name=c.get("tool_name", ""),
                        arguments=c.get("arguments", {}),
                    )
                    for c in calls_raw
                    if c.get("tool_name") in TOOL_REGISTRY
                ]
        except (json.JSONDecodeError, TypeError):
            logger.warning("Planner produced unparseable output, using default plan")

    # Default fallback plan
    return _default_plan(query)


def _default_plan(query: str) -> list[ToolCall]:
    """Return a conservative default plan when the LLM is unavailable."""
    return [
        ToolCall(
            tool_name="graph_entity_search",
            arguments={"query": query, "top_k": 10},
        ),
        ToolCall(
            tool_name="vector_chunk_search",
            arguments={"query": query, "top_k": 10},
        ),
    ]
