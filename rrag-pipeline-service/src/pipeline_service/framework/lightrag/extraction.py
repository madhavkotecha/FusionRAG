"""LLM-based entity and relation extraction.

Ported from ``LightRAG/lightrag/operate.py::extract_entities``.  The function
builds the extraction prompt, calls an LLM, parses the structured output into
entity and relation dicts, and optionally "gleans" (re-extracts) missed items.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from typing import Any

from .prompts import (
    ENTITY_EXTRACTION_SYSTEM_PROMPT,
    ENTITY_EXTRACTION_USER_PROMPT,
    ENTITY_CONTINUE_EXTRACTION_PROMPT,
    TUPLE_DELIMITER,
    COMPLETION_DELIMITER,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared LLM caller
# ---------------------------------------------------------------------------


async def _call_llm(
    prompt: str,
    model: str = "gpt-4o-mini",
    *,
    system_prompt: str | None = None,
    temperature: float = 0.0,
) -> str:
    """Call an OpenAI-compatible chat-completion endpoint.

    If ``OPENAI_API_KEY`` is not set, returns an empty string so that the
    pipeline can still be exercised in test/dev without a real API key.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

    if not api_key:
        logger.warning(
            "OPENAI_API_KEY not set -- returning empty LLM response (dev mode)"
        )
        return ""

    import httpx

    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    async with httpx.AsyncClient(timeout=120.0) as http:
        resp = await http.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": messages,
                "temperature": temperature,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _parse_extraction_output(
    text: str,
    tuple_delimiter: str = TUPLE_DELIMITER,
) -> dict[str, list[dict[str, Any]]]:
    """Parse the LLM extraction output into entity and relation dicts.

    The LLM produces lines like:
        entity<|#|>Name<|#|>Type<|#|>Description
        relation<|#|>Src<|#|>Tgt<|#|>Keywords<|#|>Description
    """
    entities: list[dict[str, Any]] = []
    relations: list[dict[str, Any]] = []

    for line in text.splitlines():
        line = line.strip()
        if not line or line == COMPLETION_DELIMITER:
            continue

        parts = line.split(tuple_delimiter)
        parts = [p.strip() for p in parts]

        if len(parts) >= 4 and "entity" in parts[0].lower():
            entity_name = _normalize_name(parts[1])
            if not entity_name:
                continue
            entities.append({
                "entity_id": entity_name,
                "entity_name": entity_name,
                "entity_type": parts[2].strip() or "Other",
                "description": parts[3].strip(),
            })

        elif len(parts) >= 5 and "relation" in parts[0].lower():
            src = _normalize_name(parts[1])
            tgt = _normalize_name(parts[2])
            if not src or not tgt:
                continue
            relations.append({
                "source_entity": src,
                "target_entity": tgt,
                "keywords": parts[3].strip(),
                "description": parts[4].strip(),
                "weight": 1.0,
            })

    return {"entities": entities, "relations": relations}


def _normalize_name(name: str) -> str:
    """Strip quotes and whitespace, then title-case."""
    name = name.strip().strip("\"'`")
    if not name:
        return ""
    return name.title()


# ---------------------------------------------------------------------------
# Main extraction function
# ---------------------------------------------------------------------------

async def llm_extract_entities_and_relations(
    content: str,
    entity_types: list[str] | None = None,
    model: str = "gpt-4o-mini",
    max_gleaning: int = 1,
    language: str = "English",
) -> dict[str, list[dict[str, Any]]]:
    """Extract entities and relations from *content* using an LLM.

    Parameters
    ----------
    content:
        The source text to extract from.
    entity_types:
        Allowed entity type labels.  Defaults to a broad set.
    model:
        OpenAI-compatible model identifier.
    max_gleaning:
        Number of additional "continue extraction" rounds to catch missed
        items (0 = no gleaning, 1 = one extra pass, etc.).
    language:
        Output language for entity names and descriptions.

    Returns
    -------
    dict with keys ``entities`` and ``relations``, each a list of dicts.
    """
    if not content or not content.strip():
        return {"entities": [], "relations": []}

    if entity_types is None:
        entity_types = [
            "Person", "Organization", "Location", "Event", "Concept",
            "Method", "Content", "Data", "Artifact", "Technology",
        ]

    entity_types_str = ", ".join(entity_types)

    # Build system prompt
    system_prompt = ENTITY_EXTRACTION_SYSTEM_PROMPT.format(
        entity_types=entity_types_str,
        tuple_delimiter=TUPLE_DELIMITER,
        completion_delimiter=COMPLETION_DELIMITER,
        language=language,
    )

    # Build user prompt
    user_prompt = ENTITY_EXTRACTION_USER_PROMPT.format(
        entity_types=entity_types_str,
        input_text=content,
        completion_delimiter=COMPLETION_DELIMITER,
    )

    # Initial extraction
    raw = await _call_llm(user_prompt, model, system_prompt=system_prompt)

    if not raw:
        return {"entities": [], "relations": []}

    result = _parse_extraction_output(raw)

    # Gleaning passes
    for _ in range(max_gleaning):
        continue_prompt = ENTITY_CONTINUE_EXTRACTION_PROMPT.format(
            completion_delimiter=COMPLETION_DELIMITER,
            tuple_delimiter=TUPLE_DELIMITER,
        )
        raw_extra = await _call_llm(
            continue_prompt, model, system_prompt=system_prompt
        )
        if not raw_extra:
            break

        extra = _parse_extraction_output(raw_extra)

        # Merge new entities (skip duplicates by entity_id)
        existing_ids = {e["entity_id"] for e in result["entities"]}
        for ent in extra["entities"]:
            if ent["entity_id"] not in existing_ids:
                result["entities"].append(ent)
                existing_ids.add(ent["entity_id"])

        # Merge new relations (skip duplicates by src+tgt pair)
        existing_rels = {
            (r["source_entity"], r["target_entity"]) for r in result["relations"]
        }
        for rel in extra["relations"]:
            pair = (rel["source_entity"], rel["target_entity"])
            rev_pair = (rel["target_entity"], rel["source_entity"])
            if pair not in existing_rels and rev_pair not in existing_rels:
                result["relations"].append(rel)
                existing_rels.add(pair)

    return result
