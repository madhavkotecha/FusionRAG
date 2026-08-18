from typing import Any

from .base import BaseComponent


class FixedSizeChunker(BaseComponent):
    """Stub: splits documents into fixed-size chunks."""

    async def execute(
        self, input_data: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        chunk_size = config.get("chunk_size", 512)
        return {
            "chunks": [
                {
                    "content": f"Mock chunk (size={chunk_size})",
                    "metadata": {"chunk_index": 0},
                }
            ]
        }


class SemanticChunker(BaseComponent):
    """Stub: splits documents using semantic similarity boundaries."""

    async def execute(
        self, input_data: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        threshold = config.get("threshold", 0.5)
        return {
            "chunks": [
                {
                    "content": f"Mock semantic chunk (threshold={threshold})",
                    "metadata": {"chunk_index": 0},
                }
            ]
        }
