from __future__ import annotations

import logging

from rrag_ingestion.components.graph_builders.base import BaseGraphBuilder
from rrag_ingestion.core.base import ComponentResult, register_component
from rrag_ingestion.models.document import SubGraph

logger = logging.getLogger(__name__)


@register_component
class KAGSubGraphBuilder(BaseGraphBuilder):
    """Builds hierarchical subgraphs with concept layers, inspired by KAG's LLMFriSPG."""

    name = "kag.subgraph_builder"
    version = "0.1.0"
    description = "Hierarchical subgraph construction with concept taxonomy (from KAG)"
    config_schema = {
        "add_chunk_links": {"type": "boolean", "default": True, "description": "Add links between entities and source chunks"},
        "add_concept_layer": {"type": "boolean", "default": False, "description": "Generate concept hierarchy using LLM"},
    }

    async def invoke(self, input_data: ComponentResult, config: dict) -> ComponentResult:
        subgraph = input_data.data.get("subgraph")
        chunks = input_data.data.get("chunks", [])
        add_chunk_links = config.get("add_chunk_links", True)

        if not subgraph:
            return ComponentResult(data=input_data.data, errors=["No subgraph provided"])

        nodes = list(subgraph.nodes if hasattr(subgraph, "nodes") else subgraph.get("nodes", []))
        edges = list(subgraph.edges if hasattr(subgraph, "edges") else subgraph.get("edges", []))

        # Add mutual indexing: chunk -> entity bidirectional links
        if add_chunk_links and chunks:
            from rrag_ingestion.models.document import Relation
            import uuid
            chunk_map = {}
            for c in chunks:
                cid = c.id if hasattr(c, "id") else c.get("id", "")
                chunk_map[cid] = c

            for entity in nodes:
                src_chunks = entity.source_chunks if hasattr(entity, "source_chunks") else entity.get("source_chunks", [])
                ename = entity.name if hasattr(entity, "name") else entity.get("name", "")
                for chunk_id in src_chunks:
                    if chunk_id in chunk_map:
                        edges.append(Relation(
                            id=str(uuid.uuid4()),
                            source_entity=ename,
                            target_entity=f"chunk:{chunk_id}",
                            relation_type="mentioned_in",
                            description=f"{ename} is mentioned in chunk {chunk_id}",
                            source_chunks=[chunk_id],
                        ))

        result_subgraph = SubGraph(nodes=nodes, edges=edges)

        return ComponentResult(
            data={**input_data.data, "subgraph": result_subgraph},
            metadata={
                "node_count": len(nodes),
                "edge_count": len(edges),
            },
        )
