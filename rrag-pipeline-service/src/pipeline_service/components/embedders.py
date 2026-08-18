from typing import Any

from .base import BaseComponent


class OpenAIEmbedder(BaseComponent):
    """Stub: generates embeddings using OpenAI API."""

    async def execute(
        self, input_data: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        model = config.get("model", "text-embedding-3-small")
        return {
            "embeddings": [
                {
                    "vector": [0.1, 0.2, 0.3],
                    "metadata": {"model": model},
                }
            ]
        }


class SentenceTransformerEmbedder(BaseComponent):
    """Stub: generates embeddings using a local Sentence Transformer model."""

    async def execute(
        self, input_data: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        model_name = config.get("model_name", "all-MiniLM-L6-v2")
        return {
            "embeddings": [
                {
                    "vector": [0.4, 0.5, 0.6],
                    "metadata": {"model": model_name},
                }
            ]
        }
