from __future__ import annotations

import logging

from rrag_ingestion.components.graph_builders.base import BaseGraphBuilder
from rrag_ingestion.core.base import ComponentResult, register_component
from rrag_ingestion.models.document import SubGraph

logger = logging.getLogger(__name__)


@register_component
class LightRAGGraphBuilder(BaseGraphBuilder):
    """Graph builder that merges entities/relations, inspired by LightRAG's merge_nodes_and_edges."""

    name = "lightrag.graph_builder"
    version = "0.1.0"
    description = "Merges extracted entities and relations into a unified knowledge graph (from LightRAG)"
    config_schema = {
        "merge_strategy": {"type": "string", "default": "merge_descriptions", "enum": ["merge_descriptions", "keep_latest", "keep_longest"]},
        "dedup_threshold": {"type": "number", "default": 0.9, "description": "Similarity threshold for entity deduplication"},
    }

    async def invoke(self, input_data: ComponentResult, config: dict) -> ComponentResult:
        subgraph = input_data.data.get("subgraph")
        if not subgraph:
            return ComponentResult(data=input_data.data, errors=["No subgraph to build from"])

        merge_strategy = config.get("merge_strategy", "merge_descriptions")
        nodes = subgraph.nodes if hasattr(subgraph, "nodes") else subgraph.get("nodes", [])
        edges = subgraph.edges if hasattr(subgraph, "edges") else subgraph.get("edges", [])

        # Deduplicate entities by name (case-insensitive)
        merged_entities = {}
        for entity in nodes:
            name = entity.name if hasattr(entity, "name") else entity.get("name", "")
            key = name.lower().strip()
            if key in merged_entities:
                existing = merged_entities[key]
                # Merge source chunks
                new_chunks = entity.source_chunks if hasattr(entity, "source_chunks") else entity.get("source_chunks", [])
                existing_chunks = existing.source_chunks if hasattr(existing, "source_chunks") else existing.get("source_chunks", [])
                combined_chunks = list(set(existing_chunks + new_chunks))
                if hasattr(existing, "source_chunks"):
                    existing.source_chunks = combined_chunks

                # Merge descriptions
                new_desc = entity.description if hasattr(entity, "description") else entity.get("description", "")
                existing_desc = existing.description if hasattr(existing, "description") else existing.get("description", "")
                if merge_strategy == "merge_descriptions" and new_desc:
                    if hasattr(existing, "description"):
                        existing.description = f"{existing_desc} {new_desc}".strip()
                elif merge_strategy == "keep_longest" and len(new_desc) > len(existing_desc):
                    if hasattr(existing, "description"):
                        existing.description = new_desc
            else:
                merged_entities[key] = entity

        # Deduplicate edges
        merged_edges = {}
        for edge in edges:
            src = (edge.source_entity if hasattr(edge, "source_entity") else edge.get("source_entity", "")).lower()
            tgt = (edge.target_entity if hasattr(edge, "target_entity") else edge.get("target_entity", "")).lower()
            rel = (edge.relation_type if hasattr(edge, "relation_type") else edge.get("relation_type", "")).lower()
            key = (src, tgt, rel)
            if key not in merged_edges:
                merged_edges[key] = edge

        merged_subgraph = SubGraph(
            nodes=list(merged_entities.values()),
            edges=list(merged_edges.values()),
        )

        return ComponentResult(
            data={**input_data.data, "subgraph": merged_subgraph},
            metadata={
                "merged_entity_count": len(merged_subgraph.nodes),
                "merged_relation_count": len(merged_subgraph.edges),
                "dedup_entities_removed": len(nodes) - len(merged_subgraph.nodes),
                "dedup_relations_removed": len(edges) - len(merged_subgraph.edges),
            },
        )
