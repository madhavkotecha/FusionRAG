"""Workspace-scoped Neo4j operations for knowledge-graph storage.

Every function takes a ``scope`` string (e.g. ``ws_abc_ds_1``) that is used as
a Neo4j node label so that different workspaces/datastores are fully isolated
inside the same database.  The pattern follows the upstream LightRAG
``Neo4JStorage`` implementation but is expressed as stateless async helpers
rather than a stateful class.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from neo4j import AsyncGraphDatabase, AsyncDriver

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Driver singleton
# ---------------------------------------------------------------------------

_driver: AsyncDriver | None = None


async def get_neo4j_driver() -> AsyncDriver:
    """Return (and lazily create) a shared async Neo4j driver."""
    global _driver
    if _driver is None:
        uri = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "password")
        _driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    return _driver


async def close_neo4j_driver() -> None:
    """Close the shared driver (useful for graceful shutdown)."""
    global _driver
    if _driver is not None:
        await _driver.close()
        _driver = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _entity_label(scope: str) -> str:
    """Return the scoped node label for entities, e.g. ``ws_abc_Entity``."""
    return f"{scope}_Entity"


def _database() -> str | None:
    """Return the configured Neo4j database name, or *None* for the default."""
    db = os.getenv("NEO4J_DATABASE")
    return db if db else None


# ---------------------------------------------------------------------------
# Entity operations
# ---------------------------------------------------------------------------

async def neo4j_upsert_entities(scope: str, entities: list[dict[str, Any]]) -> int:
    """Upsert entity nodes with a scoped label.

    Each entity dict is expected to have at least:
    * ``entity_id``   -- unique identifier (also used for MERGE)
    * ``entity_name`` -- human-readable name
    * ``entity_type`` -- category/label
    * ``description`` -- textual description

    Returns the number of entities processed.
    """
    if not entities:
        return 0

    driver = await get_neo4j_driver()
    label = _entity_label(scope)
    db = _database()
    count = 0

    async with driver.session(database=db) as session:
        for entity in entities:
            entity_id = entity.get("entity_id") or entity.get("entity_name", "")
            if not entity_id:
                continue

            props = {k: v for k, v in entity.items() if v is not None}
            props.setdefault("entity_id", entity_id)

            entity_type = props.pop("entity_type", "Entity")

            query = (
                f"MERGE (n:`{label}` {{entity_id: $entity_id}}) "
                f"SET n += $props "
                f"SET n:`{entity_type}`"
            )

            async def _write(tx, eid=entity_id, p=props, q=query):
                result = await tx.run(q, entity_id=eid, props=p)
                await result.consume()

            try:
                await session.execute_write(_write)
                count += 1
            except Exception:
                logger.exception(
                    "[%s] Failed to upsert entity %s", scope, entity_id
                )

    return count


async def neo4j_upsert_relations(
    scope: str, relations: list[dict[str, Any]]
) -> int:
    """Upsert relationship edges between scoped entity nodes.

    Each relation dict is expected to have at least:
    * ``source_entity`` -- entity_id of the source node
    * ``target_entity`` -- entity_id of the target node
    * ``keywords``      -- comma-separated relationship keywords
    * ``description``   -- textual description

    Returns the number of relations processed.
    """
    if not relations:
        return 0

    driver = await get_neo4j_driver()
    label = _entity_label(scope)
    db = _database()
    count = 0

    async with driver.session(database=db) as session:
        for rel in relations:
            src = rel.get("source_entity", "")
            tgt = rel.get("target_entity", "")
            if not src or not tgt:
                continue

            props = {
                k: v
                for k, v in rel.items()
                if k not in ("source_entity", "target_entity") and v is not None
            }

            query = (
                f"MATCH (source:`{label}` {{entity_id: $src}}) "
                f"WITH source "
                f"MATCH (target:`{label}` {{entity_id: $tgt}}) "
                f"MERGE (source)-[r:RELATED]-(target) "
                f"SET r += $props "
                f"RETURN r"
            )

            async def _write(tx, s=src, t=tgt, p=props, q=query):
                result = await tx.run(q, src=s, tgt=t, props=p)
                await result.consume()

            try:
                await session.execute_write(_write)
                count += 1
            except Exception:
                logger.exception(
                    "[%s] Failed to upsert relation %s -> %s", scope, src, tgt
                )

    return count


# ---------------------------------------------------------------------------
# Enrichment (read-path)
# ---------------------------------------------------------------------------

async def neo4j_enrich_entities(
    scope: str, entities: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Fetch full node details and neighbor information from Neo4j.

    For each entity in *entities* (matched by ``entity_id``), the returned
    dict is augmented with all stored properties and a ``neighbors`` key that
    lists directly connected entity_ids.
    """
    if not entities:
        return []

    driver = await get_neo4j_driver()
    label = _entity_label(scope)
    db = _database()
    enriched: list[dict[str, Any]] = []

    async with driver.session(database=db) as session:
        for entity in entities:
            eid = entity.get("entity_id") or entity.get("entity_name", "")
            if not eid:
                enriched.append(entity)
                continue

            query = (
                f"MATCH (n:`{label}` {{entity_id: $eid}}) "
                f"OPTIONAL MATCH (n)-[r]-(m:`{label}`) "
                f"RETURN n, collect(DISTINCT m.entity_id) AS neighbors, "
                f"collect(DISTINCT properties(r)) AS rel_props"
            )

            try:
                result = await session.run(query, eid=eid)
                record = await result.single()
                await result.consume()

                if record and record["n"]:
                    node_props = dict(record["n"])
                    merged = {**entity, **node_props}
                    merged["neighbors"] = record["neighbors"] or []
                    merged["relation_properties"] = record["rel_props"] or []
                    enriched.append(merged)
                else:
                    enriched.append(entity)
            except Exception:
                logger.exception(
                    "[%s] Failed to enrich entity %s", scope, eid
                )
                enriched.append(entity)

    return enriched


async def neo4j_enrich_relations(
    scope: str, relations: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Fetch full edge details from Neo4j for each relation.

    Each relation is matched by ``source_entity`` and ``target_entity`` and
    augmented with the stored edge properties.
    """
    if not relations:
        return []

    driver = await get_neo4j_driver()
    label = _entity_label(scope)
    db = _database()
    enriched: list[dict[str, Any]] = []

    async with driver.session(database=db) as session:
        for rel in relations:
            src = rel.get("source_entity", "")
            tgt = rel.get("target_entity", "")
            if not src or not tgt:
                enriched.append(rel)
                continue

            query = (
                f"MATCH (a:`{label}` {{entity_id: $src}})"
                f"-[r]-(b:`{label}` {{entity_id: $tgt}}) "
                f"RETURN properties(r) AS props, "
                f"properties(a) AS src_props, properties(b) AS tgt_props "
                f"LIMIT 1"
            )

            try:
                result = await session.run(query, src=src, tgt=tgt)
                record = await result.single()
                await result.consume()

                if record and record["props"]:
                    merged = {**rel, **record["props"]}
                    merged["source_properties"] = record["src_props"] or {}
                    merged["target_properties"] = record["tgt_props"] or {}
                    enriched.append(merged)
                else:
                    enriched.append(rel)
            except Exception:
                logger.exception(
                    "[%s] Failed to enrich relation %s -> %s",
                    scope, src, tgt,
                )
                enriched.append(rel)

    return enriched
