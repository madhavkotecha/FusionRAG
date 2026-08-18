from typing import Any

from .base import BaseComponent


class VectorRetriever(BaseComponent):
    """Stub: retrieves documents using vector similarity search."""

    async def execute(
        self, input_data: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        top_k = config.get("top_k", 5)
        return {
            "documents": [
                {
                    "content": f"Mock retrieved document (top_k={top_k})",
                    "metadata": {"score": 0.95},
                }
            ]
        }


class HybridRetriever(BaseComponent):
    """Stub: combines vector and keyword-based retrieval."""

    async def execute(
        self, input_data: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        top_k = config.get("top_k", 5)
        alpha = config.get("alpha", 0.5)
        return {
            "documents": [
                {
                    "content": f"Mock hybrid result (top_k={top_k}, alpha={alpha})",
                    "metadata": {"score": 0.92},
                }
            ]
        }
