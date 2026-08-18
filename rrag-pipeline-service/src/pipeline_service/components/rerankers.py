from typing import Any

from .base import BaseComponent


class CrossEncoderReranker(BaseComponent):
    """Stub: reranks documents using a cross-encoder model."""

    async def execute(
        self, input_data: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        top_k = config.get("top_k", 3)
        model = config.get("model", "cross-encoder/ms-marco-MiniLM-L-6-v2")
        return {
            "documents": [
                {
                    "content": f"Mock reranked document (model={model})",
                    "metadata": {"score": 0.98, "rank": i},
                }
                for i in range(top_k)
            ]
        }
