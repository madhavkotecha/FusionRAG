from typing import Any

from .base import BaseComponent


class SchemaFreeExtractor(BaseComponent):
    """Stub: open information extraction of entities and relations."""

    async def execute(
        self, input_data: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "entities": [
                {"name": "Example Entity", "type": "Concept", "description": "Mock entity"}
            ],
            "relations": [
                {"source": "Example Entity", "target": "Another Entity", "type": "related_to"}
            ],
        }


class SchemaConstrainedExtractor(BaseComponent):
    """Stub: extract entities/relations following a predefined domain schema."""

    async def execute(
        self, input_data: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "entities": [
                {"name": "Domain Entity", "type": config.get("entity_types", ["Concept"])[0]}
            ],
            "relations": [],
        }


class EntityExtractor(BaseComponent):
    """Stub: LightRAG-style named entity extraction with gleaning."""

    async def execute(
        self, input_data: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "entities": [
                {"name": "Extracted Entity", "type": "Person", "description": "Mock extraction"}
            ],
        }


class SubqueryDecomposer(BaseComponent):
    """Stub: decompose complex queries into sub-queries for multi-hop retrieval."""

    async def execute(
        self, input_data: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        query = input_data.get("query", "")
        return {
            "subqueries": [f"Sub-query 1 from: {query}", f"Sub-query 2 from: {query}"],
        }
