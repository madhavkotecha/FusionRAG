from typing import Any

from .base import BaseComponent


class FAISSIndexer(BaseComponent):
    """Stub: build FAISS vector index with configurable algorithm."""

    async def execute(
        self, input_data: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        index_type = config.get("index_type", "hnsw")
        dimension = config.get("dimension", 1536)
        return {
            "index": {
                "type": index_type,
                "dimension": dimension,
                "status": "built",
            }
        }


class MilvusIndexer(BaseComponent):
    """Stub: index embeddings into a Milvus collection."""

    async def execute(
        self, input_data: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        collection = config.get("collection_name", "default")
        return {
            "index": {
                "collection": collection,
                "status": "indexed",
            }
        }
