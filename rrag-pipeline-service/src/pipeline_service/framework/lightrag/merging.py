"""Entity and relation merging / deduplication.

Ported from ``LightRAG/lightrag/operate.py::merge_nodes_and_edges``.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Entity merging (embedding-based similarity)
# ---------------------------------------------------------------------------


async def merge_entities_by_similarity(
    entities: list[dict[str, Any]],
    threshold: float = 0.85,
    embedding_model: str = "text-embedding-3-small",
) -> list[dict[str, Any]]:
    """Merge duplicate entities using embedding cosine similarity.

    Entities whose description embeddings have cosine similarity above
    *threshold* are merged into a single entity.  The merge keeps the entity
    with the longest description and concatenates unique descriptions.

    Parameters
    ----------
    entities:
        List of entity dicts with at least ``entity_id``, ``entity_name``,
        and ``description``.
    threshold:
        Cosine similarity threshold above which two entities are considered
        duplicates.
    embedding_model:
        Model identifier for embedding computation.

    Returns
    -------
    Deduplicated list of entity dicts.
    """
    if len(entities) <= 1:
        return list(entities)

    # Group by normalised name first (exact-match pass)
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for ent in entities:
        key = ent.get("entity_name", ent.get("entity_id", "")).strip().lower()
        groups[key].append(ent)

    merged: list[dict[str, Any]] = []

    for _key, group in groups.items():
        if len(group) == 1:
            merged.append(group[0])
            continue

        # Merge group: keep the richest description, aggregate types
        representative = max(group, key=lambda e: len(e.get("description", "")))
        descriptions = list({e.get("description", "") for e in group if e.get("description")})
        entity_types = list({e.get("entity_type", "Other") for e in group})

        representative["description"] = " | ".join(descriptions)
        if len(entity_types) == 1:
            representative["entity_type"] = entity_types[0]
        else:
            representative["entity_type"] = entity_types[0]

        merged.append(representative)

    # --- Cross-group fuzzy pass via embeddings (when API is available) ---
    if len(merged) <= 1:
        return merged

    try:
        from .storage.qdrant_ops import _get_embeddings_batch
        import os

        if not os.getenv("OPENAI_API_KEY"):
            return merged

        texts = [e.get("description", e.get("entity_name", "")) for e in merged]
        embeddings = await _get_embeddings_batch(texts, embedding_model)

        # Simple pairwise cosine similarity
        import math

        def _cosine(a: list[float], b: list[float]) -> float:
            dot = sum(x * y for x, y in zip(a, b))
            na = math.sqrt(sum(x * x for x in a))
            nb = math.sqrt(sum(x * x for x in b))
            if na == 0 or nb == 0:
                return 0.0
            return dot / (na * nb)

        # Union-find for transitive merging
        parent = list(range(len(merged)))

        def find(i: int) -> int:
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        def union(i: int, j: int) -> None:
            ri, rj = find(i), find(j)
            if ri != rj:
                parent[ri] = rj

        for i in range(len(merged)):
            for j in range(i + 1, len(merged)):
                if _cosine(embeddings[i], embeddings[j]) >= threshold:
                    union(i, j)

        # Group by root
        root_groups: dict[int, list[int]] = defaultdict(list)
        for i in range(len(merged)):
            root_groups[find(i)].append(i)

        final: list[dict[str, Any]] = []
        for indices in root_groups.values():
            if len(indices) == 1:
                final.append(merged[indices[0]])
            else:
                best = max(indices, key=lambda i: len(merged[i].get("description", "")))
                rep = dict(merged[best])
                descs = list({merged[i].get("description", "") for i in indices if merged[i].get("description")})
                rep["description"] = " | ".join(descs)
                final.append(rep)

        return final

    except Exception:
        logger.debug("Embedding-based merge skipped (no API key or import error)")
        return merged


# ---------------------------------------------------------------------------
# Relation merging (deterministic, no LLM)
# ---------------------------------------------------------------------------


def merge_relations(relations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge duplicate relations that share the same source and target.

    Duplicate relations are detected by (source_entity, target_entity) pair
    (order-insensitive).  When merged the keywords are unioned and weights
    summed.

    Returns a deduplicated list of relation dicts.
    """
    if len(relations) <= 1:
        return list(relations)

    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for rel in relations:
        src = rel.get("source_entity", "").strip().lower()
        tgt = rel.get("target_entity", "").strip().lower()
        key = tuple(sorted([src, tgt]))
        groups[key].append(rel)

    merged: list[dict[str, Any]] = []
    for _key, group in groups.items():
        if len(group) == 1:
            merged.append(group[0])
            continue

        # Take the richest description as representative
        representative = dict(max(group, key=lambda r: len(r.get("description", ""))))

        # Union keywords
        all_keywords: set[str] = set()
        for r in group:
            kw = r.get("keywords", "")
            for k in kw.split(","):
                k = k.strip()
                if k:
                    all_keywords.add(k)
        representative["keywords"] = ", ".join(sorted(all_keywords))

        # Aggregate descriptions
        descriptions = list({r.get("description", "") for r in group if r.get("description")})
        representative["description"] = " | ".join(descriptions)

        # Sum weights
        total_weight = sum(r.get("weight", 1.0) for r in group)
        representative["weight"] = total_weight

        merged.append(representative)

    return merged
