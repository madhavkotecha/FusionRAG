"""Evidence sufficiency evaluator.

The evaluator inspects the evidence gathered so far and decides whether the
agent has enough material to generate a final answer, or whether another
retrieval round is needed.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from .prompts import EVALUATOR_SYSTEM_PROMPT, EVALUATOR_USER_PROMPT

logger = logging.getLogger(__name__)


async def evaluate_evidence(
    query: str,
    entities: list[dict[str, Any]],
    relations: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
    model: str = "gpt-4o-mini",
) -> dict[str, Any]:
    """Evaluate whether the collected evidence is sufficient.

    Parameters
    ----------
    query:
        The original user query.
    entities, relations, chunks:
        Evidence gathered so far.
    model:
        OpenAI-compatible model identifier.

    Returns
    -------
    dict with keys ``sufficient`` (bool) and ``reason`` (str).
    """
    from ..extraction import _call_llm

    entity_names = ", ".join(
        e.get("entity_name", "") for e in entities[:15]
    ) or "(none)"

    user_prompt = EVALUATOR_USER_PROMPT.format(
        query=query,
        entity_count=len(entities),
        relation_count=len(relations),
        chunk_count=len(chunks),
        entity_names=entity_names,
    )

    raw = await _call_llm(user_prompt, model, system_prompt=EVALUATOR_SYSTEM_PROMPT)

    if raw:
        try:
            parsed = json.loads(raw)
            return {
                "sufficient": bool(parsed.get("sufficient", False)),
                "reason": str(parsed.get("reason", "")),
            }
        except (json.JSONDecodeError, TypeError):
            logger.warning("Evaluator produced unparseable output")

    # Heuristic fallback: sufficient if we have entities OR chunks
    has_evidence = len(entities) > 0 or len(chunks) > 0
    return {
        "sufficient": has_evidence,
        "reason": (
            "Heuristic: evidence present" if has_evidence
            else "No evidence found"
        ),
    }
