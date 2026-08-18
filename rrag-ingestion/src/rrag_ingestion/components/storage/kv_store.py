from __future__ import annotations

import json
import logging

from rrag_ingestion.components.storage.base import BaseStorage
from rrag_ingestion.config import settings
from rrag_ingestion.core.base import ComponentResult, register_component

logger = logging.getLogger(__name__)


@register_component
class RedisKVStore(BaseStorage):
    """Redis-based KV store for metadata and cache, from LightRAG."""

    name = "lightrag.redis_kv"
    version = "0.1.0"
    description = "Redis key-value store for metadata, cache, and pipeline state (from LightRAG)"
    config_schema = {
        "redis_url": {"type": "string", "default": ""},
        "key_prefix": {"type": "string", "default": "rrag:kv:"},
        "ttl_seconds": {"type": "integer", "default": 0, "description": "TTL in seconds, 0 for no expiry"},
    }

    async def invoke(self, input_data: ComponentResult, config: dict) -> ComponentResult:
        redis_url = config.get("redis_url") or settings.redis_url
        key_prefix = config.get("key_prefix", "rrag:kv:")
        ttl = config.get("ttl_seconds", 0)

        try:
            from redis import Redis
            client = Redis.from_url(redis_url)

            stored = 0
            # Store documents
            for doc in input_data.data.get("documents", []):
                doc_data = doc.model_dump() if hasattr(doc, "model_dump") else doc
                key = f"{key_prefix}doc:{doc_data.get('id', '')}"
                client.set(key, json.dumps(doc_data, default=str))
                if ttl > 0:
                    client.expire(key, ttl)
                stored += 1

            # Store chunks
            for chunk in input_data.data.get("chunks", []):
                chunk_data = chunk.model_dump() if hasattr(chunk, "model_dump") else chunk
                key = f"{key_prefix}chunk:{chunk_data.get('id', '')}"
                client.set(key, json.dumps(chunk_data, default=str))
                if ttl > 0:
                    client.expire(key, ttl)
                stored += 1

            client.close()

            return ComponentResult(
                data=input_data.data,
                metadata={"stored_count": stored, "store": "redis"},
            )

        except Exception as e:
            return ComponentResult(data=input_data.data, errors=[f"Redis KV store failed: {e}"])
