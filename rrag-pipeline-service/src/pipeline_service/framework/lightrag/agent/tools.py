"""Agent tool definitions for Agentic RAG retrieval.

Each tool corresponds to a specific retrieval operation against the storage
layer.  The planner selects which tools to use; the tool executor dispatches
them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolDef:
    """Immutable definition of a retrieval tool."""

    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolCall:
    """A specific invocation of a tool with arguments."""

    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    """The result produced by executing a :class:`ToolCall`."""

    tool_name: str
    data: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.error is None


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

GRAPH_ENTITY_SEARCH = ToolDef(
    name="graph_entity_search",
    description=(
        "Search for entity nodes in the knowledge graph by semantic "
        "similarity to a text query.  Returns entity names, types, "
        "descriptions, and neighbor information."
    ),
    parameters={
        "query": {"type": "string", "description": "Search text"},
        "top_k": {"type": "integer", "default": 10},
    },
)

GRAPH_RELATION_SEARCH = ToolDef(
    name="graph_relation_search",
    description=(
        "Search for relationship edges in the knowledge graph by "
        "semantic similarity.  Returns source/target entities, keywords, "
        "and descriptions."
    ),
    parameters={
        "query": {"type": "string", "description": "Search text"},
        "top_k": {"type": "integer", "default": 10},
    },
)

GRAPH_TRAVERSE = ToolDef(
    name="graph_traverse",
    description=(
        "Starting from a named entity, traverse its neighbors in the "
        "knowledge graph up to a given depth.  Returns connected entities "
        "and their relationships."
    ),
    parameters={
        "entity_id": {"type": "string", "description": "Starting entity ID"},
        "depth": {"type": "integer", "default": 1},
        "max_nodes": {"type": "integer", "default": 20},
    },
)

VECTOR_CHUNK_SEARCH = ToolDef(
    name="vector_chunk_search",
    description=(
        "Search for text chunks by vector similarity.  Returns the most "
        "relevant document passages."
    ),
    parameters={
        "query": {"type": "string", "description": "Search text"},
        "top_k": {"type": "integer", "default": 10},
    },
)

VECTOR_ENTITY_SEARCH = ToolDef(
    name="vector_entity_search",
    description=(
        "Search for entities in the vector store by description similarity. "
        "Lighter weight than graph_entity_search (no Neo4j enrichment)."
    ),
    parameters={
        "query": {"type": "string", "description": "Search text"},
        "top_k": {"type": "integer", "default": 10},
    },
)

TOOL_REGISTRY: dict[str, ToolDef] = {
    t.name: t
    for t in [
        GRAPH_ENTITY_SEARCH,
        GRAPH_RELATION_SEARCH,
        GRAPH_TRAVERSE,
        VECTOR_CHUNK_SEARCH,
        VECTOR_ENTITY_SEARCH,
    ]
}
