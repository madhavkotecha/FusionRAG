from __future__ import annotations

import logging

import numpy as np

from rrag_ingestion.components.indexers.base import BaseIndexer
from rrag_ingestion.core.base import ComponentResult, register_component

logger = logging.getLogger(__name__)


@register_component
class MilvusIndexer(BaseIndexer):
    """Milvus vector database indexer from UltraRAG."""

    name = "milvus_indexer"
    version = "0.1.0"
    description = "Milvus vector database for distributed vector search (from UltraRAG)"
    config_schema = {
        "host": {"type": "string", "default": "localhost"},
        "port": {"type": "integer", "default": 19530},
        "collection_name": {"type": "string", "default": "rrag_vectors"},
        "overwrite": {"type": "boolean", "default": False},
    }

    async def invoke(self, input_data: ComponentResult, config: dict) -> ComponentResult:
        embeddings = input_data.data.get("embeddings", [])
        if not embeddings:
            return ComponentResult(data=input_data.data, errors=["No embeddings to index"])

        host = config.get("host", "localhost")
        port = config.get("port", 19530)
        collection_name = config.get("collection_name", "rrag_vectors")
        overwrite = config.get("overwrite", False)

        try:
            from pymilvus import CollectionSchema, DataType, FieldSchema, MilvusClient

            client = MilvusClient(uri=f"http://{host}:{port}")

            sample_vec = embeddings[0].vector if hasattr(embeddings[0], "vector") else embeddings[0].get("vector")
            dim = len(sample_vec)

            if overwrite and client.has_collection(collection_name):
                client.drop_collection(collection_name)

            if not client.has_collection(collection_name):
                schema = CollectionSchema([
                    FieldSchema("id", DataType.INT64, is_primary=True, auto_id=True),
                    FieldSchema("text_id", DataType.VARCHAR, max_length=128),
                    FieldSchema("vector", DataType.FLOAT_VECTOR, dim=dim),
                ])
                client.create_collection(collection_name, schema=schema)

            data = []
            for emb in embeddings:
                vec = emb.vector if hasattr(emb, "vector") else emb.get("vector")
                eid = emb.id if hasattr(emb, "id") else emb.get("id", "")
                data.append({"text_id": eid, "vector": vec})

            client.insert(collection_name, data)

            return ComponentResult(
                data={**input_data.data, "collection_name": collection_name},
                metadata={"indexed_count": len(data), "dimensions": dim},
            )

        except ImportError:
            return ComponentResult(data=input_data.data, errors=["pymilvus not installed"])
        except Exception as e:
            return ComponentResult(data=input_data.data, errors=[f"Milvus indexing failed: {e}"])
