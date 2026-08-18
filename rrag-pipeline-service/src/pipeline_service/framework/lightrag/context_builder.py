"""Context assembly for RAG answer generation.

Ported from the context-building logic in ``LightRAG/lightrag/operate.py``
(functions ``kg_query`` / ``_build_query_context``).  Assembles entities,
relations, and chunks into a structured context string with a token budget.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import tiktoken

logger = logging.getLogger(__name__)


def _count_tokens(text: str, encoding_name: str = "cl100k_base") -> int:
    """Count tokens in *text* using tiktoken."""
    encoder = tiktoken.get_encoding(encoding_name)
    return len(encoder.encode(text))


def _truncate_list_to_budget(
    items: list[dict[str, Any]],
    key: str,
    max_tokens: int,
    encoding_name: str = "cl100k_base",
) -> list[dict[str, Any]]:
    """Keep as many items as fit within *max_tokens*.

    Items are evaluated in order; once the budget is exceeded the rest are
    dropped.
    """
    encoder = tiktoken.get_encoding(encoding_name)
    kept: list[dict[str, Any]] = []
    used = 0
    for item in items:
        text = item.get(key, "")
        tokens = len(encoder.encode(str(text)))
        if used + tokens > max_tokens:
            break
        kept.append(item)
        used += tokens
    return kept


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_context(
    mode: str,
    entities: list[dict[str, Any]],
    relations: list[dict[str, Any]],
    graph_chunks: list[dict[str, Any]],
    vector_chunks: list[dict[str, Any]],
    max_entity_tokens: int = 4000,
    max_relation_tokens: int = 4000,
    max_total_tokens: int = 12000,
) -> dict[str, Any]:
    """Assemble a context payload from graph and vector retrieval results.

    Parameters
    ----------
    mode:
        Retrieval mode (``"local"``, ``"global"``, ``"hybrid"``, ``"mix"``,
        ``"naive"``).  Controls which sections are included.
    entities:
        Entity dicts (from KG / vector search).
    relations:
        Relation dicts (from KG / vector search).
    graph_chunks:
        Text chunks retrieved via the knowledge graph path.
    vector_chunks:
        Text chunks retrieved via pure vector search.
    max_entity_tokens:
        Token budget for the entity section.
    max_relation_tokens:
        Token budget for the relation section.
    max_total_tokens:
        Hard cap on the total context token count.

    Returns
    -------
    dict with keys:
        * ``entities_context``  -- JSON string of truncated entities
        * ``relations_context`` -- JSON string of truncated relations
        * ``chunks_context``    -- JSON string of combined chunks
        * ``total_tokens``      -- approximate total token count
        * ``mode``              -- echo of the *mode* parameter
    """
    # --- Truncate entities and relations to their budgets ---
    trunc_entities = _truncate_list_to_budget(
        entities, "description", max_entity_tokens
    )
    trunc_relations = _truncate_list_to_budget(
        relations, "description", max_relation_tokens
    )

    # --- Build serialised sections ---
    entities_json = json.dumps(
        [_entity_for_context(e) for e in trunc_entities],
        ensure_ascii=False,
        indent=2,
    )
    relations_json = json.dumps(
        [_relation_for_context(r) for r in trunc_relations],
        ensure_ascii=False,
        indent=2,
    )

    # Combine graph and vector chunks, dedup by content hash
    seen_content: set[str] = set()
    combined_chunks: list[dict[str, Any]] = []
    for chunk in [*graph_chunks, *vector_chunks]:
        content = chunk.get("content", "")
        if content and content not in seen_content:
            seen_content.add(content)
            combined_chunks.append(chunk)

    # Determine remaining token budget for chunks
    used = _count_tokens(entities_json) + _count_tokens(relations_json)
    chunk_budget = max(max_total_tokens - used, 0)
    trunc_chunks = _truncate_list_to_budget(
        combined_chunks, "content", chunk_budget
    )

    chunks_json = json.dumps(
        [_chunk_for_context(c) for c in trunc_chunks],
        ensure_ascii=False,
        indent=2,
    )

    total = (
        _count_tokens(entities_json)
        + _count_tokens(relations_json)
        + _count_tokens(chunks_json)
    )

    # Build the combined "assembled" text for direct LLM consumption
    sections: list[str] = []
    if entities_json and entities_json != "[]":
        sections.append(f"## Entities\n{entities_json}")
    if relations_json and relations_json != "[]":
        sections.append(f"## Relations\n{relations_json}")
    if chunks_json and chunks_json != "[]":
        sections.append(f"## Text Chunks\n{chunks_json}")
    assembled = "\n\n".join(sections)

    return {
        "assembled": assembled,
        "entities_context": entities_json,
        "relations_context": relations_json,
        "chunks_context": chunks_json,
        "chunks_used": trunc_chunks,
        "total_tokens": total,
        "mode": mode,
        "entity_count": len(trunc_entities),
        "relation_count": len(trunc_relations),
        "chunk_count": len(trunc_chunks),
    }


# ---------------------------------------------------------------------------
# Serialisation helpers (keep context payloads lean)
# ---------------------------------------------------------------------------


def _entity_for_context(e: dict[str, Any]) -> dict[str, str]:
    return {
        "entity_name": e.get("entity_name", ""),
        "entity_type": e.get("entity_type", ""),
        "description": e.get("description", ""),
    }


def _relation_for_context(r: dict[str, Any]) -> dict[str, str]:
    return {
        "source": r.get("source_entity", ""),
        "target": r.get("target_entity", ""),
        "keywords": r.get("keywords", ""),
        "description": r.get("description", ""),
    }


def _chunk_for_context(c: dict[str, Any]) -> dict[str, str]:
    return {
        "content": c.get("content", ""),
        "doc_id": c.get("full_doc_id", ""),
        "index": str(c.get("chunk_order_index", 0)),
    }
