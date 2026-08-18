from __future__ import annotations

import logging

from rrag_ingestion.components.retrievers.base import BaseRetriever
from rrag_ingestion.core.base import ComponentResult, register_component
from rrag_ingestion.models.document import RetrievalResult

logger = logging.getLogger(__name__)


@register_component
class LightRAGKGRetriever(BaseRetriever):
    """Knowledge graph retriever with local/global/hybrid/mix modes from LightRAG."""

    name = "lightrag.kg_retriever"
    version = "0.1.0"
    description = "KG-enhanced retrieval with local, global, hybrid, and mix modes (from LightRAG)"
    config_schema = {
        "mode": {"type": "string", "default": "hybrid", "enum": ["local", "global", "hybrid", "mix", "naive"]},
        "top_k": {"type": "integer", "default": 40},
        "neo4j_uri": {"type": "string", "default": "bolt://localhost:7687"},
        "neo4j_username": {"type": "string", "default": "neo4j"},
        "neo4j_password": {"type": "string", "default": "password"},
    }

    async def invoke(self, input_data: ComponentResult, config: dict) -> ComponentResult:
        query = input_data.data.get("query", "")
        if not query:
            return ComponentResult(data=input_data.data, errors=["No query provided for retrieval"])

        mode = config.get("mode", "hybrid")
        top_k = config.get("top_k", 40)

        try:
            results = []

            if mode in ("local", "hybrid", "mix"):
                local_results = await self._local_retrieval(query, config, top_k)
                results.extend(local_results)

            if mode in ("global", "hybrid", "mix"):
                global_results = await self._global_retrieval(query, config, top_k)
                results.extend(global_results)

            if mode == "naive":
                naive_results = await self._naive_retrieval(query, config, top_k)
                results.extend(naive_results)

            # Deduplicate and sort by score
            seen = set()
            unique_results = []
            for r in sorted(results, key=lambda x: x.score, reverse=True):
                if r.id not in seen:
                    seen.add(r.id)
                    unique_results.append(r)

            return ComponentResult(
                data={**input_data.data, "retrieved": unique_results[:top_k]},
                metadata={"mode": mode, "result_count": len(unique_results[:top_k])},
            )

        except Exception as e:
            return ComponentResult(data=input_data.data, errors=[f"KG retrieval failed: {e}"])

    async def _local_retrieval(self, query: str, config: dict, top_k: int) -> list[RetrievalResult]:
        """Entity-centric local retrieval via graph traversal."""
        try:
            from neo4j import AsyncGraphDatabase

            uri = config.get("neo4j_uri", "bolt://localhost:7687")
            driver = AsyncGraphDatabase.driver(
                uri, auth=(config.get("neo4j_username", "neo4j"), config.get("neo4j_password", "password"))
            )

            results = []
            async with driver.session() as session:
                # Search for entities matching the query
                records = await session.run(
                    "MATCH (n) WHERE toLower(n.name) CONTAINS toLower($query) "
                    "OR toLower(n.description) CONTAINS toLower($query) "
                    "OPTIONAL MATCH (n)-[r]-(m) "
                    "RETURN n.name AS entity, n.description AS desc, "
                    "collect(DISTINCT {target: m.name, rel: type(r), desc: r.description}) AS relations "
                    "LIMIT $limit",
                    query=query, limit=top_k,
                )
                async for record in records:
                    context = f"Entity: {record['entity']}\nDescription: {record['desc'] or ''}\n"
                    for rel in record["relations"]:
                        if rel["target"]:
                            context += f"  - {rel['rel']}: {rel['target']} ({rel.get('desc', '')})\n"

                    results.append(RetrievalResult(
                        id=record["entity"],
                        content=context,
                        score=1.0,
                        metadata={"source": "kg_local"},
                    ))

            await driver.close()
            return results

        except Exception as e:
            logger.warning(f"Local KG retrieval failed: {e}")
            return []

    async def _global_retrieval(self, query: str, config: dict, top_k: int) -> list[RetrievalResult]:
        """Community-level global retrieval."""
        try:
            from neo4j import AsyncGraphDatabase

            uri = config.get("neo4j_uri", "bolt://localhost:7687")
            driver = AsyncGraphDatabase.driver(
                uri, auth=(config.get("neo4j_username", "neo4j"), config.get("neo4j_password", "password"))
            )

            results = []
            async with driver.session() as session:
                records = await session.run(
                    "MATCH (n)-[r]-(m) "
                    "WITH n, count(r) AS degree "
                    "ORDER BY degree DESC LIMIT $limit "
                    "MATCH (n)-[r]-(m) "
                    "RETURN n.name AS hub, n.description AS desc, "
                    "collect(DISTINCT {target: m.name, rel: type(r)}) AS connections",
                    limit=top_k,
                )
                async for record in records:
                    context = f"Hub entity: {record['hub']}\nDescription: {record['desc'] or ''}\n"
                    for conn in record["connections"][:10]:
                        context += f"  - {conn['rel']}: {conn['target']}\n"

                    results.append(RetrievalResult(
                        id=record["hub"],
                        content=context,
                        score=0.8,
                        metadata={"source": "kg_global"},
                    ))

            await driver.close()
            return results

        except Exception as e:
            logger.warning(f"Global KG retrieval failed: {e}")
            return []

    async def _naive_retrieval(self, query: str, config: dict, top_k: int) -> list[RetrievalResult]:
        """Simple text matching fallback."""
        chunks = input_data.data.get("chunks", []) if hasattr(self, "_input") else []
        return [RetrievalResult(id="fallback", content=query, score=0.5, metadata={"source": "naive"})]
