"""Compile a visual query pipeline definition into a flat QueryPipeline config.

When a query pipeline is saved in the visual editor (nodes/edges), this module
extracts the component configs and produces the flat dict that rrag-ingestion's
query executor understands.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Map specific component types to retrieval_strategy values
_RETRIEVER_STRATEGY_MAP = {
    "dense_retriever": "dense",
    "hybrid_retriever": "hybrid",
    "graph_retriever": "graph",
    "web_retriever": "web",
}


def _find_nodes_by_category(nodes: list[dict], category: str) -> list[dict]:
    """Find all nodes of a given category."""
    return [
        n for n in nodes
        if n.get("data", {}).get("category") == category
    ]


def _extract_node_config(node: dict) -> dict[str, Any]:
    """Extract the config dict from a pipeline node."""
    return node.get("data", {}).get("config", {})


def _infer_retrieval_strategy(retriever_nodes: list[dict]) -> str:
    """Infer the retrieval_strategy from retriever node types."""
    if not retriever_nodes:
        return "auto"

    types = {n.get("data", {}).get("componentType", "") for n in retriever_nodes}

    # If multiple retrievers, it's hybrid
    if len(types) > 1:
        return "hybrid"

    component_type = next(iter(types))
    return _RETRIEVER_STRATEGY_MAP.get(component_type, "auto")


def compile_query_pipeline(
    pipeline_id: str,
    name: str,
    description: str | None,
    datastore_id: str | None,
    definition: dict,
) -> dict[str, Any]:
    """Convert a visual pipeline definition (nodes/edges) into a flat QueryPipeline config.

    Args:
        pipeline_id: The pipeline ID (used as the query pipeline ID).
        name: Pipeline name.
        description: Pipeline description.
        datastore_id: The datastore to bind to.
        definition: The visual definition with nodes and edges.

    Returns:
        A dict matching the CreateQueryPipelineRequest schema in rrag-ingestion.
    """
    nodes = definition.get("nodes", [])

    # Find nodes by category
    retriever_nodes = _find_nodes_by_category(nodes, "retriever")
    reranker_nodes = _find_nodes_by_category(nodes, "reranker")
    generator_nodes = _find_nodes_by_category(nodes, "generator")
    planner_nodes = _find_nodes_by_category(nodes, "planner")
    agent_nodes = _find_nodes_by_category(nodes, "agent")

    compiled: dict[str, Any] = {
        "name": name,
        "description": description or "",
        "datastore_id": datastore_id or "",
        "retrieval_strategy": _infer_retrieval_strategy(retriever_nodes),
        "definition": definition,
    }

    # Merge configs from first node of each category (primary node)
    if retriever_nodes:
        config = _extract_node_config(retriever_nodes[0])
        compiled["retriever"] = {
            "strategy": _RETRIEVER_STRATEGY_MAP.get(
                retriever_nodes[0].get("data", {}).get("componentType", ""),
                "dense",
            ),
            **config,
        }

    if reranker_nodes:
        config = _extract_node_config(reranker_nodes[0])
        compiled["reranker"] = {
            "enabled": True,
            "strategy": _infer_reranker_strategy(reranker_nodes[0]),
            **config,
        }

    if generator_nodes:
        config = _extract_node_config(generator_nodes[0])
        compiled["generator"] = config

    if planner_nodes:
        config = _extract_node_config(planner_nodes[0])
        compiled["planner"] = {
            "enabled": True,
            "strategy": _infer_planner_strategy(planner_nodes[0]),
            **config,
        }

    if agent_nodes:
        config = _extract_node_config(agent_nodes[0])
        compiled["agent"] = {
            "enabled": True,
            "agent_type": _infer_agent_type(agent_nodes[0]),
            **config,
        }

    return compiled


def _infer_reranker_strategy(node: dict) -> str:
    """Infer reranker strategy from component type."""
    comp_type = node.get("data", {}).get("componentType", "")
    mapping = {
        "cross_encoder_reranker": "cross_encoder",
        "cohere_reranker": "cohere",
        "jina_reranker": "jina",
        "llm_listwise_reranker": "llm_listwise",
    }
    return mapping.get(comp_type, "cross_encoder")


def _infer_planner_strategy(node: dict) -> str:
    """Infer planner strategy from component type."""
    comp_type = node.get("data", {}).get("componentType", "")
    mapping = {
        "corag_planner": "corag",
        "mcts_planner": "mcts",
        "kag_planner": "plan_and_execute",
    }
    return mapping.get(comp_type, "corag")


def _infer_agent_type(node: dict) -> str:
    """Infer agent type from component type."""
    comp_type = node.get("data", {}).get("componentType", "")
    mapping = {
        "orchestrator_agent": "orchestrator",
        "query_router": "router",
        "reflection_agent": "reflection",
        "memory_agent": "memory",
        "tool_use_agent": "orchestrator",
    }
    return mapping.get(comp_type, "router")
