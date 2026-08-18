"""Redis cache-aside layer for pipeline service.

All DB reads go through cache first. Mutations invalidate relevant keys.
Cache keys are workspace-scoped: rrag:ps:{entity}:{workspace_id}:{id}
"""
from __future__ import annotations

import json
import logging
from typing import Any

from redis import Redis

logger = logging.getLogger(__name__)

# TTL defaults (seconds)
TTL_SHORT = 60       # Pipeline runs
TTL_MEDIUM = 120     # Lists
TTL_LONG = 300       # Individual entities
TTL_STATIC = 1800    # Components, templates (rarely change)

PREFIX = "rrag:ps"


def _key(entity: str, workspace_id: str, suffix: str = "") -> str:
    if suffix:
        return f"{PREFIX}:{entity}:{workspace_id}:{suffix}"
    return f"{PREFIX}:{entity}:{workspace_id}"


def cache_get(redis: Redis, entity: str, workspace_id: str, suffix: str = "") -> Any | None:
    """Get a cached value. Returns deserialized Python object or None on miss."""
    try:
        raw = redis.get(_key(entity, workspace_id, suffix))
        if raw is not None:
            return json.loads(raw)
    except Exception as e:
        logger.debug(f"Cache get error: {e}")
    return None


def cache_set(redis: Redis, entity: str, workspace_id: str, value: Any,
              suffix: str = "", ttl: int = TTL_LONG) -> None:
    """Set a cached value with TTL."""
    try:
        redis.set(_key(entity, workspace_id, suffix), json.dumps(value, default=str), ex=ttl)
    except Exception as e:
        logger.debug(f"Cache set error: {e}")


def cache_delete(redis: Redis, entity: str, workspace_id: str, suffix: str = "") -> None:
    """Delete a specific cache key."""
    try:
        redis.delete(_key(entity, workspace_id, suffix))
    except Exception as e:
        logger.debug(f"Cache delete error: {e}")


def cache_invalidate_entity(redis: Redis, entity: str, workspace_id: str, entity_id: str = "") -> None:
    """Invalidate a specific entity and its list cache."""
    try:
        if entity_id:
            redis.delete(_key(entity, workspace_id, entity_id))
        redis.delete(_key(entity, workspace_id, "list"))
    except Exception as e:
        logger.debug(f"Cache invalidate error: {e}")
