from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from rrag_ingestion.components.agents.base import BaseAgent
from rrag_ingestion.config import settings
from rrag_ingestion.core.base import ComponentResult, register_component

logger = logging.getLogger(__name__)


@register_component
class ConversationMemory(BaseAgent):
    """Manages conversation history and working memory for multi-turn interactions."""

    name = "agent.memory"
    version = "0.1.0"
    description = "Conversation memory manager for multi-turn RAG interactions"
    config_schema = {
        "redis_url": {"type": "string", "default": ""},
        "max_history": {"type": "integer", "default": 20},
        "session_ttl_hours": {"type": "integer", "default": 24},
    }

    async def invoke(self, input_data: ComponentResult, config: dict) -> ComponentResult:
        session_id = input_data.data.get("session_id", "default")
        query = input_data.data.get("query", "")
        answer = input_data.data.get("answer", "")
        redis_url = config.get("redis_url") or settings.redis_url
        max_history = config.get("max_history", 20)
        ttl_hours = config.get("session_ttl_hours", 24)

        try:
            from redis import Redis
            client = Redis.from_url(redis_url)

            key = f"rrag:memory:{session_id}"
            raw = client.get(key)
            history = json.loads(raw) if raw else []

            # Append current turn
            if query:
                history.append({
                    "role": "user",
                    "content": query,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            if answer:
                history.append({
                    "role": "assistant",
                    "content": answer,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

            # Trim to max history
            history = history[-max_history * 2:]

            # Save back
            client.set(key, json.dumps(history), ex=ttl_hours * 3600)
            client.close()

            return ComponentResult(
                data={**input_data.data, "conversation_history": history, "session_id": session_id},
                metadata={"history_length": len(history)},
            )

        except Exception as e:
            return ComponentResult(
                data={**input_data.data, "conversation_history": [], "session_id": session_id},
                errors=[f"Memory management failed: {e}"],
            )
