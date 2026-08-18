from __future__ import annotations

import json
import logging
import os

import numpy as np

from rrag_ingestion.components.storage.base import BaseStorage
from rrag_ingestion.core.base import ComponentResult, register_component

logger = logging.getLogger(__name__)


@register_component
class PGVectorStore(BaseStorage):
    """PostgreSQL pgvector storage from LightRAG."""

    name = "lightrag.pg_vector"
    version = "0.1.0"
    description = "PostgreSQL with pgvector for vector similarity search (from LightRAG)"
    config_schema = {
        "connection_string": {"type": "string", "default": "postgresql://rrag:rrag_dev_password@localhost:5432/rrag"},
        "table_name": {"type": "string", "default": "rrag_embeddings"},
    }

    async def invoke(self, input_data: ComponentResult, config: dict) -> ComponentResult:
        embeddings = input_data.data.get("embeddings", [])
        if not embeddings:
            return ComponentResult(data=input_data.data, metadata={"stored_count": 0})

        conn_str = config.get("connection_string", "postgresql://rrag:rrag_dev_password@localhost:5432/rrag")
        table = config.get("table_name", "rrag_embeddings")

        try:
            import asyncpg

            conn = await asyncpg.connect(conn_str)

            # Ensure pgvector extension and table exist
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            dim = len(embeddings[0].vector if hasattr(embeddings[0], "vector") else embeddings[0].get("vector"))
            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {table} (
                    id TEXT PRIMARY KEY,
                    embedding vector({dim}),
                    content TEXT,
                    metadata JSONB DEFAULT '{{}}'
                )
            """)

            for emb in embeddings:
                eid = emb.id if hasattr(emb, "id") else emb.get("id")
                vec = emb.vector if hasattr(emb, "vector") else emb.get("vector")
                text = emb.text if hasattr(emb, "text") else emb.get("text", "")
                vec_str = "[" + ",".join(str(v) for v in vec) + "]"
                await conn.execute(
                    f"INSERT INTO {table} (id, embedding, content) VALUES ($1, $2, $3) ON CONFLICT (id) DO UPDATE SET embedding = $2, content = $3",
                    eid, vec_str, text,
                )

            await conn.close()

            return ComponentResult(
                data=input_data.data,
                metadata={"stored_count": len(embeddings), "store": "pgvector", "table": table},
            )

        except ImportError:
            return ComponentResult(data=input_data.data, errors=["asyncpg not installed"])
        except Exception as e:
            return ComponentResult(data=input_data.data, errors=[f"PGVector store failed: {e}"])
