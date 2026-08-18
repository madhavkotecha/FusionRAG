from __future__ import annotations

import logging
import os
import re

from rrag_ingestion.components.storage.base import BaseStorage
from rrag_ingestion.core.base import ComponentResult, register_component

logger = logging.getLogger(__name__)

# Cypher identifiers only allow letters, digits, and underscores
_CYPHER_IDENT_RE = re.compile(r"[^A-Za-z0-9_]")


@register_component
class Neo4jGraphStore(BaseStorage):
    """Neo4j graph storage from LightRAG."""

    name = "lightrag.neo4j_graph"
    version = "0.1.0"
    description = "Neo4j graph database for knowledge graph storage (from LightRAG)"
    config_schema = {
        "uri": {"type": "string", "default": "bolt://localhost:7687"},
        "username": {"type": "string", "default": "neo4j"},
        "password": {"type": "string", "default": "password"},
        "database": {"type": "string", "default": "neo4j"},
    }

    async def invoke(self, input_data: ComponentResult, config: dict) -> ComponentResult:
        subgraph = input_data.data.get("subgraph")
        if not subgraph:
            return ComponentResult(data=input_data.data, metadata={"stored_nodes": 0, "stored_edges": 0})

        uri = config.get("uri") or os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        username = config.get("username") or os.environ.get("NEO4J_USERNAME", "neo4j")
        password = config.get("password") or os.environ["NEO4J_PASSWORD"]
        database = config.get("database") or os.environ.get("NEO4J_DATABASE", "neo4j")

        nodes = subgraph.nodes if hasattr(subgraph, "nodes") else subgraph.get("nodes", [])
        edges = subgraph.edges if hasattr(subgraph, "edges") else subgraph.get("edges", [])

        # Per-datastore isolation: scope all graph data to a datastore_id
        datastore_id = input_data.data.get("datastore_id", "")

        try:
            from neo4j import AsyncGraphDatabase

            driver = AsyncGraphDatabase.driver(uri, auth=(username, password))

            async with driver.session(database=database) as session:
                # Upsert nodes (scoped by datastore_id)
                for ni, node in enumerate(nodes):
                    name = node.name if hasattr(node, "name") else node.get("name", "")
                    etype = node.entity_type if hasattr(node, "entity_type") else node.get("entity_type", "Entity")
                    desc = node.description if hasattr(node, "description") else node.get("description", "")
                    props = node.properties if hasattr(node, "properties") else node.get("properties", {})

                    # Sanitize label for Cypher (letters, digits, underscores only)
                    etype = _CYPHER_IDENT_RE.sub("_", etype).strip("_") or "Entity"

                    self.report_progress(f"Storing node {ni + 1}/{len(nodes)}", items_done=ni, items_total=len(nodes) + len(edges))

                    if datastore_id:
                        await session.run(
                            f"MERGE (n:`{etype}` {{name: $name, datastore_id: $ds_id}}) "
                            "SET n.description = $description, n += $props",
                            name=name, ds_id=datastore_id, description=desc, props=props,
                        )
                    else:
                        await session.run(
                            f"MERGE (n:`{etype}` {{name: $name}}) "
                            "SET n.description = $description, n += $props",
                            name=name, description=desc, props=props,
                        )

                # Upsert edges (scoped by datastore_id)
                for ei, edge in enumerate(edges):
                    src = edge.source_entity if hasattr(edge, "source_entity") else edge.get("source_entity", "")
                    tgt = edge.target_entity if hasattr(edge, "target_entity") else edge.get("target_entity", "")
                    rel_type = (edge.relation_type if hasattr(edge, "relation_type") else edge.get("relation_type", "RELATED_TO")).upper().replace(" ", "_")
                    desc = edge.description if hasattr(edge, "description") else edge.get("description", "")

                    # Sanitize relation type for Cypher
                    rel_type = _CYPHER_IDENT_RE.sub("_", rel_type).strip("_") or "RELATED_TO"

                    self.report_progress(
                        f"Storing edge {ei + 1}/{len(edges)}",
                        items_done=len(nodes) + ei,
                        items_total=len(nodes) + len(edges),
                    )

                    if datastore_id:
                        await session.run(
                            f"MATCH (a {{name: $src, datastore_id: $ds_id}}), (b {{name: $tgt, datastore_id: $ds_id}}) "
                            f"MERGE (a)-[r:`{rel_type}`]->(b) "
                            "SET r.description = $desc, r.datastore_id = $ds_id",
                            src=src, tgt=tgt, desc=desc, ds_id=datastore_id,
                        )
                    else:
                        await session.run(
                            f"MATCH (a {{name: $src}}), (b {{name: $tgt}}) "
                            f"MERGE (a)-[r:`{rel_type}`]->(b) "
                            "SET r.description = $desc",
                            src=src, tgt=tgt, desc=desc,
                        )

            await driver.close()

            return ComponentResult(
                data=input_data.data,
                metadata={"stored_nodes": len(nodes), "stored_edges": len(edges), "store": "neo4j", "uri": uri},
            )

        except ImportError:
            return ComponentResult(data=input_data.data, errors=["neo4j driver not installed. Install with: pip install neo4j"])
        except Exception as e:
            return ComponentResult(data=input_data.data, errors=[f"Neo4j storage failed: {e}"])
