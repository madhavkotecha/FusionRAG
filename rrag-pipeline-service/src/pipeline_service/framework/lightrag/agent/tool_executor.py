"""Tool executor -- dispatches :class:`ToolCall` objects to storage operations.

The executor is the bridge between the agent planner (which outputs abstract
tool calls) and the concrete storage layer (Neo4j, Qdrant, Redis).
"""

from __future__ import annotations

import logging
from typing import Any

from .tools import ToolCall, ToolResult

logger = logging.getLogger(__name__)


async def execute_tool(
    call: ToolCall,
    scope: str,
    embedding_model: str = "text-embedding-3-small",
) -> ToolResult:
    """Execute a single tool call and return the result.

    Parameters
    ----------
    call:
        The tool invocation (name + arguments).
    scope:
        Workspace scope key forwarded to every storage operation.
    embedding_model:
        Model identifier for any embedding calls required by the tool.
    """
    try:
        handler = _DISPATCH.get(call.tool_name)
        if handler is None:
            return ToolResult(
                tool_name=call.tool_name,
                error=f"Unknown tool: {call.tool_name}",
            )
        data = await handler(scope=scope, embedding_model=embedding_model, **call.arguments)
        return ToolResult(tool_name=call.tool_name, data=data)
    except Exception as exc:
        logger.exception("Tool execution failed: %s", call.tool_name)
        return ToolResult(tool_name=call.tool_name, error=str(exc))


# ---------------------------------------------------------------------------
# Handler implementations
# ---------------------------------------------------------------------------

async def _graph_entity_search(
    scope: str, query: str, top_k: int = 10, embedding_model: str = "text-embedding-3-small", **_: Any
) -> list[dict[str, Any]]:
    from ..storage.qdrant_ops import qdrant_search_entities
    from ..storage.neo4j_ops import neo4j_enrich_entities

    entities = await qdrant_search_entities(scope, query, top_k, embedding_model)
    return await neo4j_enrich_entities(scope, entities)


async def _graph_relation_search(
    scope: str, query: str, top_k: int = 10, embedding_model: str = "text-embedding-3-small", **_: Any
) -> list[dict[str, Any]]:
    from ..storage.qdrant_ops import qdrant_search_relations
    from ..storage.neo4j_ops import neo4j_enrich_relations

    relations = await qdrant_search_relations(scope, query, top_k, embedding_model)
    return await neo4j_enrich_relations(scope, relations)


async def _graph_traverse(
    scope: str, entity_id: str, depth: int = 1, max_nodes: int = 20, **_: Any
) -> list[dict[str, Any]]:
    """Traverse neighbours of *entity_id* up to *depth* hops.

    This issues a variable-length path query to Neo4j and returns the
    resulting nodes and edges.
    """
    from ..storage.neo4j_ops import get_neo4j_driver, _entity_label, _database

    driver = await get_neo4j_driver()
    label = _entity_label(scope)
    db = _database()

    query = (
        f"MATCH path = (start:`{label}` {{entity_id: $eid}})"
        f"-[*1..{depth}]-(neighbor:`{label}`) "
        f"UNWIND nodes(path) AS n "
        f"WITH DISTINCT n LIMIT $max_nodes "
        f"RETURN n.entity_id AS entity_id, n.entity_name AS entity_name, "
        f"n.entity_type AS entity_type, n.description AS description"
    )

    results: list[dict[str, Any]] = []
    async with driver.session(database=db) as session:
        cursor = await session.run(query, eid=entity_id, max_nodes=max_nodes)
        records = await cursor.data()
        await cursor.consume()
        for rec in records:
            results.append({
                "entity_id": rec.get("entity_id", ""),
                "entity_name": rec.get("entity_name", ""),
                "entity_type": rec.get("entity_type", ""),
                "description": rec.get("description", ""),
            })

    return results


async def _vector_chunk_search(
    scope: str, query: str, top_k: int = 10, embedding_model: str = "text-embedding-3-small", **_: Any
) -> list[dict[str, Any]]:
    from ..storage.qdrant_ops import qdrant_search_chunks
    return await qdrant_search_chunks(scope, query, top_k, embedding_model)


async def _vector_entity_search(
    scope: str, query: str, top_k: int = 10, embedding_model: str = "text-embedding-3-small", **_: Any
) -> list[dict[str, Any]]:
    from ..storage.qdrant_ops import qdrant_search_entities
    return await qdrant_search_entities(scope, query, top_k, embedding_model)


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_DISPATCH = {
    "graph_entity_search": _graph_entity_search,
    "graph_relation_search": _graph_relation_search,
    "graph_traverse": _graph_traverse,
    "vector_chunk_search": _vector_chunk_search,
    "vector_entity_search": _vector_entity_search,
}
